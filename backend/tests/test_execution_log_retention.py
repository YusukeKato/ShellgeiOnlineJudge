import asyncio
import json
import logging
import threading
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import soj_backend.api.api_shellgei as api_shellgei
import soj_backend.main as backend_main
from soj_backend.models.execution_log import ExecutionLogEntry
from soj_backend.models.model_db import ExecutionLog
from soj_shared.submission_request import ShellgeiData
from soj_shared.submission_status import SubmissionPersistenceStatus, SubmissionStatus
from soj_backend.models.submission import SubmissionResult
from soj_backend.database import (
    _engine_options,
    _positive_integer_from_env as _database_positive_integer_from_env,
)
from soj_backend.execution_log_retention import (
    DEFAULT_EXECUTION_LOG_RETENTION_DAYS,
    _positive_integer_from_env,
    prune_execution_logs,
)
from soj_backend.execution_log_repository import (
    ExecutionLogRepo,
    ExecutionLogRepositoryError,
    normalize_execution_log_text,
    save_execution_log_async,
)
from soj_backend.judge import JudgeResult, JudgeVerdict
from soj_shared.runner_protocol import (
    ExecutionArtifact,
    ExecutionResult,
    ExecutionStatus,
)
from soj_shared.structured_logging import SAFE_EVENT_LOGGER_NAME


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
        execution_status="completed",
        stdout="test",
        stderr="",
        timed_out=False,
        truncated=False,
        verdict="accepted",
        created_at=created_at,
    )
    db.add(execution_log)
    db.flush()
    return execution_log


def _execution_log_entry(
    output: str = "test",
    *,
    stderr: str = "",
    verdict: JudgeVerdict = JudgeVerdict.ACCEPTED,
) -> ExecutionLogEntry:
    """任意の分離出力と判定から、repository test用のtyped保存entryを返す。"""
    execution = ExecutionResult(
        status=ExecutionStatus.COMPLETED,
        stdout=output,
        stderr=stderr,
        exit_code=0,
        timed_out=False,
        truncated=False,
        duration_ms=12,
        artifact=None,
        error=None,
    )
    return ExecutionLogEntry.from_results(
        "STANDARD-00000001",
        "printf test",
        execution,
        JudgeResult(verdict=verdict),
    )


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
            "options": "-c statement_timeout=5000 -c lock_timeout=5000 -c search_path=public",
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
            execution_status="completed",
            stdout="pending",
            stderr="",
            timed_out=False,
            truncated=False,
            verdict="accepted",
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


def test_execution_log_repository_applies_retention_in_the_log_transaction() -> None:
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

        repository = ExecutionLogRepo(session_factory=lambda: db, prune_logs=prune)
        log_id = repository.save(_execution_log_entry())

        assert db.scalars(select(ExecutionLog.id)).all() == [log_id]


def test_execution_log_repository_saves_structured_result_and_normalizes_nul() -> None:
    # DB保存前にNULをreplacement characterへ置換し、通常文字列は維持することを確認する。
    with _database_session() as db:
        repository = ExecutionLogRepo(session_factory=lambda: db)
        log_id = repository.save(
            _execution_log_entry("before\x00after", stderr="warning")
        )

        stored = db.scalar(select(ExecutionLog).where(ExecutionLog.id == log_id))
        assert stored is not None
        assert stored.output == "before\N{REPLACEMENT CHARACTER}afterwarning"
        assert stored.stdout == "before\N{REPLACEMENT CHARACTER}after"
        assert stored.stderr == "warning"
        assert stored.execution_status == "completed"
        assert stored.exit_code == 0
        assert stored.timed_out is False
        assert stored.truncated is False
        assert stored.duration_ms == 12
        assert stored.verdict == "accepted"
        assert stored.judge_reason is None
        assert normalize_execution_log_text("no-nul") == "no-nul"


def test_execution_log_repository_rolls_back_and_closes_after_commit_failure() -> None:
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

    repository = ExecutionLogRepo(
        session_factory=session_factory,
        prune_logs=lambda _db: 0,
    )
    with pytest.raises(ExecutionLogRepositoryError):
        repository.save(_execution_log_entry())

    assert events == ["add", "commit", "rollback", "close"]


