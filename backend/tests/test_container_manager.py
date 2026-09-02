import threading
import time
from typing import Any

import docker
import pytest

import scripts.container_manager as container_manager_module
from scripts.container_manager import (
    CgroupResourceLimitsRequiredError,
    ContainerCapacityError,
    ContainerManager,
    INSTANCE_LABEL,
    MANAGED_LABEL,
    OWNER_LABEL,
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
        self.name = container_id
        self.kill_calls = 0
        self.remove_calls = 0
        self.start_calls = 0
        self.kill_error: Exception | None = None
        self.remove_error: Exception | None = None
        self.start_error: Exception | None = None
        self.cgroup_exit_code = cgroup_exit_code
        self.cgroup_output = cgroup_output
        self.labels: dict[str, str] = {}
        self.removed = False
        self.remove_delay = 0.0
        self.active_remove_calls = 0
        self.max_active_remove_calls = 0
        self._remove_state_lock = threading.Lock()

    def exec_run(self, command: list[str]) -> FakeExecResult:
        assert command[:2] == ["/bin/sh", "-c"]
        return FakeExecResult(self.cgroup_exit_code, self.cgroup_output)

    def kill(self) -> None:
        self.kill_calls += 1
        if self.removed:
            raise docker.errors.NotFound("container already removed")
        if self.kill_error is not None:
            raise self.kill_error

    def start(self) -> None:
        self.start_calls += 1
        if self.start_error is not None:
            raise self.start_error

    def remove(self, force: bool = False) -> None:
        assert force is True
        with self._remove_state_lock:
            self.active_remove_calls += 1
            self.max_active_remove_calls = max(
                self.max_active_remove_calls,
                self.active_remove_calls,
            )
        try:
            self.remove_calls += 1
            if self.remove_delay:
                time.sleep(self.remove_delay)
            if self.removed:
                raise docker.errors.NotFound("container already removed")
            if self.remove_error is not None:
                raise self.remove_error
            self.removed = True
        finally:
            with self._remove_state_lock:
                self.active_remove_calls -= 1


class FakeContainers:
    def __init__(self) -> None:
        self.created: list[FakeContainer] = []
        self.create_kwargs: list[dict[str, Any]] = []
        self.create_error: Exception | None = None
        self.create_error_after_creation: Exception | None = None
        self.start_error: Exception | None = None
        self.created_remove_error: Exception | None = None
        self.external: list[FakeContainer] = []
        self.list_calls: list[dict[str, Any]] = []
        self.cgroup_exit_code = 0
        self.cgroup_output = (
            f"{SANDBOX_MEMORY_LIMIT_BYTES}\n{SANDBOX_PIDS_LIMIT}\n{SANDBOX_CPU_MAX}\n"
        ).encode("ascii")

    def create(self, image_id: str, **kwargs: Any) -> FakeContainer:
        if self.create_error is not None:
            raise self.create_error
        container = FakeContainer(
            f"container-{len(self.created)}",
            self.cgroup_exit_code,
            self.cgroup_output,
        )
        container.name = kwargs["name"]
        container.labels = kwargs["labels"]
        container.start_error = self.start_error
        container.remove_error = self.created_remove_error
        self.created.append(container)
        self.create_kwargs.append({"image_id": image_id, **kwargs})
        if self.create_error_after_creation is not None:
            raise self.create_error_after_creation
        return container

    def list(
        self,
        all: bool = False,
        filters: dict[str, list[str]] | None = None,
    ) -> list[FakeContainer]:
        self.list_calls.append({"all": all, "filters": filters})
        required_labels = set((filters or {}).get("label", []))
        containers = [*self.external, *self.created]
        return [
            container
            for container in containers
            if not container.removed
            and required_labels.issubset(
                {f"{key}={value}" for key, value in container.labels.items()}
            )
        ]

    def get(self, container_name: str) -> FakeContainer:
        for container in [*self.external, *self.created]:
            if container.name == container_name and not container.removed:
                return container
        raise docker.errors.NotFound("container not found")


class FakeImages:
    def __init__(self) -> None:
        self.pull_calls: list[str] = []

    def pull(self, image_id: str) -> None:
        self.pull_calls.append(image_id)


class FakeDockerClient:
    def __init__(
        self,
        rootless: bool = True,
        cgroup_version: str = "2",
        cgroup_driver: str = "systemd",
    ) -> None:
        self.containers = FakeContainers()
        self.images = FakeImages()
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
    assert manager.is_ready is False
    assert_capacity_error(manager)


def test_shutdown_removes_warm_containers_and_closes_client() -> None:
    client = FakeDockerClient()
    manager = ContainerManager(client=client, pool_size=2)
    manager.initialize_pool()

    manager.shutdown_pool()

    assert manager.managed_count == 0
    assert all(container.remove_calls == 1 for container in client.containers.created)
    assert client.closed is True
    for options in client.containers.create_kwargs:
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
        assert dict(options["log_config"]) == {"Type": "none", "Config": {}}
        assert options["pids_limit"] == 50
        assert options["tmpfs"] == SANDBOX_TMPFS
        assert [dict(ulimit) for ulimit in options["ulimits"]] == [
            {"Name": "fsize", "Soft": 50_000_000, "Hard": 50_000_000},
            {"Name": "nofile", "Soft": 256, "Hard": 256},
            {"Name": "core", "Soft": 0, "Hard": 0},
        ]
        assert options["labels"] == {
            MANAGED_LABEL: "true",
            OWNER_LABEL: "shellgei-online-judge",
            INSTANCE_LABEL: manager.instance_id,
        }
        assert options["name"].startswith("soj-sandbox-")
        assert SANDBOX_INIT_COMMAND.endswith(
            "exec sleep infinity </dev/null >/dev/null 2>&1"
        )


def test_pool_initialization_fails_closed_when_container_creation_fails() -> None:
    client = FakeDockerClient()
    client.containers.create_error = RuntimeError("daemon unavailable")
    manager = ContainerManager(client=client, pool_size=1)

    try:
        manager.initialize_pool()
    except RuntimeError as exc:
        assert str(exc) == "daemon unavailable"
    else:
        raise AssertionError("pool initialization unexpectedly succeeded")

    assert manager.managed_count == 0
    assert client.closed is True


def test_runtime_create_failure_keeps_uncertain_name_in_capacity() -> None:
    client = FakeDockerClient()
    manager = ContainerManager(client=client, pool_size=1)
    manager.initialize_pool()
    container = manager.get_container()
    client.containers.create_error = RuntimeError("daemon unavailable")

    manager.release_container(container)

    assert manager.managed_count == 1
    assert manager.is_ready is False
    assert_capacity_error(manager)
    manager.shutdown_pool()


def test_readiness_requires_initialized_complete_pool_and_stops_on_shutdown() -> None:
    # 未初期化とshutdown中は非ready、完全初期化後はlease中でもreadyとなることを確認する。
    client = FakeDockerClient()
    manager = ContainerManager(client=client, pool_size=1)

    assert manager.is_ready is False

    manager.initialize_pool()
    assert manager.is_ready is True

    manager.get_container()
    assert manager.is_ready is True

    manager.begin_shutdown()
    assert manager.is_ready is False
    manager.shutdown_pool()


def test_fresh_manager_recovers_readiness_after_degraded_replenishment() -> None:
    # 補充失敗で劣化したmanagerは非readyを維持し、新規managerの再初期化で復帰する。
    failed_client = FakeDockerClient()
    failed_manager = ContainerManager(client=failed_client, pool_size=1)
    failed_manager.initialize_pool()
    container = failed_manager.get_container()
    failed_client.containers.create_error = RuntimeError("daemon unavailable")

    failed_manager.release_container(container)

    assert failed_manager.is_ready is False
    failed_manager.shutdown_pool()

    restarted_client = FakeDockerClient()
    restarted_manager = ContainerManager(client=restarted_client, pool_size=1)
    restarted_manager.initialize_pool()

    assert restarted_manager.is_ready is True
    restarted_manager.shutdown_pool()


@pytest.mark.parametrize("owner_id", ["", "contains space", "../other"])
def test_owner_id_rejects_unsafe_label_values(owner_id: str) -> None:
    with pytest.raises(ValueError, match="owner_id"):
        ContainerManager(owner_id=owner_id)


def test_pool_initialization_removes_only_stale_containers_for_owner() -> None:
    client = FakeDockerClient()
    stale_owned = FakeContainer("stale-owned", 0, b"")
    stale_owned.labels = {
        MANAGED_LABEL: "true",
        OWNER_LABEL: "deployment-a",
        INSTANCE_LABEL: "old-instance",
    }
    other_owner = FakeContainer("other-owner", 0, b"")
    other_owner.labels = {
        MANAGED_LABEL: "true",
        OWNER_LABEL: "deployment-b",
        INSTANCE_LABEL: "other-instance",
    }
    client.containers.external.extend([stale_owned, other_owner])
    manager = ContainerManager(
        client=client,
        pool_size=1,
        owner_id="deployment-a",
        instance_id="new-instance",
    )

    manager.initialize_pool()

    assert stale_owned.removed is True
    assert other_owner.removed is False
    assert client.containers.list_calls == [
        {
            "all": True,
            "filters": {
                "label": [
                    f"{MANAGED_LABEL}=true",
                    f"{OWNER_LABEL}=deployment-a",
                ]
            },
        }
    ]
    assert manager.managed_count == 1
    manager.shutdown_pool()


def test_pool_initialization_fails_when_stale_cleanup_fails() -> None:
    client = FakeDockerClient()
    stale = FakeContainer("stale", 0, b"")
    stale.labels = {
        MANAGED_LABEL: "true",
        OWNER_LABEL: "deployment-a",
    }
    stale.remove_error = RuntimeError("daemon unavailable")
    client.containers.external.append(stale)
    manager = ContainerManager(
        client=client,
        pool_size=1,
        owner_id="deployment-a",
    )

    with pytest.raises(RuntimeError, match="failed to remove stale sandbox"):
        manager.initialize_pool()

    assert client.containers.created == []
    assert client.closed is True


def test_start_failure_removes_registered_container() -> None:
    client = FakeDockerClient()
    client.containers.start_error = RuntimeError("start failed")
    manager = ContainerManager(client=client, pool_size=1)

    with pytest.raises(RuntimeError, match="start failed"):
        manager.initialize_pool()

    assert len(client.containers.created) == 1
    container = client.containers.created[0]
    assert container.start_calls == 1
    assert container.remove_calls == 1
    assert manager.managed_count == 0
    assert client.closed is True


def test_ambiguous_create_failure_recovers_container_by_name() -> None:
    client = FakeDockerClient()
    client.containers.create_error_after_creation = RuntimeError("create response lost")
    manager = ContainerManager(client=client, pool_size=1)

    with pytest.raises(RuntimeError, match="create response lost"):
        manager.initialize_pool()

    assert len(client.containers.created) == 1
    assert client.containers.created[0].remove_calls == 1
    assert manager.managed_count == 0
    assert client.closed is True


def test_unresolved_ambiguous_create_failure_keeps_capacity_reserved() -> None:
    client = FakeDockerClient()
    client.containers.create_error_after_creation = RuntimeError("create response lost")
    client.containers.created_remove_error = RuntimeError("remove failed")
    manager = ContainerManager(client=client, pool_size=1)

    with pytest.raises(RuntimeError, match="create response lost"):
        manager.initialize_pool()

    assert len(client.containers.created) == 1
    assert client.containers.created[0].remove_calls == 2
    assert manager.managed_count == 1
    assert client.closed is True


def test_release_and_shutdown_serialize_container_cleanup() -> None:
    client = FakeDockerClient()
    manager = ContainerManager(client=client, pool_size=1)
    manager.initialize_pool()
    container = manager.get_container()
    container.remove_delay = 0.05
    errors: list[Exception] = []

    def release() -> None:
        try:
            manager.release_container(container)
        except Exception as exc:
            errors.append(exc)

    def shutdown() -> None:
        try:
            manager.shutdown_pool()
        except Exception as exc:
            errors.append(exc)

    release_thread = threading.Thread(target=release)
    shutdown_thread = threading.Thread(target=shutdown)
    release_thread.start()
    time.sleep(0.01)
    shutdown_thread.start()
    release_thread.join(timeout=1)
    shutdown_thread.join(timeout=1)

    assert errors == []
    assert release_thread.is_alive() is False
    assert shutdown_thread.is_alive() is False
    assert container.max_active_remove_calls == 1
    assert manager.managed_count == 0
