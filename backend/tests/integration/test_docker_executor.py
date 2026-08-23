import asyncio
import os
from pathlib import Path

import pytest

from scripts.container_manager import ContainerManager
from scripts.run_shellgei import ShellgeiDockerClient


pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(
        os.getenv("SOJ_RUN_DOCKER_TESTS") != "1",
        reason="set SOJ_RUN_DOCKER_TESTS=1 on an isolated Docker test host",
    ),
]

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_real_container_has_required_baseline_isolation() -> None:
    manager = ContainerManager(pool_size=1)
    manager.initialize_pool()
    try:
        assert manager.client is not None
        daemon_info = manager.client.info()
        assert "name=rootless" in daemon_info["SecurityOptions"]
        assert daemon_info["CgroupVersion"] == "2"
        assert daemon_info["CgroupDriver"] == "systemd"

        container = manager.get_container()
        container.reload()
        host_config = container.attrs["HostConfig"]

        assert host_config["NetworkMode"] == "none"
        assert host_config["IpcMode"] == "none"
        assert host_config["Memory"] == 512 * 1024 * 1024
        assert host_config["MemorySwap"] == 512 * 1024 * 1024
        assert host_config["NanoCpus"] == 500_000_000
        assert host_config["PidsLimit"] == 50
        assert host_config["CapDrop"] == ["ALL"]
        assert "no-new-privileges:true" in host_config["SecurityOpt"]

        cgroup_result = container.exec_run(
            [
                "/bin/sh",
                "-c",
                "cat /sys/fs/cgroup/memory.max; "
                "cat /sys/fs/cgroup/pids.max; "
                "cat /sys/fs/cgroup/cpu.max",
            ]
        )
        assert cgroup_result.exit_code == 0
        assert cgroup_result.output.decode("ascii").splitlines() == [
            str(512 * 1024 * 1024),
            "50",
            "50000 100000",
        ]
        manager.release_container(container)
    finally:
        manager.shutdown_pool()


def test_real_silent_timeout_cleans_up_and_worker_recovers() -> None:
    manager = ContainerManager(pool_size=1)
    client = ShellgeiDockerClient(container_manager=manager, max_concurrent=1)
    client.base_dir = REPOSITORY_ROOT
    manager.initialize_pool()
    try:
        timed_out = asyncio.run(
            client.run_with_timeout(
                "while :; do :; done",
                "STANDARD-00000001",
                timeout=0.5,
            )
        )
        recovered = asyncio.run(
            client.run_with_timeout(
                "printf recovered",
                "STANDARD-00000001",
                timeout=5,
            )
        )

        assert timed_out == ["\n[Timed out]", ""]
        assert recovered[0] == "recovered"
        assert recovered[1]
        assert manager.managed_count == 1
    finally:
        manager.shutdown_pool()
        client.close()
