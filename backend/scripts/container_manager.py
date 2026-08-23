import logging
import threading
from collections import deque
from typing import Any

import docker


logger = logging.getLogger(__name__)

DEFAULT_IMAGE_ID = "theoldmoon0602/shellgeibot"
DEFAULT_POOL_SIZE = 3
DOCKER_API_TIMEOUT_SECONDS = 15
MANAGED_LABEL = "com.shellgei-online-judge.sandbox"
SANDBOX_WORK_DIRECTORY = "/work"
SANDBOX_HOME_DIRECTORY = "/tmp/home"
SANDBOX_MEMORY_LIMIT_BYTES = 512 * 1024 * 1024
SANDBOX_CPU_MAX = "50000 100000"
SANDBOX_PIDS_LIMIT = 50
SANDBOX_INIT_COMMAND = (
    f"umask 077; mkdir -p {SANDBOX_HOME_DIRECTORY}; "
    f"ln -s /media {SANDBOX_WORK_DIRECTORY}/media; "
    f"ln -s /ShellGeiData {SANDBOX_WORK_DIRECTORY}/ShellGeiData; "
    "exec sleep infinity </dev/null >/dev/null 2>&1"
)
SANDBOX_TMPFS = {
    "/work": "rw,exec,nosuid,nodev,size=64M,nr_inodes=4096,mode=0700",
    "/tmp": "rw,exec,nosuid,nodev,size=32M,nr_inodes=4096,mode=1777",
    "/media": "rw,noexec,nosuid,nodev,size=100M,nr_inodes=1024,mode=0755",
    "/dev": "rw,noexec,nosuid,nodev,size=64M,nr_inodes=1024,mode=0755",
}


class ContainerCapacityError(RuntimeError):
    """Raised when the manager cannot create another managed container."""


class RootlessDockerRequiredError(RuntimeError):
    """Raised when the configured Docker daemon is not running rootless."""


class CgroupResourceLimitsRequiredError(RuntimeError):
    """Raised when required cgroup resource limits cannot be enforced."""


