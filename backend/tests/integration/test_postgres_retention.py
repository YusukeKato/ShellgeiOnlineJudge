import os
import socket
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import docker
import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

import scripts.database_migrations as migration_module
from migrations.versions import v0001_legacy_execution_logs
from models.execution import ExecutionResult, ExecutionStatus
from models.execution_log import ExecutionLogEntry
from models.model_db import ExecutionLog
from scripts.database_migrations import (
    DatabaseMigration,
    DatabaseMigrationError,
    migrate_database,
)
from scripts.execution_log_repository import (
    ExecutionLogRepo,
    ExecutionLogRepositoryError,
)
from scripts.execution_log_retention import prune_execution_logs
from scripts.judge import JudgeResult, JudgeVerdict


pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(
        os.getenv("SOJ_RUN_DOCKER_TESTS") != "1",
        reason="set SOJ_RUN_DOCKER_TESTS=1 on an isolated Docker test host",
    ),
]

POSTGRES_IMAGE = (
    "postgres:15-alpine@"
    "sha256:fe0737ba566a2c5b2a28f34433c0a423261900ec17b9bf7ad115e1aae7e57f1b"
)
POSTGRES_USER = "soj_retention_test"
POSTGRES_PASSWORD = "soj_retention_test_password"
POSTGRES_DATABASE = "soj_retention_test"


def _published_postgres_port(container: Any) -> int:
    container.reload()
    bindings = container.attrs["NetworkSettings"]["Ports"]["5432/tcp"]
    assert bindings
    return int(bindings[0]["HostPort"])


def _available_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _wait_for_postgres(container: Any, timeout: float = 20) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        container.reload()
        if container.status == "exited":
            pytest.fail(
                "temporary PostgreSQL exited:\n"
                + container.logs(tail=50).decode("utf-8", errors="replace")
            )
        ready = container.exec_run(
            ["pg_isready", "-U", POSTGRES_USER, "-d", POSTGRES_DATABASE]
        )
        if ready.exit_code == 0:
            return
        time.sleep(0.1)
    pytest.fail("temporary PostgreSQL did not become ready")


