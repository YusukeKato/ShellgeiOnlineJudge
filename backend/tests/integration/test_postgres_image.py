import os
import time
import uuid
from contextlib import ExitStack
from typing import Any

import docker
import pytest

from tests.postgres_support import database_image, upstream_postgres_image


pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(
        os.getenv("SOJ_RUN_DOCKER_TESTS") != "1",
        reason="enable Docker tests after building the database image",
    ),
]


def sql(container: Any, statement: str) -> str:
    """専用DBへ固定SQLを実行し、失敗を隠さず結果を返す。外部portは使用しない。"""
    result = container.exec_run(
        [
            "psql",
            "-U",
            "upgrade_test",
            "-d",
            "upgrade_test",
            "-At",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            statement,
        ]
    )
    assert result.exit_code == 0, result.output.decode()
    return result.output.decode().strip()


def wait_ready(container: Any) -> None:
    """initdb中の一時serverを避け、PID 1のpostgresがSQLを受け付けるまで上限付きで待つ。"""
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        container.reload()
        if container.status == "exited":
            raise RuntimeError("temporary database exited")
        result = container.exec_run(["cat", "/proc/1/comm"])
        if result.exit_code == 0 and result.output.strip() == b"postgres":
            result = container.exec_run(["pg_isready", "-U", "upgrade_test"])
            if result.exit_code == 0:
                return
        time.sleep(0.2)
    raise TimeoutError("temporary database did not become ready")


def test_existing_database_survives_image_upgrade_and_rollback() -> None:
    # 旧imageの初期化済みvolumeを新imageで読み書きし、旧imageへの復帰後もdataと非root実行を確認する。
    assert os.environ.get("DOCKER_HOST", "").startswith("unix://")
    client = docker.from_env(timeout=30)
    with ExitStack() as cleanup:
        cleanup.callback(client.close)
        assert "name=rootless" in client.info()["SecurityOptions"]
        old = client.images.get(upstream_postgres_image())
        new = client.images.get(database_image())
        for field in ("Entrypoint", "Cmd", "Volumes"):
            assert new.attrs["Config"][field] == old.attrs["Config"][field]
        assert "PGDATA=/var/lib/postgresql/data" in new.attrs["Config"]["Env"]
        owner = "soj-db-upgrade-" + uuid.uuid4().hex
        volume = client.volumes.create(name=owner, labels={"soj.test.owner": owner})
        cleanup.callback(volume.remove)
        previous_version = None
        for index, image in enumerate((old.id, new.id, old.id)):
            assert image is not None
            with ExitStack() as containers:
                container = client.containers.create(
                    image,
                    name=f"{owner}-{index}",
                    environment={
                        "POSTGRES_USER": "upgrade_test",
                        "POSTGRES_DB": "upgrade_test",
                        "POSTGRES_PASSWORD": uuid.uuid4().hex,
                    },
                    volumes={
                        volume.name: {"bind": "/var/lib/postgresql/data", "mode": "rw"}
                    },
                    network_mode="none",
                    mem_limit="256m",
                    memswap_limit="256m",
                    pids_limit=100,
                    log_config=docker.types.LogConfig(type="none"),
                )
                containers.callback(container.remove, force=True, v=True)
                container.start()
                wait_ready(container)
                version = sql(container, "SHOW server_version_num")
                assert 150000 <= int(version) < 160000
                if previous_version is not None:
                    assert version == previous_version
                previous_version = version
                status = container.exec_run(["cat", "/proc/1/status"])
                assert status.exit_code == 0
                uid = next(
                    line
                    for line in status.output.decode().splitlines()
                    if line.startswith("Uid:")
                )
                assert all(int(value) != 0 for value in uid.split()[1:])
                if index == 0:
                    sql(container, "CREATE TABLE retained (id integer PRIMARY KEY)")
                assert sql(container, "SELECT count(*) FROM retained") == str(index)
                sql(container, f"INSERT INTO retained VALUES ({index})")
                assert sql(container, "SELECT count(*) FROM retained") == str(index + 1)
                # SIGTERM/SIGINTを受けるPID 1を維持し、次の起動前に正常終了を確認する。
                container.stop(timeout=20)
                container.reload()
                assert container.attrs["State"]["ExitCode"] == 0
