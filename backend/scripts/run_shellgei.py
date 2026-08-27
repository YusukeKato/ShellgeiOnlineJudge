#!/usr/bin/env python3
import asyncio
import base64
import threading
from collections.abc import Iterable
from typing import Any

import yaml
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from scripts.async_thread import wait_for_thread_future
from scripts.container_manager import SANDBOX_WORK_DIRECTORY, manager
from scripts.execution_archive import build_execution_archive
from scripts.input_validation import validate_problem_id
from scripts.sandbox_limits import BoundedByteBuffer


DEFAULT_EXECUTION_TIMEOUT_SECONDS = 10
DEFAULT_OUTPUT_LIMIT_CHARS = 1000
MAX_UTF8_BYTES_PER_CHAR = 4
MAX_IMAGE_BYTES = 750_000
DOCKER_OPERATION_GRACE_SECONDS: float = 15.0
EXECUTION_ARCHIVE_ENVIRONMENT = "SOJ_EXECUTION_ARCHIVE"
EXECUTION_ARCHIVE_EXTRACT_COMMAND = (
    "set -eu; umask 077; "
    f'printf "%s" "${EXECUTION_ARCHIVE_ENVIRONMENT}" | /usr/bin/base64 -d | '
    "/usr/bin/tar -x -f - --no-same-owner --no-same-permissions"
)
OUTPUT_IMAGE_READ_COMMAND = (
    "if [ -f /media/output.gif ]; then source=/media/output.gif; "
    "elif [ -f /media/output.jpg ]; then source=/media/output.jpg; "
    "else exit 0; fi; "
    f'exec /usr/bin/head -c {MAX_IMAGE_BYTES + 1} -- "$source"'
)


class SandboxBusyError(RuntimeError):
    """Raised when all sandbox execution slots are occupied."""


class _ExecutionWatchdog:
    def __init__(self, container: Any) -> None:
        self.container = container
        self._lock = threading.Lock()
        self._finished = False
        self._reason: str | None = None
        self.termination_error: Exception | None = None

    def terminate(self, reason: str) -> bool:
        with self._lock:
            if self._finished or self._reason is not None:
                return False
            self._reason = reason
        try:
            self.container.kill()
        except Exception as exc:
            self.termination_error = exc
        return True

    def finish(self) -> str | None:
        with self._lock:
            self._finished = True
            return self._reason

    @property
    def reason(self) -> str | None:
        with self._lock:
            return self._reason


