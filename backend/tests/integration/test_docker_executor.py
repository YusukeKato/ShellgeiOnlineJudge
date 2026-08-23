import asyncio
import os
import uuid
from pathlib import Path

import docker
import pytest
import yaml

from scripts.container_manager import (
    INSTANCE_LABEL,
    MANAGED_LABEL,
    OWNER_LABEL,
    SANDBOX_HOME_DIRECTORY,
    SANDBOX_TMPFS,
    SANDBOX_WORK_DIRECTORY,
    ContainerManager,
)
from scripts.run_shellgei import ShellgeiDockerClient


pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(
        os.getenv("SOJ_RUN_DOCKER_TESTS") != "1",
        reason="set SOJ_RUN_DOCKER_TESTS=1 on an isolated Docker test host",
    ),
]

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_runner_restart_reconciles_owned_sandbox_containers() -> None:
    owner_id = f"integration-{uuid.uuid4().hex}"
    old_manager = ContainerManager(pool_size=1, owner_id=owner_id)
    new_manager = ContainerManager(pool_size=1, owner_id=owner_id)
    old_manager.initialize_pool()
    old_container = old_manager.get_container()
    old_container_id = old_container.id
    try:
        new_manager.initialize_pool()

        assert new_manager.client is not None
        with pytest.raises(docker.errors.NotFound):
            new_manager.client.containers.get(old_container_id)

        replacement = new_manager.get_container()
        replacement.reload()
        labels = replacement.attrs["Config"]["Labels"]
        assert labels[MANAGED_LABEL] == "true"
        assert labels[OWNER_LABEL] == owner_id
        assert labels[INSTANCE_LABEL] == new_manager.instance_id
        new_manager.release_container(replacement)
    finally:
        new_manager.shutdown_pool()
        old_manager.shutdown_pool()


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
        container_config = container.attrs["Config"]

        assert host_config["ReadonlyRootfs"] is True
        assert host_config["NetworkMode"] == "none"
        assert host_config["IpcMode"] == "none"
        assert host_config["Memory"] == 512 * 1024 * 1024
        assert host_config["MemorySwap"] == 512 * 1024 * 1024
        assert host_config["NanoCpus"] == 500_000_000
        assert host_config["PidsLimit"] == 50
        assert host_config["CapDrop"] == ["ALL"]
        assert "no-new-privileges:true" in host_config["SecurityOpt"]
        assert host_config["LogConfig"] == {"Type": "none", "Config": {}}
        assert host_config["Tmpfs"] == SANDBOX_TMPFS
        assert {
            ulimit["Name"]: (ulimit["Soft"], ulimit["Hard"])
            for ulimit in host_config["Ulimits"]
        } == {
            "fsize": (50_000_000, 50_000_000),
            "nofile": (256, 256),
            "core": (0, 0),
        }
        assert container_config["WorkingDir"] == SANDBOX_WORK_DIRECTORY
        environment = dict(item.split("=", 1) for item in container_config["Env"])
        assert environment["HOME"] == SANDBOX_HOME_DIRECTORY
        assert environment["TMPDIR"] == "/tmp"

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

        filesystem_result = container.exec_run(
            [
                "/bin/sh",
                "-c",
                "set -eu; "
                "if /bin/sh -c ': > /rootfs-write-test' 2>/dev/null; then "
                "exit 50; fi; "
                ": > /work/work-test; "
                ": > /tmp/tmp-test; "
                ": > /media/media-test; "
                ": > /dev/dev-test; "
                'test "$(readlink /work/media)" = /media; '
                'test "$(readlink /work/ShellGeiData)" = /ShellGeiData; '
                'test "$PWD" = /work; '
                'test "$HOME" = /tmp/home; '
                'test "$(readlink /proc/1/fd/0)" = /dev/null; '
                'test "$(readlink /proc/1/fd/1)" = /dev/null; '
                'test "$(readlink /proc/1/fd/2)" = /dev/null; '
                'test "$(ulimit -n)" = 256; '
                'test "$(ulimit -c)" = 0',
            ],
            workdir=SANDBOX_WORK_DIRECTORY,
        )
        assert filesystem_result.exit_code == 0, filesystem_result.output.decode(
            "utf-8", errors="replace"
        )

        mount_limits_result = container.exec_run(
            [
                "/bin/sh",
                "-c",
                "for spec in /work:65536:4096 /tmp:32768:4096 "
                "/media:102400:1024 /dev:65536:1024; do "
                "path=${spec%%:*}; rest=${spec#*:}; expected_kib=${rest%%:*}; "
                "expected_inodes=${rest#*:}; "
                "actual_kib=$(df -kP \"$path\" | awk 'NR == 2 {print $2}'); "
                "actual_inodes=$(df -iP \"$path\" | awk 'NR == 2 {print $2}'); "
                'test "$actual_kib" = "$expected_kib"; '
                'test "$actual_inodes" = "$expected_inodes"; '
                "done",
            ]
        )
        assert mount_limits_result.exit_code == 0, mount_limits_result.output.decode(
            "utf-8", errors="replace"
        )
        manager.release_container(container)
    finally:
        manager.shutdown_pool()


