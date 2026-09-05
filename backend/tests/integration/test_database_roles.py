import os
import time
import uuid
from collections.abc import Iterator

import docker
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

from soj_backend.database_access import (
    provision_runtime_role,
    validate_runtime_database,
)
from soj_backend.database_migrations import migrate_database
from soj_backend.execution_log_repository import ExecutionLogRepo
from soj_backend.execution_log_retention import prune_execution_logs
from soj_backend.models.execution_log import ExecutionLogEntry
from soj_backend.judge import JudgeResult, JudgeVerdict
from soj_shared.models.execution import ExecutionResult, ExecutionStatus
from tests.postgres_support import database_image


pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(
        os.getenv("SOJ_RUN_DOCKER_TESTS") != "1",
        reason="requires isolated rootless Docker",
    ),
]


@pytest.fixture
def admin_database() -> Iterator[Engine]:
    """専用tmpfs DBだけを作成し、admin接続を返す。本番volumeやroleへ触れない。"""
    assert os.environ.get("DOCKER_HOST", "").startswith("unix://")
    client = docker.from_env(timeout=10)
    container = None
    engine = None
    try:
        assert "name=rootless" in client.info()["SecurityOptions"]
        client.images.get(database_image())
        password = uuid.uuid4().hex
        container = client.containers.create(
            database_image(),
            name=f"soj-db-role-{uuid.uuid4().hex}",
            environment={
                "POSTGRES_USER": "role_admin",
                "POSTGRES_PASSWORD": password,
                "POSTGRES_DB": "soj",
            },
            ports={"5432/tcp": ("127.0.0.1", 0)},
            tmpfs={
                "/var/lib/postgresql/data": "rw,nosuid,nodev,size=128M,nr_inodes=4096,mode=0700"
            },
            mem_limit="256m",
            memswap_limit="256m",
            pids_limit=100,
            log_config=docker.types.LogConfig(type="none"),
        )
        container.start()
        container.reload()
        port = int(
            container.attrs["NetworkSettings"]["Ports"]["5432/tcp"][0]["HostPort"]
        )
        engine = create_engine(
            URL.create(
                "postgresql",
                username="role_admin",
                password=password,
                host="127.0.0.1",
                port=port,
                database="soj",
            ),
            connect_args={"connect_timeout": 2},
        )
        deadline = time.monotonic() + 20
        while True:
            try:
                with engine.connect():
                    break
            except DBAPIError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("temporary DB did not start") from None
                time.sleep(0.1)
        yield engine
    finally:
        try:
            if engine is not None:
                engine.dispose()
            if container is not None:
                container.remove(force=True, v=True)
        finally:
            client.close()


def test_runtime_role_preserves_legacy_data_and_cannot_run_ddl(
    admin_database: Engine,
) -> None:
    # 旧volume相当のlegacy行・所有者を維持して分離し、保存/retentionは成功、管理操作は拒否する。
    migrate_database(admin_database, "0001_legacy_execution_logs")
    with admin_database.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO execution_logs(problem_id, shellgei, output, judge) VALUES ('old', 'echo old', 'old', '1')"
            )
        )
    migrate_database(admin_database)
    password = "test'password@with\\reserved"
    provision_runtime_role(admin_database, "soj_app", password)
    provision_runtime_role(admin_database, "soj_app", password)
    app = create_engine(
        admin_database.url.set(username="soj_app", password=password),
        connect_args={"connect_timeout": 2},
    )
    try:
        validate_runtime_database(app)
        with pytest.raises(RuntimeError):
            validate_runtime_database(admin_database)
        with app.connect() as connection:
            assert connection.scalar(text("SELECT output FROM execution_logs")) == "old"
            assert (
                connection.scalar(
                    text(
                        "SELECT pg_get_userbyid(relowner) FROM pg_class WHERE oid = 'execution_logs'::regclass"
                    )
                )
                == "role_admin"
            )
        repo = ExecutionLogRepo(
            sessionmaker(bind=app),
            prune_logs=lambda session: prune_execution_logs(session, max_rows=1),
        )
        execution = ExecutionResult(
            status=ExecutionStatus.COMPLETED,
            stdout="new",
            stderr="",
            exit_code=0,
            timed_out=False,
            truncated=False,
            duration_ms=1,
            artifact=None,
            error=None,
        )
        entry = ExecutionLogEntry.from_results(
            "STANDARD-00000001",
            "echo new",
            execution,
            JudgeResult(verdict=JudgeVerdict.ACCEPTED),
        )
        assert repo.save(entry) == 2
        assert repo.prune() == 0
        with app.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM execution_logs")) == 1
        for sql in (
            "CREATE TABLE forbidden(id int)",
            "CREATE TEMP TABLE forbidden(id int)",
            "ALTER TABLE execution_logs ADD COLUMN forbidden int",
            "DROP TABLE execution_logs",
            "TRUNCATE execution_logs",
            "UPDATE execution_logs SET output = 'forbidden'",
            "DELETE FROM soj_schema_migrations",
            "SELECT setval('execution_logs_id_seq', 1)",
            "CREATE ROLE forbidden",
            "SET ROLE role_admin",
        ):
            with pytest.raises(DBAPIError), app.begin() as connection:
                connection.execute(text(sql))
        # 旧binary向けschema rollbackは管理者だけが行い、再upgrade・再grantで復帰する。
        migrate_database(admin_database, "0001_legacy_execution_logs")
        with pytest.raises(RuntimeError):
            validate_runtime_database(app)
        migrate_database(admin_database)
        provision_runtime_role(admin_database, "soj_app", password)
        validate_runtime_database(app)
        with app.connect() as connection:
            assert connection.scalar(text("SELECT output FROM execution_logs")) == "new"
        with pytest.raises(RuntimeError):
            provision_runtime_role(admin_database, "role_admin", "do-not-change")
    finally:
        app.dispose()


def test_privilege_drift_and_role_membership_are_rejected(
    admin_database: Engine,
) -> None:
    # 列単位UPDATE、PUBLIC権限、role所属の後付けでもruntime検査を通過しない。
    migrate_database(admin_database)
    provision_runtime_role(admin_database, "soj_app", "app-password")
    app = create_engine(
        admin_database.url.set(username="soj_app", password="app-password")
    )
    try:
        for grant, revoke in (
            (
                "GRANT UPDATE(output) ON execution_logs TO soj_app",
                "REVOKE UPDATE(output) ON execution_logs FROM soj_app",
            ),
            (
                "GRANT CREATE ON SCHEMA public TO PUBLIC",
                "REVOKE CREATE ON SCHEMA public FROM PUBLIC",
            ),
            ("GRANT role_admin TO soj_app", "REVOKE role_admin FROM soj_app"),
        ):
            with admin_database.begin() as connection:
                connection.execute(text(grant))
            with pytest.raises(RuntimeError):
                validate_runtime_database(app)
            with admin_database.begin() as connection:
                connection.execute(text(revoke))
            validate_runtime_database(app)
    finally:
        app.dispose()