class ShellgeiDockerClient:
    def __init__(
        self,
        container_manager: Any = manager,
        max_concurrent: int | None = None,
    ) -> None:
        self.manager = container_manager
        capacity = max_concurrent or container_manager.pool_size
        if capacity < 1:
            raise ValueError("max_concurrent must be at least 1")
        self.executor = ThreadPoolExecutor(max_workers=capacity)
        self._execution_slots = threading.BoundedSemaphore(capacity)
        self.base_dir = Path(__file__).resolve().parent.parent

    @staticmethod
    def _stream_chunks(output: Any) -> Iterable[bytes]:
        if isinstance(output, bytes):
            return (output,)
        return output

    @staticmethod
    def _format_output(
        output: BoundedByteBuffer,
        limit_chars: int,
        reason: str | None,
        execution_error: Exception | None,
    ) -> str:
        decoded = output.to_bytes().decode("utf-8", errors="ignore")
        if reason == "timeout":
            suffix = "\n[Timed out]"
            return decoded[: max(0, limit_chars - len(suffix))] + suffix
        if reason == "output_limit":
            return decoded[:limit_chars] + "..."
        if execution_error is not None:
            return f"Error during execution: {execution_error}"[:limit_chars]
        if not decoded:
            return "NULL"
        if len(decoded) > limit_chars:
            return decoded[:limit_chars] + "..."
        return decoded

    def _read_output_image(self, container: Any) -> str:
        image = BoundedByteBuffer(MAX_IMAGE_BYTES + 1)
        try:
            image_stream = container.exec_run(
                ["/bin/sh", "-c", OUTPUT_IMAGE_READ_COMMAND],
                stdout=True,
                stderr=False,
                stream=True,
            )
            for chunk in self._stream_chunks(image_stream.output):
                if chunk and not image.append(chunk):
                    return ""
        except Exception:
            return ""
        payload = image.to_bytes()
        if not payload or len(payload) > MAX_IMAGE_BYTES:
            return ""
        return base64.b64encode(payload).decode("ascii")

    def exec_shellgei(
        self, shellgei: str, problem_id: str, timeout: float, limit_str: int
    ) -> list[str]:
        try:
            validate_problem_id(problem_id)
        except ValueError:
            return ["Error: invalid problem ID.", ""]

        container = None
        container_stopped = False
        try:
            container = self.manager.get_container()
        except Exception as e:
            return [f"Error: failed to get container: {e}", ""]

        try:
            # Build all request-specific files in memory. Host-side shared temporary
            # files would allow concurrent requests to overwrite each other's data.
            yaml_path = self.base_dir / "problems" / "yaml_data" / f"{problem_id}.yaml"
            input_str = ""
            if yaml_path.exists():
                with open(yaml_path, "r", encoding="utf-8") as yf:
                    p_data = yaml.safe_load(yf)
                input_str = p_data.get("input", "")
            execution_archive = build_execution_archive(shellgei, input_str)
            encoded_archive = base64.b64encode(execution_archive.getvalue()).decode(
                "ascii"
            )
            setup_result = container.exec_run(
                ["/bin/sh", "-c", EXECUTION_ARCHIVE_EXTRACT_COMMAND],
                environment={EXECUTION_ARCHIVE_ENVIRONMENT: encoded_archive},
                stdout=False,
                stderr=True,
                workdir=SANDBOX_WORK_DIRECTORY,
            )
            if setup_result.exit_code != 0:
                raise RuntimeError("failed to prepare sandbox files")
            watchdog = _ExecutionWatchdog(container)
            timeout_timer = threading.Timer(
                timeout, watchdog.terminate, args=("timeout",)
            )
            timeout_timer.daemon = True
            timeout_timer.start()

            output = BoundedByteBuffer(limit_str * MAX_UTF8_BYTES_PER_CHAR)
            output_image = ""
            execution_error: Exception | None = None
            try:
                container.exec_run(
                    ["convert", "-size", "200x200", "xc:white", "/media/output.jpg"],
                    workdir=SANDBOX_WORK_DIRECTORY,
                )
                if watchdog.reason is None:
                    exec_stream = container.exec_run(
                        ["bash", "z.bash"],
                        demux=False,
                        stream=True,
                        workdir=SANDBOX_WORK_DIRECTORY,
                    )
                    for chunk in self._stream_chunks(exec_stream.output):
                        if chunk and not output.append(chunk):
                            watchdog.terminate("output_limit")
                            break
                if watchdog.reason is None:
                    output_image = self._read_output_image(container)
            except Exception as exc:
                execution_error = exc
            finally:
                timeout_timer.cancel()
                reason = watchdog.finish()
                if reason is None:
                    try:
                        # Stop PID 1 as well as any user-created background children
                        # before inspecting the output image.
                        container.kill()
                        container_stopped = True
                    except Exception as exc:
                        execution_error = execution_error or exc
                elif watchdog.termination_error is None:
                    container_stopped = True
                timeout_timer.join(timeout=0.1)

            output_utf8 = self._format_output(
                output, limit_str, reason, execution_error
            )
            if reason is not None or execution_error is not None:
                return [output_utf8, ""]
            return [output_utf8, output_image]
        except Exception as e:
            return [f"Error during execution: {e}", ""]

        finally:
            if container:
                self.manager.release_container(
                    container,
                    already_stopped=container_stopped,
                )

    async def run_with_timeout(
        self,
        shellgei: str,
        problem_id: str,
        timeout: float = DEFAULT_EXECUTION_TIMEOUT_SECONDS,
        limit_str: int = DEFAULT_OUTPUT_LIMIT_CHARS,
    ) -> list[str]:
        if not self._execution_slots.acquire(blocking=False):
            raise SandboxBusyError("sandbox execution capacity reached")

        release_when_done = False
        try:
            future = self.executor.submit(
                self.exec_shellgei,
                shellgei,
                problem_id,
                timeout,
                limit_str,
            )
            try:
                return await wait_for_thread_future(
                    future,
                    timeout=timeout + DOCKER_OPERATION_GRACE_SECONDS,
                )
            except TimeoutError:
                # A running thread cannot be cancelled. Keep its capacity reserved
                # until the watchdog-driven cleanup has actually returned.
                future.add_done_callback(lambda _: self._execution_slots.release())
                release_when_done = True
                return ["Error: sandbox cleanup timed out.", ""]
            except asyncio.CancelledError:
                future.add_done_callback(lambda _: self._execution_slots.release())
                release_when_done = True
                raise
        except Exception as e:
            return [f"Error: run with timeout: {e}", ""]
        finally:
            if not release_when_done:
                self._execution_slots.release()

    def close(self) -> None:
        self.executor.shutdown(wait=True, cancel_futures=True)
