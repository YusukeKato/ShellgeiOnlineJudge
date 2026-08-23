from typing import Any

import pytest

import scripts.container_manager as container_manager_module
from scripts.container_manager import (
    CgroupResourceLimitsRequiredError,
    ContainerCapacityError,
    ContainerManager,
    RootlessDockerRequiredError,
    SANDBOX_CPU_MAX,
    SANDBOX_HOME_DIRECTORY,
    SANDBOX_INIT_COMMAND,
    SANDBOX_MEMORY_LIMIT_BYTES,
    SANDBOX_PIDS_LIMIT,
    SANDBOX_TMPFS,
    SANDBOX_WORK_DIRECTORY,
)


class FakeExecResult:
    def __init__(self, exit_code: int, output: bytes) -> None:
        self.exit_code = exit_code
        self.output = output


class FakeContainer:
    def __init__(
        self,
        container_id: str,
        cgroup_exit_code: int,
        cgroup_output: bytes,
    ) -> None:
        self.id = container_id
        self.kill_calls = 0
        self.remove_calls = 0
        self.kill_error: Exception | None = None
        self.remove_error: Exception | None = None
        self.cgroup_exit_code = cgroup_exit_code
        self.cgroup_output = cgroup_output

    def exec_run(self, command: list[str]) -> FakeExecResult:
        assert command[:2] == ["/bin/sh", "-c"]
        return FakeExecResult(self.cgroup_exit_code, self.cgroup_output)

    def kill(self) -> None:
        self.kill_calls += 1
        if self.kill_error is not None:
            raise self.kill_error

    def remove(self, force: bool = False) -> None:
        assert force is True
        self.remove_calls += 1
        if self.remove_error is not None:
            raise self.remove_error


class FakeContainers:
    def __init__(self) -> None:
        self.created: list[FakeContainer] = []
        self.run_kwargs: list[dict[str, Any]] = []
        self.run_error: Exception | None = None
        self.cgroup_exit_code = 0
        self.cgroup_output = (
            f"{SANDBOX_MEMORY_LIMIT_BYTES}\n{SANDBOX_PIDS_LIMIT}\n{SANDBOX_CPU_MAX}\n"
        ).encode("ascii")

    def run(self, image_id: str, **kwargs: Any) -> FakeContainer:
        if self.run_error is not None:
            raise self.run_error
        container = FakeContainer(
            f"container-{len(self.created)}",
            self.cgroup_exit_code,
            self.cgroup_output,
        )
        self.created.append(container)
        self.run_kwargs.append({"image_id": image_id, **kwargs})
        return container


class FakeDockerClient:
    def __init__(
        self,
        rootless: bool = True,
        cgroup_version: str = "2",
        cgroup_driver: str = "systemd",
    ) -> None:
        self.containers = FakeContainers()
        self.closed = False
        self.rootless = rootless
        self.cgroup_version = cgroup_version
        self.cgroup_driver = cgroup_driver
        self.info_calls = 0

    def info(self) -> dict[str, Any]:
        self.info_calls += 1
        security_options = ["name=seccomp,profile=builtin"]
        if self.rootless:
            security_options.append("name=rootless")
        return {
            "SecurityOptions": security_options,
            "CgroupVersion": self.cgroup_version,
            "CgroupDriver": self.cgroup_driver,
        }

    def close(self) -> None:
        self.closed = True


def assert_capacity_error(manager: ContainerManager) -> None:
    try:
        manager.get_container()
    except ContainerCapacityError:
        return
    raise AssertionError("ContainerCapacityError was not raised")


