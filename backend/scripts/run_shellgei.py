#!/usr/bin/env python3
import asyncio
import base64
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from models.execution import (
    MAX_CAPTURED_OUTPUT_CHARS,
    MAX_EXECUTION_ERROR_CHARS,
    ExecutionArtifact,
    ExecutionResult,
    ExecutionStatus,
)
from scripts.async_thread import wait_for_thread_future
from scripts.container_manager import manager
from scripts.input_validation import validate_problem_id
from scripts.problem_repository import (
    ProblemRecord,
    ProblemRepository,
    get_problem_repository,
)
from scripts.sandbox_executor import (
    SandboxAcquisitionError,
    SandboxExecutionOutcome,
    SandboxExecutor,
)


DEFAULT_EXECUTION_TIMEOUT_SECONDS = 10
DEFAULT_OUTPUT_LIMIT_CHARS = MAX_CAPTURED_OUTPUT_CHARS
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

    @staticmethod
    def _error_result(message: str, duration_ms: int = 0) -> ExecutionResult:
        """入力messageと任意の所要時間から、出力なしの構造化error結果を返す。"""
        return ExecutionResult(
            status=ExecutionStatus.ERROR,
            stdout="",
            stderr="",
            exit_code=None,
            timed_out=False,
            truncated=False,
            duration_ms=duration_ms,
            artifact=None,
            error=message[:MAX_EXECUTION_ERROR_CHARS],
        )

    @staticmethod
    def _decode_output(
        outcome: SandboxExecutionOutcome,
        limit_chars: int,
    ) -> tuple[str, str, bool]:
        """分離byte出力をUTF-8化して合計文字数上限へ収め、切り詰め有無を返す。"""
        stdout = outcome.stdout.decode("utf-8", errors="ignore")
        stderr = outcome.stderr.decode("utf-8", errors="ignore")
        stdout_limited = stdout[:limit_chars]
        stderr_limit = max(0, limit_chars - len(stdout_limited))
        stderr_limited = stderr[:stderr_limit]
        truncated = (
            outcome.truncated
            or len(stdout_limited) < len(stdout)
            or len(stderr_limited) < len(stderr)
        )
        return stdout_limited, stderr_limited, truncated

    @classmethod
    def _to_execution_result(
        cls,
        outcome: SandboxExecutionOutcome,
        record: ProblemRecord,
        limit_chars: int,
    ) -> ExecutionResult:
        """sandboxのbinary outcomeを上限検証済みrunner実行結果へ変換して返す。"""
        stdout, stderr, truncated = cls._decode_output(outcome, limit_chars)
        status = outcome.status
        if truncated and status is ExecutionStatus.COMPLETED:
            status = ExecutionStatus.OUTPUT_LIMIT
        artifact = None
        judge = record.definition.judge
        if (
            status is ExecutionStatus.COMPLETED
            and judge.type == "image"
            and outcome.artifact is not None
        ):
            artifact = ExecutionArtifact(
                path=judge.artifact.path,
                media_type=judge.artifact.media_type,
                data=base64.b64encode(outcome.artifact).decode("ascii"),
            )
        error = outcome.error
        if status is ExecutionStatus.ERROR:
            error = (error or "sandbox execution failed")[:MAX_EXECUTION_ERROR_CHARS]
        elif error is not None:
            error = error[:MAX_EXECUTION_ERROR_CHARS]
        return ExecutionResult(
            status=status,
            stdout=stdout,
            stderr=stderr,
            exit_code=outcome.exit_code,
            timed_out=outcome.timed_out,
            truncated=truncated,
            duration_ms=outcome.duration_ms,
            artifact=artifact,
            error=error,
        )

    def exec_shellgei(
        self, shellgei: str, problem_id: str, timeout: float, limit_str: int
    ) -> ExecutionResult:
        """指定問題のfixtureとcommandをsandboxで同期実行し、構造化結果を返す。"""
        try:
            validate_problem_id(problem_id)
        except ValueError:
            return self._error_result("invalid problem ID")
        record = self._repository().get(problem_id)
        if record is None:
            return self._error_result("problem not found")

        try:
            outcome = self.sandbox_executor.execute(
                record,
                shellgei,
                timeout,
                limit_str,
            )
            return self._to_execution_result(outcome, record, limit_str)
        except SandboxAcquisitionError as exc:
            return self._error_result(f"failed to get container: {exc}")
        except Exception as e:
            return self._error_result(str(e))

    async def run_with_timeout(
        self,
        shellgei: str,
        problem_id: str,
        timeout: float = DEFAULT_EXECUTION_TIMEOUT_SECONDS,
        limit_str: int = DEFAULT_OUTPUT_LIMIT_CHARS,
    ) -> ExecutionResult:
        """空き枠があればsandbox実行をthreadへ委譲し、構造化結果を返す。"""
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
                return self._error_result("sandbox cleanup timed out")
            except asyncio.CancelledError:
                future.add_done_callback(lambda _: self._execution_slots.release())
                release_when_done = True
                raise
        except Exception as e:
            return self._error_result(f"run with timeout: {e}")
        finally:
            if not release_when_done:
                self._execution_slots.release()

    def close(self) -> None:
        """新規thread投入を止め、実行中taskの完了を待ってexecutorを閉じる。"""
        self.executor.shutdown(wait=True, cancel_futures=True)
