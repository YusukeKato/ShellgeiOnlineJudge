import asyncio
import threading
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import api.api_shellgei as api_shellgei
import main as backend_main
from models.model_db import ExecutionLog
from models.model_shellgei import ShellgeiData
from scripts.database import (
    _engine_options,
    _positive_integer_from_env as _database_positive_integer_from_env,
)
from scripts.execution_log_retention import (
    DEFAULT_EXECUTION_LOG_RETENTION_DAYS,
    _positive_integer_from_env,
    prune_execution_logs,
)
from scripts.execution_log_persistence import (
    ExecutionLogPersistenceError,
    normalize_execution_log_text,
    persist_execution_log,
    persist_execution_log_async,
)
from scripts.runner_protocol import ExecutionResult


def _database_session() -> Session:
    """memory内SQLiteへ実行log tableを作成し、test用Sessionを返す。"""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    ExecutionLog.__table__.create(engine)
    return Session(engine)


def _add_log(db: Session, created_at: datetime) -> ExecutionLog:
    """入力Sessionへ指定日時の実行logを追加・flushし、採番済みmodelを返す。"""
    execution_log = ExecutionLog(
        problem_id="STANDARD-00000001",
        shellgei="printf test",
        output="test",
        judge="1",
        created_at=created_at,
    )
    db.add(execution_log)
    db.flush()
    return execution_log


def test_default_execution_log_retention_is_one_year() -> None:
    # 実行logの既定保持期間が365日であることを確認する。
    assert DEFAULT_EXECUTION_LOG_RETENTION_DAYS == 365


def test_postgres_engine_options_bound_connection_pool_and_statements() -> None:
    # PostgreSQLだけに接続・statement・lock timeout設定が付与されることを確認する。
    assert _engine_options("sqlite+pysqlite:///:memory:", 5) == {}
    assert _engine_options("postgresql+psycopg2://db", 5) == {
        "pool_timeout": 5,
        "connect_args": {
            "connect_timeout": 5,
            "options": "-c statement_timeout=5000 -c lock_timeout=5000",
        },
    }


