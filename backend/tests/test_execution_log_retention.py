import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import api.api_shellgei as api_shellgei
import main as backend_main
from models.model_db import ExecutionLog
from models.model_shellgei import ShellgeiData
from scripts.execution_log_retention import (
    DEFAULT_EXECUTION_LOG_RETENTION_DAYS,
    _positive_integer_from_env,
    prune_execution_logs,
)


def _database_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    ExecutionLog.__table__.create(engine)
    return Session(engine)


def _add_log(db: Session, created_at: datetime) -> ExecutionLog:
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
    assert DEFAULT_EXECUTION_LOG_RETENTION_DAYS == 365


def test_prune_execution_logs_removes_expired_rows() -> None:
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


def test_shell_api_applies_retention_in_the_log_transaction(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    now = datetime.now(timezone.utc)
    with _database_session() as db:
        for offset in range(3, 0, -1):
            _add_log(db, now - timedelta(seconds=offset))
        db.commit()

        class NoLatestLog:
            def order_by(self, *_args: object) -> "NoLatestLog":
                return self

            def first(self) -> None:
                return None

        async def run_with_timeout(_shellgei: str, _problem_id: str) -> list[str]:
            return ["test", ""]

        def judge(_output: str, _image: str, _problem_id: str) -> str:
            return "1"

        def prune(db_session: Session) -> int:
            return prune_execution_logs(
                db_session,
                now=now,
                retention_days=30,
                max_rows=1,
            )

        monkeypatch.setattr(
            api_shellgei.docker_client,
            "run_with_timeout",
            run_with_timeout,
        )
        monkeypatch.setattr(api_shellgei.shellgei_judge, "judge", judge)
        monkeypatch.setattr(api_shellgei, "prune_execution_logs", prune)
        monkeypatch.setattr(db, "query", lambda *_args: NoLatestLog())
        yaml_dir = tmp_path / "problems" / "yaml_data"
        yaml_dir.mkdir(parents=True)
        (yaml_dir / "STANDARD-00000001.yaml").touch()
        monkeypatch.setattr(
            api_shellgei,
            "__file__",
            str(tmp_path / "api" / "api_shellgei.py"),
        )

        response = asyncio.run(
            api_shellgei.post_shellgei(
                ShellgeiData(
                    shellgei="printf test",
                    problem_id="STANDARD-00000001",
                ),
                db,
            )
        )

        retained_ids = db.scalars(select(ExecutionLog.id)).all()
        assert response.output == "test"
        assert response.id == str(retained_ids[0])
        assert len(retained_ids) == 1


def test_backend_startup_prunes_before_initializing_sandbox_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class FakeDatabase:
        def commit(self) -> None:
            events.append("commit")

    class DatabaseContext:
        def __enter__(self) -> FakeDatabase:
            events.append("session_enter")
            return FakeDatabase()

        def __exit__(self, *_args: object) -> None:
            events.append("session_exit")

    class FakeDockerClient:
        def close(self) -> None:
            events.append("client_close")

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
        backend_main.manager,
        "initialize_pool",
        lambda: events.append("pool_initialize"),
    )
    monkeypatch.setattr(
        backend_main.manager,
        "shutdown_pool",
        lambda: events.append("pool_shutdown"),
    )
    monkeypatch.setattr(
        backend_main.api_shellgei,
        "docker_client",
        FakeDockerClient(),
    )

    async def run_lifespan() -> None:
        async with backend_main.lifespan(backend_main.app):
            events.append("serving")

    asyncio.run(run_lifespan())

    assert events == [
        "create_all",
        "session_enter",
        "prune",
        "commit",
        "session_exit",
        "pool_initialize",
        "serving",
        "pool_shutdown",
        "client_close",
    ]


@pytest.mark.parametrize("value", ["0", "-1", "not-an-integer"])
def test_execution_log_limit_environment_must_be_positive(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv("TEST_EXECUTION_LOG_LIMIT", value)

    with pytest.raises(RuntimeError, match="must be a positive integer"):
        _positive_integer_from_env("TEST_EXECUTION_LOG_LIMIT", 10)