class ContainerManager:
    def __init__(
        self,
        client: Any | None = None,
        image_id: str = DEFAULT_IMAGE_ID,
        pool_size: int = DEFAULT_POOL_SIZE,
    ) -> None:
        if pool_size < 1:
            raise ValueError("pool_size must be at least 1")
        # Defer connecting to Docker until startup initializes the pool. This keeps
        # imports and non-Docker tests independent from daemon availability.
        self.client = client
        self.image_id = image_id
        self.pool: deque[Any] = deque()
        self.lock = threading.Lock()
        self.pool_size = pool_size
        self._slots = threading.BoundedSemaphore(pool_size)
        self._managed: dict[str, Any] = {}
        self._shutting_down = False

    def _get_client(self) -> Any:
        with self.lock:
            if self._shutting_down:
                raise RuntimeError("container manager is shutting down")
            if self.client is None:
                client = docker.from_env(
                    timeout=DOCKER_API_TIMEOUT_SECONDS,
                )
                try:
                    daemon_info = client.info()
                    security_options = daemon_info.get("SecurityOptions", [])
                    if "name=rootless" not in security_options:
                        raise RootlessDockerRequiredError(
                            "the sandbox Docker daemon must run in rootless mode"
                        )
                    if (
                        str(daemon_info.get("CgroupVersion")) != "2"
                        or daemon_info.get("CgroupDriver") != "systemd"
                    ):
                        raise CgroupResourceLimitsRequiredError(
                            "the sandbox Docker daemon must use cgroup v2 "
                            "with the systemd driver"
                        )
                except Exception:
                    client.close()
                    raise
                self.client = client
            return self.client

    def _container_options(self) -> dict[str, Any]:
        return {
            "detach": True,
            "command": ["/bin/sh", "-c", SANDBOX_INIT_COMMAND],
            "read_only": True,
            "working_dir": SANDBOX_WORK_DIRECTORY,
            "environment": {
                "HOME": SANDBOX_HOME_DIRECTORY,
                "TMPDIR": "/tmp",
            },
            "ipc_mode": "none",
            "network_mode": "none",
            "mem_limit": "512m",
            "memswap_limit": "512m",
            "nano_cpus": 500000000,
            "pids_limit": SANDBOX_PIDS_LIMIT,
            "cap_drop": ["ALL"],
            "security_opt": ["no-new-privileges:true"],
            "log_config": docker.types.LogConfig(type="none"),
            "tmpfs": dict(SANDBOX_TMPFS),
            "ulimits": [
                docker.types.Ulimit(name="fsize", soft=50000000, hard=50000000),
                docker.types.Ulimit(name="nofile", soft=256, hard=256),
                docker.types.Ulimit(name="core", soft=0, hard=0),
            ],
            "labels": {MANAGED_LABEL: "true"},
        }

    @staticmethod
    def _container_id(container: Any) -> str:
        return str(container.id)

    @staticmethod
    def _validate_container_resource_limits(container: Any) -> None:
        result = container.exec_run(
            [
                "/bin/sh",
                "-c",
                "cat /sys/fs/cgroup/memory.max; "
                "cat /sys/fs/cgroup/pids.max; "
                "cat /sys/fs/cgroup/cpu.max",
            ]
        )
        output = result.output.decode("ascii", errors="replace").splitlines()
        expected = [
            str(SANDBOX_MEMORY_LIMIT_BYTES),
            str(SANDBOX_PIDS_LIMIT),
            SANDBOX_CPU_MAX,
        ]
        if result.exit_code != 0 or output != expected:
            raise CgroupResourceLimitsRequiredError(
                "sandbox cgroup limits are not enforced: "
                f"exit_code={result.exit_code}, values={output!r}"
            )

    def _create_container(self) -> Any:
        with self.lock:
            if self._shutting_down:
                raise RuntimeError("container manager is shutting down")
        if not self._slots.acquire(blocking=False):
            raise ContainerCapacityError("managed container capacity reached")

        try:
            container = self._get_client().containers.run(
                self.image_id,
                **self._container_options(),
            )
        except Exception:
            self._slots.release()
            raise

        with self.lock:
            self._managed[self._container_id(container)] = container
            shutting_down = self._shutting_down
        if shutting_down:
            self._cleanup_container(container)
            raise RuntimeError("container manager is shutting down")
        try:
            self._validate_container_resource_limits(container)
        except Exception:
            self._cleanup_container(container)
            raise
        return container

    def _create_and_add(self) -> Any:
        container = self._create_container()
        with self.lock:
            if not self._shutting_down:
                self.pool.append(container)
                return container
        self._cleanup_container(container)
        raise RuntimeError("container manager is shutting down")

    def initialize_pool(self) -> None:
        """Synchronously create the complete warm pool or fail startup."""
        logger.info("Initializing container pool (%s)", self.pool_size)
        try:
            for _ in range(self.pool_size):
                self._create_and_add()
        except Exception:
            self.shutdown_pool()
            raise
        logger.info("Container pool ready")

    def get_container(self) -> Any:
        """Lease one container without ever exceeding the hard capacity."""
        with self.lock:
            if self._shutting_down:
                raise RuntimeError("container manager is shutting down")
            if self.pool:
                return self.pool.popleft()
        return self._create_container()

    def _forget_removed_container(self, container: Any) -> None:
        with self.lock:
            removed = self._managed.pop(self._container_id(container), None)
        if removed is not None:
            self._slots.release()

    def _cleanup_container(self, container: Any, kill: bool = True) -> bool:
        if kill:
            try:
                container.kill()
            except Exception as exc:
                # force=True can still remove a container after kill fails.
                logger.warning(
                    "Failed to kill sandbox container %s: %s", container.id, exc
                )

        try:
            container.remove(force=True)
        except docker.errors.NotFound:
            self._forget_removed_container(container)
            return True
        except Exception as exc:
            logger.error("Failed to remove sandbox container %s: %s", container.id, exc)
            return False

        self._forget_removed_container(container)
        return True

    def release_container(self, container: Any, already_stopped: bool = False) -> None:
        """Synchronously destroy a used container and replenish within capacity."""
        removed = self._cleanup_container(container, kill=not already_stopped)
        with self.lock:
            should_replenish = removed and not self._shutting_down
        if not should_replenish:
            return
        try:
            self._create_and_add()
        except Exception as exc:
            logger.error("Failed to replenish sandbox container: %s", exc)

    def shutdown_pool(self) -> None:
        """Stop accepting work and remove every container owned by this manager."""
        with self.lock:
            self._shutting_down = True
            containers = list(self._managed.values())
            self.pool.clear()
            client = self.client
        for container in containers:
            self._cleanup_container(container)
        close = getattr(client, "close", None)
        if close is not None:
            close()

    @property
    def managed_count(self) -> int:
        with self.lock:
            return len(self._managed)


manager = ContainerManager()
