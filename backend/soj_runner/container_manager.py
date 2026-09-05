import logging
import os
import re
import threading
import uuid
from collections import deque
from typing import Any

import docker


logger = logging.getLogger(__name__)

DEFAULT_IMAGE_ID = (
    "theoldmoon0602/shellgeibot:latest@"
    "sha256:aaaa5b10e6419e4309a0b53a8d9e48ddcadabb92cc1dc7e1a739bc0248741a36"
)
DEFAULT_POOL_SIZE = 3
DOCKER_API_TIMEOUT_SECONDS = 15
MANAGED_LABEL = "com.shellgei-online-judge.sandbox"
OWNER_LABEL = "com.shellgei-online-judge.owner"
INSTANCE_LABEL = "com.shellgei-online-judge.runner-instance"
DEFAULT_SANDBOX_OWNER_ID = "shellgei-online-judge"
SANDBOX_OWNER_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,62}")
PINNED_IMAGE_PATTERN = re.compile(r"[^@\s]+@sha256:[0-9a-f]{64}")
SANDBOX_CONTAINER_NAME_PREFIX = "soj-sandbox"
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


class SandboxImageConfigurationError(RuntimeError):
    """Raised when the sandbox image declares an unsafe filesystem volume."""


class SandboxMountConfigurationError(RuntimeError):
    """Raised when Docker creates an unexpected sandbox mount."""


