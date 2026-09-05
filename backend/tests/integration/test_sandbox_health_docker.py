import os
import time
import uuid
from typing import Any

import docker
import pytest

from soj_runner.sandbox_identity import INSTANCE_LABEL, MANAGED_LABEL, OWNER_LABEL
from soj_tools.sandbox_health import inspect_health


pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(
        os.getenv("SOJ_RUN_DOCKER_TESTS") != "1"
        or os.getenv("SOJ_RUN_RUNTIME_IMAGE_TESTS") != "1",
        reason="enable Docker and runtime image tests with a local backend image",
    ),
]


def test_host_monitor_detects_owned_orphans_without_mutating_containers() -> None:
    # 専用の軽量containerだけで健全・停止・runner欠落を再現し、別ownerの除外と非変更を確認する。
    assert os.environ.get("DOCKER_HOST", "").startswith("unix://")
    client = docker.from_env(timeout=10)
    containers: list[Any] = []
    owner = f"soj-health-{uuid.uuid4().hex}"
    runner_name = f"{owner}-runner"
    image = os.environ["SOJ_BACKEND_RUNTIME_IMAGE"]
    try:
        assert "name=rootless" in client.info()["SecurityOptions"]
        client.images.get(image)
        options: dict[str, Any] = {
            "image": image,
            "command": ["python", "-c", "import time; time.sleep(120)"],
            "network_mode": "none",
            "read_only": True,
            "cap_drop": ["ALL"],
            "security_opt": ["no-new-privileges:true"],
            "mem_limit": "32m",
            "memswap_limit": "32m",
            "nano_cpus": 100000000,
            "pids_limit": 16,
            "log_config": docker.types.LogConfig(type="none"),
        }
        runner = client.containers.create(
            **options,
            name=runner_name,
            labels={"com.docker.compose.service": "runner"},
            environment={"SANDBOX_OWNER_ID": owner},
            healthcheck={
                "test": ["CMD", "python", "-c", "pass"],
                "interval": 1000000000,
                "timeout": 1000000000,
                "retries": 1,
            },
        )
        containers.append(runner)
        runner.start()
        for index in range(4):
            sandbox = client.containers.create(
                **options,
                name=f"{owner}-{index}",
                labels={
                    MANAGED_LABEL: "true",
                    OWNER_LABEL: owner if index < 3 else f"{owner}-other",
                    INSTANCE_LABEL: "test-instance",
                },
            )
            containers.append(sandbox)
            if index < 3:
                sandbox.start()
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            runner.reload()
            if runner.attrs["State"]["Health"]["Status"] == "healthy":
                break
            time.sleep(0.25)
        report = inspect_health(client, owner, runner_name)
        assert report["status"] == "ok"
        assert report["sandbox_count"] == 3
        for container in containers[:4]:
            container.reload()
            assert container.status == "running"
        # 再起動を持たないtest用runnerだけを停止する。実runnerやdaemonは停止しない。
        runner.stop(timeout=1)
        report = inspect_health(client, owner, runner_name)
        assert "sandboxes_without_running_runner" in report["issues"]
        assert report["sandbox_count"] == 3
        containers[1].stop(timeout=1)
        report = inspect_health(client, owner, runner_name)
        assert report["sandbox_not_running"] == 1
        runner.remove(v=True)
        report = inspect_health(client, owner, runner_name)
        assert report["runner_state"] == "missing"
        assert report["sandbox_count"] == 3
        # 監視が残存containerを削除していないことを、取得可能性とstateで確認する。
        for container in containers[1:]:
            container.reload()
        assert containers[2].status == containers[3].status == "running"
    finally:
        try:
            for container in reversed(containers):
                try:
                    container.remove(force=True, v=True)
                except docker.errors.NotFound:
                    pass
        finally:
            client.close()
