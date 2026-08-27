import asyncio
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from models.model_shellgei import ShellgeiData
from scripts.async_thread import wait_for_thread_future
from scripts.runner_protocol import (
    RUNNER_EXECUTE_PATH,
    RunnerConfigurationError,
    RunnerExecutionResponse,
    get_runner_shared_secret,
)


logger = logging.getLogger(__name__)

RUNNER_BASE_URL = "http://runner:8001"
RUNNER_REQUEST_TIMEOUT_SECONDS = 30
RUNNER_RESPONSE_LIMIT_BYTES = 1_100_000
RUNNER_CLIENT_CAPACITY = 3


class RunnerUnavailableError(RuntimeError):
    """Raised when the private runner cannot return a valid result."""


class RunnerBusyError(RuntimeError):
    """Raised when the private runner cannot accept another execution."""


class RunnerClient:
    def __init__(self) -> None:
        self.executor = ThreadPoolExecutor(max_workers=RUNNER_CLIENT_CAPACITY)
        self._slots = threading.BoundedSemaphore(RUNNER_CLIENT_CAPACITY)
        self._opener = build_opener(ProxyHandler({}))

    @staticmethod
    def validate_configuration() -> None:
        get_runner_shared_secret()

    def _execute_sync(self, shellgei: str, problem_id: str) -> list[str]:
        secret = get_runner_shared_secret()
        payload = ShellgeiData(shellgei=shellgei, problem_id=problem_id)
        request = Request(
            f"{RUNNER_BASE_URL}{RUNNER_EXECUTE_PATH}",
            data=payload.model_dump_json().encode("utf-8"),
            headers={
                "Authorization": f"Bearer {secret}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self._opener.open(
                request,
                timeout=RUNNER_REQUEST_TIMEOUT_SECONDS,
            ) as response:
                response_body = response.read(RUNNER_RESPONSE_LIMIT_BYTES + 1)
                if len(response_body) > RUNNER_RESPONSE_LIMIT_BYTES:
                    raise RunnerUnavailableError("runner response exceeded the limit")
        except HTTPError as exc:
            if exc.code == 429:
                raise RunnerBusyError("runner execution capacity reached") from exc
            raise RunnerUnavailableError(
                f"runner returned HTTP status {exc.code}"
            ) from exc
        except OSError as exc:
            raise RunnerUnavailableError("runner request failed") from exc

        try:
            result = RunnerExecutionResponse.model_validate_json(response_body)
        except ValueError as exc:
            raise RunnerUnavailableError("runner returned an invalid response") from exc
        return [result.output, result.image]

    async def run(self, shellgei: str, problem_id: str) -> list[str]:
        if not self._slots.acquire(blocking=False):
            raise RunnerBusyError("runner client capacity reached")

        release_when_done = False
        try:
            future = self.executor.submit(
                self._execute_sync,
                shellgei,
                problem_id,
            )
            try:
                return await wait_for_thread_future(future)
            except asyncio.CancelledError:
                future.add_done_callback(lambda _: self._slots.release())
                release_when_done = True
                raise
        except (RunnerBusyError, RunnerConfigurationError, RunnerUnavailableError):
            raise
        except Exception as exc:
            logger.warning("Unexpected runner client failure: %s", exc)
            raise RunnerUnavailableError("runner request failed") from exc
        finally:
            if not release_when_done:
                self._slots.release()

    def close(self) -> None:
        self.executor.shutdown(wait=True, cancel_futures=True)


runner_client = RunnerClient()
