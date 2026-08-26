import os
import socket
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import docker
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from models.model_db import ExecutionLog
from scripts.execution_log_persistence import (
    ExecutionLogPersistenceError,
    persist_execution_log,
)
from scripts.execution_log_retention import prune_execution_logs


pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(
        os.getenv("SOJ_RUN_DOCKER_TESTS") != "1",
        reason="set SOJ_RUN_DOCKER_TESTS=1 on an isolated Docker test host",
    ),
]

POSTGRES_IMAGE = "postgres:15-alpine"
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


def test_postgres_enforces_execution_log_age_and_row_limits() -> None:
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
        ExecutionLog.__table__.create(database_engine)

        now = datetime.now(timezone.utc)
        with Session(database_engine) as db:
            for index in range(5):
                db.add(
                    ExecutionLog(
                        problem_id="STANDARD-00000001",
                        shellgei=f"printf {index}",
                        output=str(index),
                        judge="1",
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
        nul_log_id = persist_execution_log(
            "STANDARD-00000001",
            "printf nul",
            "before\x00after",
            "1",
            session_factory=timeout_session_factory,
        )
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
            with pytest.raises(ExecutionLogPersistenceError):
                persist_execution_log(
                    "STANDARD-00000001",
                    "printf blocked",
                    "blocked",
                    "1",
                    session_factory=timeout_session_factory,
                )
            lock_session.rollback()

        recovered_log_id = persist_execution_log(
            "STANDARD-00000001",
            "printf recovered",
            "recovered",
            "1",
            session_factory=timeout_session_factory,
        )
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
            container.remove(force=True)
        client.close()
