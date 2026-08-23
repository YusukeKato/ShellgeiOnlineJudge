from typing import Any

import pytest

import scripts.container_manager as container_manager_module
from scripts.container_manager import (
    ContainerCapacityError,
    ContainerManager,
    RootlessDockerRequiredError,
)


class FakeContainer:
    def __init__(self, container_id: str) -> None:
        self.id = container_id
        self.kill_calls = 0
        self.remove_calls = 0
        self.kill_error: Exception | None = None
        self.remove_error: Exception | None = None

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

    def run(self, image_id: str, **kwargs: Any) -> FakeContainer:
        if self.run_error is not None:
            raise self.run_error
        container = FakeContainer(f"container-{len(self.created)}")
        self.created.append(container)
        self.run_kwargs.append({"image_id": image_id, **kwargs})
        return container


class FakeDockerClient:
    def __init__(self, rootless: bool = True) -> None:
        self.containers = FakeContainers()
        self.closed = False
        self.rootless = rootless
        self.info_calls = 0

    def info(self) -> dict[str, list[str]]:
        self.info_calls += 1
        security_options = ["name=seccomp,profile=builtin"]
        if self.rootless:
            security_options.append("name=rootless")
        return {"SecurityOptions": security_options}

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
        assert options["network_mode"] == "none"
        assert options["ipc_mode"] == "none"
        assert options["mem_limit"] == "512m"
        assert options["memswap_limit"] == "512m"
        assert options["nano_cpus"] == 500_000_000
        assert options["cap_drop"] == ["ALL"]
        assert options["security_opt"] == ["no-new-privileges:true"]
        assert options["pids_limit"] == 50
        assert options["tmpfs"] == {"/media": "size=100M"}
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