@pytest.mark.parametrize("value", ["0", "-1", "not-an-integer"])
def test_database_operation_timeout_environment_must_be_positive(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    # DB操作timeoutの環境変数が正の整数でない場合に設定errorとなることを確認する。
    monkeypatch.setenv("TEST_DATABASE_OPERATION_TIMEOUT", value)

    with pytest.raises(RuntimeError, match="must be a positive integer"):
        _database_positive_integer_from_env("TEST_DATABASE_OPERATION_TIMEOUT", 5)


def test_prune_execution_logs_removes_expired_rows() -> None:
    # 保持期限より古いlogだけを削除し、境界日時のlogを残すことを確認する。
    now = datetime(2026, 8, 23, tzinfo=timezone.utc)
    with _database_session() as db:
        expired = _add_log(db, now - timedelta(days=31))
        retained = _add_log(db, now - timedelta(days=30))
        expired_id = expired.id
        retained_id = retained.id

        deleted = prune_execution_logs(
            db,
            now=now,
            retention_days=30,
            max_rows=10,
        )
        db.commit()

        retained_ids = db.scalars(select(ExecutionLog.id)).all()
        assert deleted == 1
        assert retained_ids == [retained_id]
        assert expired_id not in retained_ids


def test_prune_execution_logs_keeps_only_the_newest_id_window() -> None:
    # 件数上限を超えた場合に新しいIDのlogだけが指定件数残ることを確認する。
    now = datetime(2026, 8, 23, tzinfo=timezone.utc)
    with _database_session() as db:
        logs = [_add_log(db, now) for _ in range(5)]

        deleted = prune_execution_logs(
            db,
            now=now,
            retention_days=30,
            max_rows=3,
        )
        db.commit()

        retained_ids = db.scalars(
            select(ExecutionLog.id).order_by(ExecutionLog.id)
        ).all()
        assert deleted == 2
        assert retained_ids == [log.id for log in logs[-3:]]


def test_prune_execution_logs_flushes_a_pending_new_log() -> None:
    # 未flushの新規logを採番してから件数上限を適用することを確認する。
    now = datetime(2026, 8, 23, tzinfo=timezone.utc)
    with _database_session() as db:
        first = _add_log(db, now)
        pending = ExecutionLog(
            problem_id="STANDARD-00000001",
            shellgei="printf pending",
            output="pending",
            judge="1",
            created_at=now,
        )
        db.add(pending)
        first_id = first.id

        deleted = prune_execution_logs(
            db,
            now=now,
            retention_days=30,
            max_rows=1,
        )
        db.commit()

        assert pending.id is not None
        assert deleted == 1
        assert db.scalars(select(ExecutionLog.id)).all() == [pending.id]
        assert first_id != pending.id


def test_persist_execution_log_applies_retention_in_the_log_transaction() -> None:
    # log保存transaction内で保持件数を適用し、新規logだけが残ることを確認する。
    now = datetime.now(timezone.utc)
    with _database_session() as db:
        for offset in range(3, 0, -1):
            _add_log(db, now - timedelta(seconds=offset))
        db.commit()

        def prune(db_session: Session) -> int:
            """入力Sessionへtest固定条件の保持処理を適用し、削除件数を返す。"""
            return prune_execution_logs(
                db_session,
                now=now,
                retention_days=30,
                max_rows=1,
            )

        log_id = persist_execution_log(
            "STANDARD-00000001",
            "printf test",
            "test",
            "1",
            session_factory=lambda: db,
            prune_logs=prune,
        )

        assert db.scalars(select(ExecutionLog.id)).all() == [log_id]


def test_persist_execution_log_normalizes_nul_for_storage() -> None:
    # DB保存前にNULをreplacement characterへ置換し、通常文字列は維持することを確認する。
    with _database_session() as db:
        log_id = persist_execution_log(
            "STANDARD-00000001",
            "printf test",
            "before\x00after",
            "1",
            session_factory=lambda: db,
        )

        stored_output = db.scalar(
            select(ExecutionLog.output).where(ExecutionLog.id == log_id)
        )
        assert stored_output == "before\N{REPLACEMENT CHARACTER}after"
        assert normalize_execution_log_text("no-nul") == "no-nul"


def test_persist_execution_log_rolls_back_and_closes_after_commit_failure() -> None:
    # commit失敗時にrollbackとcloseを必ず順番に実行することを確認する。
    events: list[str] = []

    class FailingSession:
        def add(self, execution_log: ExecutionLog) -> None:
            """入力logへ模擬IDを設定し、add呼出しをeventへ記録する。"""
            setattr(execution_log, "id", 1)
            events.append("add")

        def commit(self) -> None:
            """commit呼出しを記録して模擬例外を送出する。"""
            events.append("commit")
            raise RuntimeError("commit failed")

        def rollback(self) -> None:
            """rollback呼出しをeventへ記録する。"""
            events.append("rollback")

        def close(self) -> None:
            """close呼出しをeventへ記録する。"""
            events.append("close")

    def session_factory() -> Session:
        """失敗動作を持つ模擬Sessionを生成し、Session型として返す。"""
        return FailingSession()  # type: ignore[return-value]

    with pytest.raises(ExecutionLogPersistenceError):
        persist_execution_log(
            "STANDARD-00000001",
            "true",
            "test",
            "1",
            session_factory=session_factory,
            prune_logs=lambda _db: 0,
        )

    assert events == ["add", "commit", "rollback", "close"]


def test_async_execution_log_persistence_does_not_block_the_event_loop() -> None:
    # 同期DB保存をthreadへ移し、待機中もevent loopが動作することを確認する。
    started = threading.Event()
    release = threading.Event()

    def blocking_persistence(*_args: str) -> int:
        """release通知まで同期的に待機し、完了後に固定log IDを返す。"""
        started.set()
        release.wait(timeout=1)
        return 1

    async def scenario() -> None:
        """非同期保存を起動し、event loopを塞がず完了する一連の操作を実行する。"""
        persistence = asyncio.create_task(
            persist_execution_log_async(
                "STANDARD-00000001",
                "true",
                "test",
                "1",
                persist_log=blocking_persistence,
            )
        )
        while not started.is_set():
            await asyncio.sleep(0)
        await asyncio.sleep(0.001)
        assert not persistence.done()
        release.set()
        for _ in range(1000):
            if persistence.done():
                break
            await asyncio.sleep(0.001)
        else:
            raise AssertionError("execution log worker did not finish")
        assert await persistence == 1

    try:
        asyncio.run(scenario())
    finally:
        release.set()


def test_shell_api_returns_result_when_log_persistence_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # DB保存に失敗しても実行・判定結果をid=-1で利用者へ返すことを確認する。
    async def execute(_shellgei: str, _problem_id: str) -> ExecutionResult:
        """入力commandとIDを使用せず、runnerの固定成功結果を返す。"""
        return ExecutionResult(output="test", image="")

    def judge(_output: str, _image: str, _problem_id: str) -> str:
        """入力結果を使用せず、固定の正解判定codeを返す。"""
        return "1"

    async def unavailable(*_args: Any, **_kwargs: Any) -> int:
        """DB worker停止を再現するExecutionLogPersistenceErrorを送出する。"""
        raise ExecutionLogPersistenceError("unavailable")

    monkeypatch.setattr(api_shellgei.runner_gateway, "execute", execute)
    monkeypatch.setattr(api_shellgei.shellgei_judge, "judge", judge)
    monkeypatch.setattr(api_shellgei, "persist_execution_log_async", unavailable)
    monkeypatch.setattr(
        api_shellgei,
        "get_problem_repository",
        lambda: SimpleNamespace(get=lambda _problem_id: object()),
    )

    response = asyncio.run(
        api_shellgei.post_shellgei(
            ShellgeiData(
                shellgei="printf test",
                problem_id="STANDARD-00000001",
            )
        )
    )

    assert response.output == "test"
    assert response.id == "-1"
    assert response.judge == "1"


def test_backend_startup_validates_runner_and_prunes_logs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # backend起動・終了処理がrepository、DB保持、worker終了を所定順で行うことを確認する。
    events: list[str] = []

    class FakeDatabase:
        def commit(self) -> None:
            """模擬DB commitをeventへ記録する。"""
            events.append("commit")

    class DatabaseContext:
        def __enter__(self) -> FakeDatabase:
            """DB context開始を記録し、模擬DBを返す。"""
            events.append("session_enter")
            return FakeDatabase()

        def __exit__(self, *_args: object) -> None:
            """DB context終了をeventへ記録する。"""
            events.append("session_exit")

    class FakeRunnerClient:
        def validate_configuration(self) -> None:
            """runner設定検証の呼出しをeventへ記録する。"""
            events.append("runner_validate")

        def close(self) -> None:
            """runner client終了の呼出しをeventへ記録する。"""
            events.append("runner_close")

    monkeypatch.setattr(
        backend_main.Base.metadata,
        "create_all",
        lambda **_kwargs: events.append("create_all"),
    )
    monkeypatch.setattr(backend_main, "SessionLocal", DatabaseContext)
    monkeypatch.setattr(
        backend_main,
        "prune_execution_logs",
        lambda _db: events.append("prune"),
    )
    monkeypatch.setattr(
        backend_main,
        "load_problem_repository",
        lambda: events.append("repository_load"),
    )
    monkeypatch.setattr(
        backend_main,
        "close_execution_log_persistence",
        lambda: events.append("log_persistence_close"),
    )
    monkeypatch.setattr(backend_main, "runner_client", FakeRunnerClient())

    async def run_lifespan() -> None:
        """backend lifespanへ入り、request受付期間をeventへ記録して終了する。"""
        async with backend_main.lifespan(backend_main.app):
            events.append("serving")

    asyncio.run(run_lifespan())

    assert events == [
        "runner_validate",
        "repository_load",
        "create_all",
        "session_enter",
        "prune",
        "commit",
        "session_exit",
        "serving",
        "runner_close",
        "log_persistence_close",
    ]


@pytest.mark.parametrize("value", ["0", "-1", "not-an-integer"])
def test_execution_log_limit_environment_must_be_positive(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    # log保持件数の環境変数が正の整数でない場合に設定errorとなることを確認する。
    monkeypatch.setenv("TEST_EXECUTION_LOG_LIMIT", value)

    with pytest.raises(RuntimeError, match="must be a positive integer"):
        _positive_integer_from_env("TEST_EXECUTION_LOG_LIMIT", 10)