def test_real_writable_area_rejects_capacity_and_inode_exhaustion() -> None:
    manager = ContainerManager(pool_size=1)
    manager.initialize_pool()
    try:
        container = manager.get_container()
        bounded_write_result = container.exec_run(
            [
                "/bin/sh",
                "-c",
                "set -eu; count=0; "
                'while test "$count" -le 4200; do '
                'if touch "/work/inode-$count" 2>/dev/null; then '
                "count=$((count + 1)); else break; fi; done; "
                'test "$count" -ge 4000; test "$count" -le 4096; '
                "rm -f /work/inode-*; "
                "dd if=/dev/zero of=/work/large-a bs=1M count=40 status=none; "
                "if dd if=/dev/zero of=/work/large-b bs=1M count=40 "
                "status=none 2>/dev/null; then exit 60; fi",
            ],
            workdir=SANDBOX_WORK_DIRECTORY,
        )
        assert bounded_write_result.exit_code == 0, bounded_write_result.output.decode(
            "utf-8", errors="replace"
        )

        manager.release_container(container)
        replacement = manager.get_container()
        clean_result = replacement.exec_run(
            [
                "/bin/sh",
                "-c",
                'set -eu; test "$(readlink /work/media)" = /media; '
                'test "$(readlink /work/ShellGeiData)" = /ShellGeiData; '
                'test -z "$(find /work -mindepth 1 -maxdepth 1 '
                '! -name media ! -name ShellGeiData -print -quit)"',
            ],
            workdir=SANDBOX_WORK_DIRECTORY,
        )
        assert clean_result.exit_code == 0, clean_result.output.decode(
            "utf-8", errors="replace"
        )
        manager.release_container(replacement)
    finally:
        manager.shutdown_pool()


def test_real_workdir_home_input_image_and_request_isolation() -> None:
    manager = ContainerManager(pool_size=1)
    client = ShellgeiDockerClient(container_manager=manager, max_concurrent=1)
    client.base_dir = REPOSITORY_ROOT
    manager.initialize_pool()
    try:
        input_data = yaml.safe_load(
            (REPOSITORY_ROOT / "problems/yaml_data/PRACTICE-awk-02.yaml").read_text(
                encoding="utf-8"
            )
        )["input"]
        with_input = asyncio.run(
            client.run_with_timeout(
                'set -eu; test "$PWD" = /work; test "$HOME" = /tmp/home; '
                'temporary=$(mktemp); printf temporary > "$temporary"; '
                'printf work > generated.txt; printf home > "$HOME/state"; '
                "cat input.txt",
                "PRACTICE-awk-02",
                timeout=5,
            )
        )
        isolated = asyncio.run(
            client.run_with_timeout(
                'test ! -e generated.txt; test ! -e "$HOME/state"; printf clean',
                "STANDARD-00000001",
                timeout=5,
            )
        )
        image_command = yaml.safe_load(
            (REPOSITORY_ROOT / "problems/yaml_data/IMAGE-00000001.yaml").read_text(
                encoding="utf-8"
            )
        )["answer"]
        image_result = asyncio.run(
            client.run_with_timeout(image_command, "IMAGE-00000001", timeout=5)
        )

        assert with_input[0] == input_data
        assert with_input[1]
        assert isolated[0] == "clean"
        assert image_result[1]
        assert manager.managed_count == 1
    finally:
        manager.shutdown_pool()
        client.close()


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