def _wait_for_database_connection(
    database_engine: Engine,
    timeout: float = 10,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with database_engine.connect():
                return
        except OperationalError:
            time.sleep(0.1)
    pytest.fail("temporary PostgreSQL port did not become reachable")


def _execution_log_entry(output: str) -> ExecutionLogEntry:
    """入力stdoutから実PostgreSQL保存用のtyped実行ログentryを生成して返す。"""
    execution = ExecutionResult(
        status=ExecutionStatus.COMPLETED,
        stdout=output,
        stderr="",
        exit_code=0,
        timed_out=False,
        truncated=False,
        duration_ms=1,
        artifact=None,
        error=None,
    )
    return ExecutionLogEntry.from_results(
        "STANDARD-00000001",
        f"printf {output}",
        execution,
        JudgeResult(verdict=JudgeVerdict.ACCEPTED),
    )


def test_postgres_migration_repository_retention_and_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 実PostgreSQLでforward/rollback、repository保存、保持上限、lock失敗後の回復を確認する。
    client = docker.from_env()
    container = None
    database_engine = None
    timeout_engine = None
    try:
        assert "name=rootless" in client.info()["SecurityOptions"]
        try:
            client.images.get(POSTGRES_IMAGE)
        except docker.errors.ImageNotFound:
            pytest.skip(f"pull {POSTGRES_IMAGE} before running this test")

        postgres_port = _available_loopback_port()
        container = client.containers.run(
            POSTGRES_IMAGE,
            detach=True,
            environment={
                "POSTGRES_USER": POSTGRES_USER,
                "POSTGRES_PASSWORD": POSTGRES_PASSWORD,
                "POSTGRES_DB": POSTGRES_DATABASE,
            },
            ports={"5432/tcp": ("127.0.0.1", postgres_port)},
            tmpfs={
                "/var/lib/postgresql/data": (
                    "rw,nosuid,nodev,size=128M,nr_inodes=4096,mode=0700"
                )
            },
            mem_limit="256m",
            memswap_limit="256m",
            pids_limit=100,
            log_config=docker.types.LogConfig(type="none"),
        )
        _wait_for_postgres(container)
        port = _published_postgres_port(container)
        database_url = (
            f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
            f"@127.0.0.1:{port}/{POSTGRES_DATABASE}"
        )
        database_engine = create_engine(database_url)
        _wait_for_database_connection(database_engine)
        with database_engine.begin() as connection:
            v0001_legacy_execution_logs.upgrade(connection)
            connection.execute(
                text(
                    """
                    INSERT INTO execution_logs
                        (problem_id, shellgei, output, judge, created_at)
                    VALUES
                        ('STANDARD-00000001', 'printf legacy',
                         'legacy-output', '1', CURRENT_TIMESTAMP)
                    """
                )
            )

        migrate_database(database_engine)
        with Session(database_engine) as db:
            legacy = db.scalar(
                select(ExecutionLog).where(ExecutionLog.shellgei == "printf legacy")
            )
            assert legacy is not None
            assert legacy.execution_status == "legacy_unknown"
            assert legacy.stdout == "legacy-output"
            assert legacy.stderr == ""
            assert legacy.verdict == "accepted"

        migrate_database(database_engine, "0001_legacy_execution_logs")
        rolled_back_columns = {
            column["name"]
            for column in inspect(database_engine).get_columns("execution_logs")
        }
        assert rolled_back_columns.isdisjoint(
            migration_module.v0002_structured_execution_logs.STRUCTURED_COLUMNS
        )

        original_migrations = migration_module.MIGRATIONS

        def fail_after_ddl(connection: Any) -> None:
            """実PostgreSQLへ模擬列を追加後に失敗し、DDL rollbackを検証可能にする。"""
            connection.execute(
                text("ALTER TABLE execution_logs ADD COLUMN temporary_private TEXT")
            )
            raise RuntimeError("migration failed")

        failing_migration = DatabaseMigration(
            revision=original_migrations[1].revision,
            upgrade=fail_after_ddl,
            downgrade=original_migrations[1].downgrade,
        )
        monkeypatch.setattr(
            migration_module,
            "MIGRATIONS",
            (original_migrations[0], failing_migration),
        )
        with pytest.raises(DatabaseMigrationError):
            migrate_database(database_engine)
        assert "temporary_private" not in {
            column["name"]
            for column in inspect(database_engine).get_columns("execution_logs")
        }
        monkeypatch.setattr(migration_module, "MIGRATIONS", original_migrations)
        migrate_database(database_engine)
        migrated_columns = {
            column["name"]: column
            for column in inspect(database_engine).get_columns("execution_logs")
        }
        for required_column in (
            "execution_status",
            "stdout",
            "stderr",
            "timed_out",
            "truncated",
            "verdict",
        ):
            assert migrated_columns[required_column]["nullable"] is False
        assert set(migrated_columns).isdisjoint(
            {"ip_address", "headers", "user_agent", "artifact", "image"}
        )
        with Session(database_engine) as db:
            migrated_legacy = db.scalar(
                select(ExecutionLog).where(ExecutionLog.shellgei == "printf legacy")
            )
            assert migrated_legacy is not None
            db.delete(migrated_legacy)
            db.commit()

        now = datetime.now(timezone.utc)
        with Session(database_engine) as db:
            for index in range(5):
                db.add(
                    ExecutionLog(
                        problem_id="STANDARD-00000001",
                        shellgei=f"printf {index}",
                        output=str(index),
                        judge="1",
                        execution_status="completed",
                        stdout=str(index),
                        stderr="",
                        timed_out=False,
                        truncated=False,
                        verdict="accepted",
                        created_at=(
                            now - timedelta(days=31)
                            if index == 0
                            else now - timedelta(seconds=5 - index)
                        ),
                    )
                )

            deleted = prune_execution_logs(
                db,
                now=now,
                retention_days=30,
                max_rows=3,
            )
            db.commit()

            retained_outputs = db.scalars(
                select(ExecutionLog.output).order_by(ExecutionLog.id)
            ).all()
            assert deleted == 2
            assert retained_outputs == ["2", "3", "4"]

        timeout_engine = create_engine(
            database_url,
            connect_args={"options": "-c lock_timeout=200"},
        )
        timeout_session_factory = sessionmaker(bind=timeout_engine)
        repository = ExecutionLogRepo(session_factory=timeout_session_factory)
        nul_log_id = repository.save(_execution_log_entry("before\x00after"))
        with Session(database_engine) as db:
            assert (
                db.scalar(
                    select(ExecutionLog.output).where(ExecutionLog.id == nul_log_id)
                )
                == "before\N{REPLACEMENT CHARACTER}after"
            )

        with Session(database_engine) as lock_session:
            lock_session.execute(
                text("LOCK TABLE execution_logs IN ACCESS EXCLUSIVE MODE")
            )
            with pytest.raises(ExecutionLogRepositoryError):
                repository.save(_execution_log_entry("blocked"))
            lock_session.rollback()

        recovered_log_id = repository.save(_execution_log_entry("recovered"))
        with Session(database_engine) as db:
            assert (
                db.scalar(
                    select(ExecutionLog.output).where(
                        ExecutionLog.id == recovered_log_id
                    )
                )
                == "recovered"
            )
    finally:
        if timeout_engine is not None:
            timeout_engine.dispose()
        if database_engine is not None:
            database_engine.dispose()
        if container is not None:
            container.remove(force=True, v=True)
        client.close()