def test_async_execution_log_repository_does_not_block_the_event_loop() -> None:
    # 同期DB保存をthreadへ移し、待機中もevent loopが動作することを確認する。
    started = threading.Event()
    release = threading.Event()

    def blocking_persistence(_entry: ExecutionLogEntry) -> int:
        """release通知まで同期的に待機し、完了後に固定log IDを返す。"""
        started.set()
        release.wait(timeout=1)
        return 1

    async def scenario() -> None:
        """非同期保存を起動し、event loopを塞がず完了する一連の操作を実行する。"""
        persistence = asyncio.create_task(
            save_execution_log_async(
                _execution_log_entry(),
                persist_entry=blocking_persistence,
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


def test_async_execution_log_success_event_uses_request_id_without_user_data(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # DB保存成功eventへrequest IDと所要時間だけを記録し、entry内のcommand・出力を複製しない。
    request_id = "a" * 32
    entry = _execution_log_entry("PRIVATE-OUTPUT")
    caplog.set_level(logging.INFO, logger=SAFE_EVENT_LOGGER_NAME)

    result = asyncio.run(
        save_execution_log_async(
            entry,
            request_id=request_id,
            persist_entry=lambda _entry: 42,
        )
    )

    assert result == 42
    event = json.loads(caplog.records[-1].message)
    assert event["event"] == "execution_log_save_completed"
    assert event["component"] == "execution_log"
    assert event["request_id"] == request_id
    assert event["duration_ms"] >= 0
    assert "PRIVATE-OUTPUT" not in caplog.records[-1].message
    assert entry.shellgei not in caplog.records[-1].message


def test_async_execution_log_failure_event_redacts_exception_and_entry(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # DB保存例外に利用者dataが含まれても、失敗eventには例外文・command・出力を記録しない。
    request_id = "b" * 32
    entry = _execution_log_entry("PRIVATE-OUTPUT")

    def fail_persistence(_entry: ExecutionLogEntry) -> int:
        """入力entryは使用せず、機密文字列を含むrepository例外を送出する。"""
        raise ExecutionLogRepositoryError("PRIVATE-DATABASE-ERROR")

    caplog.set_level(logging.WARNING, logger=SAFE_EVENT_LOGGER_NAME)

    with pytest.raises(ExecutionLogRepositoryError):
        asyncio.run(
            save_execution_log_async(
                entry,
                request_id=request_id,
                persist_entry=fail_persistence,
            )
        )

    event = json.loads(caplog.records[-1].message)
    assert event["event"] == "execution_log_save_failed"
    assert event["request_id"] == request_id
    serialized_event = caplog.records[-1].message
    assert "PRIVATE-DATABASE-ERROR" not in serialized_event
    assert "PRIVATE-OUTPUT" not in serialized_event
    assert entry.shellgei not in serialized_event


def test_shell_api_returns_result_when_log_persistence_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # use caseが返したDB保存不能結果を、id=-1の既存responseへ変換することを確認する。
    async def submit(_shellgei: str, _problem_id: str) -> SubmissionResult:
        """入力を使わず、実行・判定済みだがログ未保存の提出結果を返す。"""
        execution = ExecutionResult(
            status=ExecutionStatus.COMPLETED,
            stdout="test",
            stderr="",
            exit_code=0,
            timed_out=False,
            truncated=False,
            duration_ms=1,
            artifact=None,
            error=None,
        )
        return SubmissionResult(
            status=SubmissionStatus.COMPLETED,
            submitted_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
            execution=execution,
            judgment=JudgeResult(verdict=JudgeVerdict.ACCEPTED),
            persistence=SubmissionPersistenceStatus.UNAVAILABLE,
        )

    monkeypatch.setattr(api_shellgei.submit_solution_service, "submit", submit)

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

    class FakeRunnerClient:
        def validate_configuration(self) -> None:
            """runner設定検証の呼出しをeventへ記録する。"""
            events.append("runner_validate")

        def close(self) -> None:
            """runner client終了の呼出しをeventへ記録する。"""
            events.append("runner_close")

    class FakeExecutionLogRepo:
        def prune(self) -> int:
            """起動時retention呼出しを記録し、削除0件を返す。"""
            events.append("prune")
            return 0

    monkeypatch.setattr(
        backend_main,
        "validate_runtime_database",
        lambda _engine: events.append("validate_database"),
    )
    monkeypatch.setattr(backend_main, "execution_log_repo", FakeExecutionLogRepo())
    monkeypatch.setattr(
        backend_main,
        "load_problem_repository",
        lambda: events.append("repository_load"),
    )
    monkeypatch.setattr(
        backend_main,
        "close_execution_log_repository",
        lambda: events.append("log_repository_close"),
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
        "validate_database",
        "prune",
        "serving",
        "runner_close",
        "log_repository_close",
    ]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("request_id", "a" * 32),
        # RFC 5737の文書・テスト専用範囲TEST-NET-2を使い、実在利用者のIP addressを含めない。
        ("ip_address", "198.51.100.10"),
        ("headers", {"User-Agent": "private"}),
    ],
)
def test_execution_log_entry_rejects_request_metadata(
    field: str,
    value: object,
) -> None:
    # request ID・IP address・HTTP header等をtyped保存境界へ追加できないことを確認する。
    data = _execution_log_entry().model_dump()
    data[field] = value

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ExecutionLogEntry.model_validate(data)


def test_execution_log_entry_discards_image_artifact_before_repository() -> None:
    # typed実行結果に画像があっても、保存entryへartifact dataや内部error fieldを移さないことを確認する。
    result = ExecutionResult(
        status=ExecutionStatus.COMPLETED,
        stdout="",
        stderr="",
        exit_code=0,
        timed_out=False,
        truncated=False,
        duration_ms=1,
        artifact=ExecutionArtifact(
            path="media/output.jpg",
            media_type="image/jpeg",
            data="encoded-private-image",
        ),
        error=None,
    )

    entry = ExecutionLogEntry.from_results(
        "IMAGE-00000001",
        "convert image",
        result,
        JudgeResult(verdict=JudgeVerdict.ACCEPTED),
    )

    stored_fields = entry.model_dump()
    assert "artifact" not in stored_fields
    assert "error" not in stored_fields
    assert "encoded-private-image" not in str(stored_fields)


def test_execution_log_entry_discards_internal_error_detail() -> None:
    # runner内部errorを一般化し、host path等の詳細がrepository入力へ残らないことを確認する。
    result = ExecutionResult(
        status=ExecutionStatus.ERROR,
        stdout="",
        stderr="",
        exit_code=None,
        timed_out=False,
        truncated=False,
        duration_ms=1,
        artifact=None,
        error="private backend path: /srv/internal/secret",
    )

    entry = ExecutionLogEntry.from_results(
        "STANDARD-00000001",
        "true",
        result,
        JudgeResult(verdict=JudgeVerdict.EXECUTION_FAILURE),
    )

    assert entry.legacy_output == "Error during execution"
    assert "/srv/internal/secret" not in str(entry.model_dump())


def test_execution_log_table_has_no_request_or_artifact_columns() -> None:
    # 永続schemaにrequest ID・IP・header・User-Agent・画像artifact用の列がないことを確認する。
    stored_columns = set(ExecutionLog.__table__.columns.keys())
    forbidden_columns = {
        "ip_address",
        "request_id",
        "forwarded_for",
        "headers",
        "user_agent",
        "artifact",
        "image",
    }

    assert stored_columns.isdisjoint(forbidden_columns)


@pytest.mark.parametrize("value", ["0", "-1", "not-an-integer"])
def test_execution_log_limit_environment_must_be_positive(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    # log保持件数の環境変数が正の整数でない場合に設定errorとなることを確認する。
    monkeypatch.setenv("TEST_EXECUTION_LOG_LIMIT", value)

    with pytest.raises(RuntimeError, match="must be a positive integer"):
        _positive_integer_from_env("TEST_EXECUTION_LOG_LIMIT", 10)
