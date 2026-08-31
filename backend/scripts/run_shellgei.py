#!/usr/bin/env python3
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from scripts.async_thread import wait_for_thread_future
from scripts.container_manager import manager
from scripts.input_validation import validate_problem_id
from scripts.problem_repository import ProblemRepository, get_problem_repository
from scripts.sandbox_executor import (
    SandboxAcquisitionError,
    SandboxExecutor,
)


DEFAULT_EXECUTION_TIMEOUT_SECONDS = 10
DEFAULT_OUTPUT_LIMIT_CHARS = 1000
MAX_IMAGE_BYTES = 750_000
DOCKER_OPERATION_GRACE_SECONDS: float = 15.0


class SandboxBusyError(RuntimeError):
    """Raised when all sandbox execution slots are occupied."""


class ShellgeiDockerClient:
    def __init__(
        self,
        container_manager: Any = manager,
        max_concurrent: int | None = None,
        problem_repository: ProblemRepository | None = None,
        sandbox_executor: SandboxExecutor | None = None,
    ) -> None:
        """manager・並行数・問題repository・任意executorでclientを初期化する。"""
        self.manager = container_manager
        capacity = max_concurrent or container_manager.pool_size
        if capacity < 1:
            raise ValueError("max_concurrent must be at least 1")
        self.executor = ThreadPoolExecutor(max_workers=capacity)
        self._execution_slots = threading.BoundedSemaphore(capacity)
        self.problem_repository = problem_repository
        self.sandbox_executor = sandbox_executor or SandboxExecutor(container_manager)

    def _repository(self) -> ProblemRepository:
        """注入済みrepositoryを返し、未指定なら起動時にloadしたrepositoryを返す。"""
        return self.problem_repository or get_problem_repository()

    def exec_shellgei(
        self, shellgei: str, problem_id: str, timeout: float, limit_str: int
    ) -> list[str]:
        """指定問題のfixtureとcommandをsandboxで同期実行し、文字列・画像を返す。"""
        try:
            validate_problem_id(problem_id)
        except ValueError:
            return ["Error: invalid problem ID.", ""]
        record = self._repository().get(problem_id)
        if record is None:
            return ["Error: problem not found.", ""]

        try:
            result = self.sandbox_executor.execute(
                record,
                shellgei,
                timeout,
                limit_str,
            )
            return [result.output, result.artifact]
        except SandboxAcquisitionError as exc:
            return [f"Error: failed to get container: {exc}", ""]
        except Exception as e:
            return [f"Error during execution: {e}", ""]

    async def run_with_timeout(
        self,
        shellgei: str,
        problem_id: str,
        timeout: float = DEFAULT_EXECUTION_TIMEOUT_SECONDS,
        limit_str: int = DEFAULT_OUTPUT_LIMIT_CHARS,
    ) -> list[str]:
        """空き枠があればsandbox実行をthreadへ委譲し、timeout込みの結果を返す。"""
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
        """新規thread投入を止め、実行中taskの完了を待ってexecutorを閉じる。"""
        self.executor.shutdown(wait=True, cancel_futures=True)
