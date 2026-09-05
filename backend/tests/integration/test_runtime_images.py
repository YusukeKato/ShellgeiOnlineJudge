import json
import os
import time
import uuid
from collections.abc import Iterator
from contextlib import ExitStack
from pathlib import Path
from typing import Any

import docker
import pytest
import yaml

from scripts.container_manager import OWNER_LABEL
from scripts.problem_repository import build_problem_repository
from tests.postgres_support import database_image


pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(
        os.getenv("SOJ_RUN_DOCKER_TESTS") != "1"
        or os.getenv("SOJ_RUN_RUNTIME_IMAGE_TESTS") != "1",
        reason="enable Docker and runtime image tests after building both production targets",
    ),
]
ROOT = Path(__file__).resolve().parents[3]
COMPOSE = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))


@pytest.fixture
def runtime_client() -> Iterator[Any]:
    """明示されたlocal rootless daemonとbuild済みimageだけを使うtest clientを返す。"""
    assert os.environ.get("DOCKER_HOST", "").startswith("unix://")
    client = docker.from_env(timeout=30)
    try:
        assert "name=rootless" in client.info()["SecurityOptions"]
        for service in ("backend", "runner"):
            client.images.get(os.environ[f"SOJ_{service.upper()}_RUNTIME_IMAGE"])
        yield client
    finally:
        client.close()


def _image(service: str) -> str:
    """実際にbuildした各runtime imageの明示的なreferenceを環境から返す。"""
    return os.environ[f"SOJ_{service.upper()}_RUNTIME_IMAGE"]


def _restrictions(service: str) -> dict[str, Any]:
    """Composeの実行制限をDocker SDKへ渡し、test独自の緩い設定で起動しない。"""
    config = COMPOSE["services"][service]
    return {
        "read_only": config["read_only"],
        "tmpfs": dict(value.split(":", 1) for value in config["tmpfs"]),
        "cap_drop": config["cap_drop"],
        "security_opt": config["security_opt"],
    }


@pytest.mark.parametrize("service", ["backend", "runner"])
def test_production_image_contains_only_its_runtime_boundary(
    runtime_client: Any, service: str
) -> None:
    # 実imageのPython/Expat修正版、非root import、不要package・逆側コード・開発資産の不在を確認する。
    script = """
import importlib
import importlib.metadata
import json
import os
import pyexpat
import sys
from pathlib import Path
from scripts.problem_repository import load_problem_repository

service = os.environ['SOJ_TEST_SERVICE']
# SOJ-022の修正版を維持し、scannerが取りこぼす内蔵ExpatのCVE-2026-72522も再導入しない。
assert sys.version_info[:3] >= (3, 12, 14)
assert pyexpat.version_info >= (2, 8, 3)
importlib.import_module('main' if service == 'backend' else 'runner_main')
load_problem_repository()
assert os.getuid() == os.getgid() == 10001
assert not os.access('/app/backend', os.W_OK)
assert not Path('/run/docker.sock').exists()
assert not Path('tests').exists()
assert not Path('problems/yaml_data').exists()
assert not Path('/build').exists()
assert not list(Path('/app').rglob('poetry.lock'))
assert not list(Path('/app').rglob('pyproject.toml'))
assert 'CapEff:\\t0000000000000000' in Path('/proc/self/status').read_text()
packages = {d.metadata['Name'].lower() for d in importlib.metadata.distributions()}
assert not packages.intersection({'poetry', 'pytest', 'ruff', 'mypy', 'gunicorn', 'pytz', 'playwright', 'pyee'})
assert not any(name.startswith('types-') for name in packages)
if service == 'backend':
    assert 'docker' not in packages
    assert {'sqlalchemy', 'psycopg2-binary'} <= packages
    assert not Path('runner_main.py').exists()
    assert not Path('scripts/container_manager.py').exists()
    assert not Path('scripts/sandbox_executor.py').exists()
else:
    assert 'docker' in packages
    assert not packages.intersection({'sqlalchemy', 'psycopg2-binary'})
    assert not Path('main.py').exists()
    assert not Path('api').exists()
    assert not Path('migrations').exists()
    assert not Path('scripts/database.py').exists()
print(json.dumps({'service': service, 'uid': os.getuid(), 'packages': sorted(packages)}))
"""
    output = runtime_client.containers.run(
        _image(service),
        ["python", "-c", script],
        environment={"SOJ_TEST_SERVICE": service, "DATABASE_URL": "sqlite:///:memory:"},
        network_mode="none",
        remove=True,
        **_restrictions(service),
    )
    assert json.loads(output)["uid"] == 10001


def _socket_binding() -> dict[str, dict[str, str]]:
    """明示済みlocal daemon socketを、test runner内の固定pathへmountする設定を返す。"""
    return {
        os.environ["DOCKER_HOST"].removeprefix("unix://"): {
            "bind": "/run/docker.sock",
            "mode": "ro",
        }
    }


def _socket_gid(client: Any) -> int:
    """rootless namespace内のsocket GIDを読み取り、host側の数値を誤用しない。"""
    output = client.containers.run(
        _image("runner"),
        ["python", "-c", "import os; print(os.stat('/run/docker.sock').st_gid)"],
        user="0:0",
        volumes=_socket_binding(),
        network_mode="none",
        remove=True,
        **_restrictions("runner"),
    )
    return int(output)