def test_default_docker_client_is_created_lazily(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeDockerClient()
    calls: list[dict[str, Any]] = []

    def fake_from_env(**kwargs: Any) -> FakeDockerClient:
        calls.append(kwargs)
        return client

    monkeypatch.setattr(container_manager_module.docker, "from_env", fake_from_env)
    manager = ContainerManager(pool_size=1)

    assert calls == []

    manager.initialize_pool()

    assert calls == [{"timeout": 15}]
    assert client.info_calls == 1
    manager.shutdown_pool()


def test_default_docker_client_rejects_rootful_daemon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeDockerClient(rootless=False)
    monkeypatch.setattr(
        container_manager_module.docker,
        "from_env",
        lambda **kwargs: client,
    )
    manager = ContainerManager(pool_size=1)

    with pytest.raises(RootlessDockerRequiredError):
        manager.initialize_pool()

    assert client.closed is True
    assert client.containers.created == []


@pytest.mark.parametrize(
    ("cgroup_version", "cgroup_driver"),
    [("1", "systemd"), ("2", "cgroupfs")],
)
def test_default_docker_client_rejects_unsupported_cgroup_configuration(
    monkeypatch: pytest.MonkeyPatch,
    cgroup_version: str,
    cgroup_driver: str,
) -> None:
    client = FakeDockerClient(
        cgroup_version=cgroup_version,
        cgroup_driver=cgroup_driver,
    )
    monkeypatch.setattr(
        container_manager_module.docker,
        "from_env",
        lambda **kwargs: client,
    )
    manager = ContainerManager(pool_size=1)

    with pytest.raises(CgroupResourceLimitsRequiredError):
        manager.initialize_pool()

    assert client.closed is True
    assert client.containers.created == []


def test_pool_initialization_rejects_unenforced_container_limits() -> None:
    client = FakeDockerClient()
    client.containers.cgroup_output = b"max\nmax\nmax 100000\n"
    manager = ContainerManager(client=client, pool_size=1)

    with pytest.raises(CgroupResourceLimitsRequiredError):
        manager.initialize_pool()

    assert manager.managed_count == 0
    assert len(client.containers.created) == 1
    container = client.containers.created[0]
    assert container.kill_calls == 1
    assert container.remove_calls == 1
    assert client.closed is True


def test_manager_never_creates_more_than_hard_capacity() -> None:
    client = FakeDockerClient()
    manager = ContainerManager(client=client, image_id="test-image", pool_size=2)
    manager.initialize_pool()

    first = manager.get_container()
    second = manager.get_container()
    assert_capacity_error(manager)
    assert manager.managed_count == 2

    manager.release_container(first)

    assert first.remove_calls == 1
    assert len(client.containers.created) == 3
    assert manager.managed_count == 2
    assert manager.get_container() is client.containers.created[-1]
    assert_capacity_error(manager)

    manager.release_container(second)
    manager.shutdown_pool()


def test_remove_is_attempted_when_kill_fails() -> None:
    client = FakeDockerClient()
    manager = ContainerManager(client=client, pool_size=1)
    manager.initialize_pool()
    container = manager.get_container()
    container.kill_error = RuntimeError("kill failed")

    manager.release_container(container)

    assert container.kill_calls == 1
    assert container.remove_calls == 1
    assert manager.managed_count == 1
    manager.shutdown_pool()


def test_cleanup_failure_does_not_create_replacement_container() -> None:
    client = FakeDockerClient()
    manager = ContainerManager(client=client, pool_size=1)
    manager.initialize_pool()
    container = manager.get_container()
    container.remove_error = RuntimeError("remove failed")

    manager.release_container(container)

    assert len(client.containers.created) == 1
    assert manager.managed_count == 1
    assert_capacity_error(manager)


def test_shutdown_removes_warm_containers_and_closes_client() -> None:
    client = FakeDockerClient()
    manager = ContainerManager(client=client, pool_size=2)
    manager.initialize_pool()

    manager.shutdown_pool()

    assert manager.managed_count == 0
    assert all(container.remove_calls == 1 for container in client.containers.created)
    assert client.closed is True
    for options in client.containers.run_kwargs:
        assert options["command"] == ["/bin/sh", "-c", SANDBOX_INIT_COMMAND]
        assert options["read_only"] is True
        assert options["working_dir"] == SANDBOX_WORK_DIRECTORY
        assert options["environment"] == {
            "HOME": SANDBOX_HOME_DIRECTORY,
            "TMPDIR": "/tmp",
        }
        assert options["network_mode"] == "none"
        assert options["ipc_mode"] == "none"
        assert options["mem_limit"] == "512m"
        assert options["memswap_limit"] == "512m"
        assert options["nano_cpus"] == 500_000_000
        assert options["cap_drop"] == ["ALL"]
        assert options["security_opt"] == ["no-new-privileges:true"]
        assert options["pids_limit"] == 50
        assert options["tmpfs"] == SANDBOX_TMPFS
        assert [dict(ulimit) for ulimit in options["ulimits"]] == [
            {"Name": "fsize", "Soft": 50_000_000, "Hard": 50_000_000},
            {"Name": "nofile", "Soft": 256, "Hard": 256},
            {"Name": "core", "Soft": 0, "Hard": 0},
        ]
        assert options["labels"] == {"com.shellgei-online-judge.sandbox": "true"}


def test_pool_initialization_fails_closed_when_container_creation_fails() -> None:
    client = FakeDockerClient()
    client.containers.run_error = RuntimeError("daemon unavailable")
    manager = ContainerManager(client=client, pool_size=1)

    try:
        manager.initialize_pool()
    except RuntimeError as exc:
        assert str(exc) == "daemon unavailable"
    else:
        raise AssertionError("pool initialization unexpectedly succeeded")

    assert manager.managed_count == 0
    assert client.closed is True