class ContainerManager:
    def __init__(
        self,
        client: Any | None = None,
        image_id: str = DEFAULT_IMAGE_ID,
        pool_size: int = DEFAULT_POOL_SIZE,
        owner_id: str = DEFAULT_SANDBOX_OWNER_ID,
        instance_id: str | None = None,
    ) -> None:
        if pool_size < 1:
            raise ValueError("pool_size must be at least 1")
        if PINNED_IMAGE_PATTERN.fullmatch(image_id) is None:
            raise ValueError("image_id must include a sha256 digest")
        if SANDBOX_OWNER_ID_PATTERN.fullmatch(owner_id) is None:
            raise ValueError("owner_id must contain only safe label characters")
        # Defer connecting to Docker until startup initializes the pool. This keeps
        # imports and non-Docker tests independent from daemon availability.
        self.client = client
        self.image_id = image_id
        self.owner_id = owner_id
        self.instance_id = instance_id or uuid.uuid4().hex
        self.pool: deque[Any] = deque()
        self.lock = threading.Lock()
        self._create_shutdown_lock = threading.Lock()
        self._cleanup_lock = threading.Lock()
        self.pool_size = pool_size
        self._slots = threading.BoundedSemaphore(pool_size)
        self._managed: dict[str, Any] = {}
        self._pending_names: set[str] = set()
        self._shutting_down = False
        self._initialized = False
        self._degraded = False
        self._image_validated = False

    def _mark_degraded(self) -> None:
        """shutdown中でなければpoolを再起動が必要な劣化状態として記録する。"""
        with self.lock:
            if not self._shutting_down:
                self._degraded = True

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
            "labels": {
                MANAGED_LABEL: "true",
                OWNER_LABEL: self.owner_id,
                INSTANCE_LABEL: self.instance_id,
            },
        }

    @staticmethod
    def _validate_sandbox_image(image: Any) -> None:
        """入力imageをinspectし、永続・匿名volumeを生成するVOLUME宣言がなければ返す。"""
        config = image.attrs.get("Config")
        if not isinstance(config, dict):
            raise SandboxImageConfigurationError(
                "sandbox image configuration is unavailable"
            )
        if config.get("Volumes") not in (None, {}):
            raise SandboxImageConfigurationError(
                "sandbox image must not declare filesystem volumes"
            )

    def _ensure_sandbox_image(self, client: Any) -> None:
        """固定digestのimageを取得またはpullし、安全なmetadataを一度だけ検証する。"""
        if self._image_validated:
            return
        try:
            image = client.images.get(self.image_id)
        except docker.errors.ImageNotFound:
            image = client.images.pull(self.image_id)
        self._validate_sandbox_image(image)
        self._image_validated = True

    @staticmethod
    def _validate_container_mounts(container: Any) -> None:
        """作成済みcontainerをinspectし、許可していないbind・volume・mountを拒否する。"""
        container.reload()
        attributes = container.attrs
        host_config = attributes.get("HostConfig")
        container_config = attributes.get("Config")
        if not isinstance(host_config, dict) or not isinstance(container_config, dict):
            raise SandboxMountConfigurationError(
                "sandbox container configuration is unavailable"
            )
        if (
            attributes.get("Mounts")
            or host_config.get("Binds")
            or host_config.get("Mounts")
            or host_config.get("VolumesFrom")
            or container_config.get("Volumes")
        ):
            raise SandboxMountConfigurationError(
                "sandbox container has an unexpected mount or volume"
            )
        if host_config.get("Tmpfs") != SANDBOX_TMPFS:
            raise SandboxMountConfigurationError(
                "sandbox container tmpfs configuration does not match the allowlist"
            )

    def _owned_container_filters(self) -> dict[str, list[str]]:
        return {
            "label": [
                f"{MANAGED_LABEL}=true",
                f"{OWNER_LABEL}={self.owner_id}",
            ]
        }

    def _reconcile_stale_containers(self) -> None:
        client = self._get_client()
        try:
            stale_containers = client.containers.list(
                all=True,
                filters=self._owned_container_filters(),
            )
        except Exception as exc:
            raise RuntimeError("failed to list stale sandbox containers") from exc

        for container in stale_containers:
            try:
                with self._cleanup_lock:
                    container.remove(force=True, v=True)
            except docker.errors.NotFound:
                continue
            except Exception as exc:
                raise RuntimeError(
                    f"failed to remove stale sandbox container {container.id}"
                ) from exc

    def _new_container_name(self) -> str:
        return f"{SANDBOX_CONTAINER_NAME_PREFIX}-{uuid.uuid4().hex}"

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
        with self._create_shutdown_lock:
            with self.lock:
                if self._shutting_down:
                    raise RuntimeError("container manager is shutting down")
            client = self._get_client()
            self._ensure_sandbox_image(client)
            if not self._slots.acquire(blocking=False):
                raise ContainerCapacityError("managed container capacity reached")

            container_name = self._new_container_name()
            with self.lock:
                self._pending_names.add(container_name)

            try:
                container = client.containers.create(
                    self.image_id,
                    name=container_name,
                    **self._container_options(),
                )
                self._validate_container_mounts(container)
            except Exception:
                if self._cleanup_pending_container(
                    container_name,
                    accept_not_found=False,
                ):
                    self._forget_pending_name(container_name)
                raise

            with self.lock:
                self._pending_names.discard(container_name)
                self._managed[self._container_id(container)] = container

            try:
                container.start()
            except Exception:
                self._cleanup_container(container, kill=False)
                raise
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
            self._reconcile_stale_containers()
            for _ in range(self.pool_size):
                self._create_and_add()
        except Exception:
            self.shutdown_pool()
            raise
        with self.lock:
            self._initialized = True
        logger.info("Container pool ready")

    def get_container(self) -> Any:
        """Lease one container without ever exceeding the hard capacity."""
        with self.lock:
            if self._shutting_down:
                raise RuntimeError("container manager is shutting down")
            if self.pool:
                return self.pool.popleft()
        try:
            return self._create_container()
        except ContainerCapacityError:
            raise
        except Exception:
            self._mark_degraded()
            raise

    def _forget_removed_container(self, container: Any) -> None:
        with self.lock:
            removed = self._managed.pop(self._container_id(container), None)
        if removed is not None:
            self._slots.release()

    def _forget_pending_name(self, container_name: str) -> None:
        with self.lock:
            removed = container_name in self._pending_names
            self._pending_names.discard(container_name)
        if removed:
            self._slots.release()

    def _cleanup_pending_container(
        self,
        container_name: str,
        accept_not_found: bool = True,
    ) -> bool:
        client = self.client
        if client is None:
            return False
        with self._cleanup_lock:
            try:
                container = client.containers.get(container_name)
            except docker.errors.NotFound:
                return accept_not_found
            except Exception as exc:
                logger.error(
                    "Failed to resolve pending sandbox container %s: %s",
                    container_name,
                    exc,
                )
                return False
            try:
                container.remove(force=True, v=True)
            except docker.errors.NotFound:
                return True
            except Exception as exc:
                logger.error(
                    "Failed to remove pending sandbox container %s: %s",
                    container_name,
                    exc,
                )
                return False
        return True

    def _cleanup_container(self, container: Any, kill: bool = True) -> bool:
        with self._cleanup_lock:
            return self._cleanup_container_locked(container, kill=kill)

    def _cleanup_container_locked(self, container: Any, kill: bool = True) -> bool:
        if kill:
            try:
                container.kill()
            except docker.errors.NotFound:
                pass
            except Exception as exc:
                # force=True can still remove a container after kill fails.
                logger.warning(
                    "Failed to kill sandbox container %s: %s", container.id, exc
                )

        try:
            container.remove(force=True, v=True)
        except docker.errors.NotFound:
            self._forget_removed_container(container)
            return True
        except Exception as exc:
            logger.error("Failed to remove sandbox container %s: %s", container.id, exc)
            return False

        self._forget_removed_container(container)
        return True

    def begin_shutdown(self) -> None:
        """Stop new work and kill managed containers to unblock execution threads."""
        with self._create_shutdown_lock:
            with self.lock:
                if self._shutting_down:
                    return
                self._shutting_down = True
                containers = list(self._managed.values())
                self.pool.clear()
        for container in containers:
            with self._cleanup_lock:
                try:
                    container.kill()
                except docker.errors.NotFound:
                    continue
                except Exception as exc:
                    logger.warning(
                        "Failed to kill sandbox container %s during shutdown: %s",
                        container.id,
                        exc,
                    )

    def release_container(self, container: Any, already_stopped: bool = False) -> None:
        """Synchronously destroy a used container and replenish within capacity."""
        removed = self._cleanup_container(container, kill=not already_stopped)
        if not removed:
            self._mark_degraded()
        with self.lock:
            should_replenish = removed and not self._shutting_down
        if not should_replenish:
            return
        try:
            self._create_and_add()
        except Exception as exc:
            self._mark_degraded()
            logger.error("Failed to replenish sandbox container: %s", exc)

    def shutdown_pool(self) -> None:
        """Stop accepting work and remove every container owned by this manager."""
        self.begin_shutdown()
        with self._create_shutdown_lock:
            with self.lock:
                containers = list(self._managed.values())
                pending_names = list(self._pending_names)
                client = self.client
        for container in containers:
            self._cleanup_container(container, kill=False)
        for container_name in pending_names:
            if self._cleanup_pending_container(container_name):
                self._forget_pending_name(container_name)
        close = getattr(client, "close", None)
        if close is not None:
            close()

    @property
    def managed_count(self) -> int:
        with self.lock:
            return len(self._managed) + len(self._pending_names)

    @property
    def is_ready(self) -> bool:
        """初期化済み完全capacityで劣化・生成途中・shutdownがなければTrueを返す。"""
        with self.lock:
            return (
                self._initialized
                and not self._degraded
                and not self._shutting_down
                and len(self._managed) == self.pool_size
                and not self._pending_names
            )


manager = ContainerManager(
    owner_id=os.getenv("SANDBOX_OWNER_ID", DEFAULT_SANDBOX_OWNER_ID),
)