def test_runner_socket_requires_the_explicit_supplementary_group(
    runtime_client: Any,
) -> None:
    # 補助groupなしではsocketへ接続できず、実測GIDを付与した場合だけ同じ非root UIDで接続できる。
    script = """
import os
import socket
assert os.getuid() == 10001
with socket.socket(socket.AF_UNIX) as connection:
    try:
        connection.connect('/run/docker.sock')
    except PermissionError:
        print('denied')
    else:
        print('connected')
"""
    for groups, expected in (
        ([], b"denied"),
        ([_socket_gid(runtime_client)], b"connected"),
    ):
        output = runtime_client.containers.run(
            _image("runner"),
            ["python", "-c", script],
            group_add=groups,
            volumes=_socket_binding(),
            network_mode="none",
            remove=True,
            **_restrictions("runner"),
        )
        assert output.strip() == expected


def _wait_for_command(container: Any, command: list[str]) -> bytes:
    """一時serviceの起動を上限付きで待ち、成功した確認commandの出力を返す。"""
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        container.reload()
        assert container.status == "running", "temporary runtime exited during startup"
        result = container.exec_run(command)
        if result.exit_code == 0:
            return result.output
        time.sleep(0.2)
    pytest.fail("temporary runtime did not become ready")


def test_split_images_execute_judge_and_persist_through_private_networks(
    runtime_client: Any,
) -> None:
    # 本番targetと制限で起動し、内部通信・非root sandbox実行・text/image判定・DB保存を確認する。
    client = runtime_client
    owner = f"runtime-test-{uuid.uuid4().hex}"
    containers: list[Any] = []
    networks: list[Any] = []
    repository = build_problem_repository(
        ROOT / "problems/v3",
        ROOT / "problems/image",
        ROOT / "problems/v3/manifest.json",
    )
    secret = uuid.uuid4().hex + uuid.uuid4().hex

    def create_service(image: str, network: Any, alias: str, **kwargs: Any) -> Any:
        """test専用networkの固定aliasでcontainerを作成し、cleanup対象へ直ちに登録する。"""
        container = client.containers.create(
            image,
            name=f"{owner}-{alias}",
            network=network.name,
            networking_config={
                network.name: client.api.create_endpoint_config(aliases=[alias])
            },
            log_config=docker.types.LogConfig(
                type=COMPOSE["services"]["backend"]["logging"]["driver"],
                config=COMPOSE["services"]["backend"]["logging"]["options"],
            ),
            **kwargs,
        )
        containers.append(container)
        return container

    try:
        for suffix in ("runner", "db"):
            networks.append(client.networks.create(f"{owner}-{suffix}", internal=True))
        runner_network, db_network = networks
        db = create_service(
            database_image(),
            db_network,
            "db",
            environment={
                "POSTGRES_USER": "runtime_test",
                "POSTGRES_PASSWORD": secret,
                "POSTGRES_DB": "runtime_test",
            },
            tmpfs={"/var/lib/postgresql/data": "rw,size=128M"},
        )
        db.start()
        _wait_for_command(
            db, ["pg_isready", "-U", "runtime_test", "-d", "runtime_test"]
        )
        runner = create_service(
            _image("runner"),
            runner_network,
            "runner",
            command=COMPOSE["services"]["runner"]["command"],
            environment={
                "DOCKER_HOST": "unix:///run/docker.sock",
                "SANDBOX_OWNER_ID": owner,
                "RUNNER_SHARED_SECRET": secret,
            },
            volumes=_socket_binding(),
            group_add=[_socket_gid(client)],
            **_restrictions("runner"),
        )
        runner.start()
        _wait_for_command(
            runner,
            [
                "python",
                "-c",
                "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/internal/ready').read()",
            ],
        )
        backend = create_service(
            _image("backend"),
            runner_network,
            "backend",
            environment={
                "DATABASE_URL": f"postgresql://runtime_test:{secret}@db:5432/runtime_test",
                "RUNNER_SHARED_SECRET": secret,
            },
            **_restrictions("backend"),
        )
        db_network.connect(backend)
        backend.start()
        _wait_for_command(
            backend,
            [
                "python",
                "-c",
                "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api').read()",
            ],
        )
        for problem_id, command, verdict in (
            ("STANDARD-00000001", "echo test", "accepted"),
            ("STANDARD-00000001", "printf wrong", "wrong_answer"),
            (
                "IMAGE-00000001",
                repository.require("IMAGE-00000001").definition.reference_solution,
                "accepted",
            ),
        ):
            payload = json.dumps({"shellgei": command, "problem_id": problem_id})
            result = backend.exec_run(
                [
                    "python",
                    "-c",
                    "import sys, urllib.request; request = urllib.request.Request('http://127.0.0.1:8000/api/v3/submissions', data=sys.argv[1].encode(), headers={'Content-Type': 'application/json'}); print(urllib.request.urlopen(request, timeout=40).read().decode())",
                    payload,
                ]
            )
            assert result.exit_code == 0, result.output.decode()
            response = json.loads(result.output)
            assert response["verdict"] == verdict
            assert response["execution"]["status"] == "completed"
            assert response["persistence"] == "saved"
            assert response["submission_id"] > 0
            if problem_id.startswith("IMAGE"):
                assert response["artifact"]["media_type"] == "image/jpeg"
    finally:
        # 1件の停止・削除が失敗しても、残るtest専用資源のcleanupをすべて試みる。
        with ExitStack() as cleanup:
            for network in networks:
                cleanup.callback(network.remove)
            cleanup.callback(_remove_owned_sandboxes, client, owner)
            for container in containers:
                cleanup.callback(container.remove, force=True, v=True)
                cleanup.callback(container.stop, timeout=20)


def _remove_owned_sandboxes(client: Any, owner: str) -> None:
    """service停止後に当該test ownerのsandboxだけを回収し、他環境には触れない。"""
    with ExitStack() as cleanup:
        for sandbox in client.containers.list(
            all=True, filters={"label": f"{OWNER_LABEL}={owner}"}
        ):
            cleanup.callback(sandbox.remove, force=True, v=True)
