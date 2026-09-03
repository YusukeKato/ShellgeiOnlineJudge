import asyncio
import logging
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from scripts.async_thread import wait_for_thread_future
from scripts.problem_repository import get_problem_repository
from scripts.request_context import current_request_id, new_request_id
from scripts.runner_protocol import (
    RUNNER_EXECUTE_PATH,
    RUNNER_PROTOCOL_VERSION,
    ExecutionResult,
    RunnerBusyError,
    RunnerConfigurationError,
    RunnerExecutionRequest,
    RunnerExecutionResponse,
    RunnerGateway,
    RunnerUnavailableError,
    get_runner_shared_secret,
)
from scripts.structured_logging import (
    LogComponent,
    LogEvent,
    SAFE_EVENT_LOGGER_NAME,
    log_safe_event,
)


logger = logging.getLogger(SAFE_EVENT_LOGGER_NAME)

RUNNER_BASE_URL = "http://runner:8001"
RUNNER_REQUEST_TIMEOUT_SECONDS = 30
RUNNER_RESPONSE_LIMIT_BYTES = 1_100_000
RUNNER_CLIENT_CAPACITY = 3
ProblemRevisionProvider = Callable[[], str]
RequestIdProvider = Callable[[], str]


def loaded_problem_revision() -> str:
    """backend起動時に検証・読込済みとなったproblem revisionを返す。"""
    return get_problem_repository().revision


def request_id_for_execution() -> str:
    """現在の提出IDを返し、HTTP context外の実行なら新しいIDを生成する。"""
    return current_request_id() or new_request_id()


class RunnerClient:
    def __init__(
        self,
        problem_revision_provider: ProblemRevisionProvider = loaded_problem_revision,
        request_id_provider: RequestIdProvider = request_id_for_execution,
    ) -> None:
        """固定worker・直接接続opener・revision・request ID取得関数を初期化する。"""
        self.executor = ThreadPoolExecutor(max_workers=RUNNER_CLIENT_CAPACITY)
        self._slots = threading.BoundedSemaphore(RUNNER_CLIENT_CAPACITY)
        self._opener = build_opener(ProxyHandler({}))
        self._problem_revision_provider = problem_revision_provider
        self._request_id_provider = request_id_provider

    @staticmethod
    def validate_configuration() -> None:
        """runner共有secretを起動前に検証し、返値なしで設定不備を通知する。"""
        get_runner_shared_secret()

    def _execute_sync(
        self,
        shellgei: str,
        problem_id: str,
        request_id: str,
    ) -> ExecutionResult:
        """入力command・ID・request IDをversion付きHTTP requestで送り、typed結果を返す。

        認証、通信、status、response byte上限、JSON schemaの異常はrunner用例外へ
        変換し、HTTP worker threadから呼び出せる同期処理として実行する。
        """
        secret = get_runner_shared_secret()
        problem_revision = self._problem_revision_provider()
        payload = RunnerExecutionRequest(
            protocol_version=RUNNER_PROTOCOL_VERSION,
            request_id=request_id,
            problem_revision=problem_revision,
            shellgei=shellgei,
            problem_id=problem_id,
        )
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
            if exc.code == 409:
                raise RunnerUnavailableError(
                    "runner problem revision mismatch"
                ) from exc
            raise RunnerUnavailableError(
                f"runner returned HTTP status {exc.code}"
            ) from exc
        except OSError as exc:
            raise RunnerUnavailableError("runner request failed") from exc

        try:
            response = RunnerExecutionResponse.model_validate_json(response_body)
        except ValueError as exc:
            raise RunnerUnavailableError("runner returned an invalid response") from exc
        if response.problem_revision != problem_revision:
            raise RunnerUnavailableError("runner returned a different problem revision")
        if response.request_id != request_id:
            raise RunnerUnavailableError("runner returned a different request ID")
        return response.result

    async def execute(self, shellgei: str, problem_id: str) -> ExecutionResult:
        """空きworkerがあればprivate runnerを呼び、typed実行結果を非同期で返す。

        入力はcommandとproblem ID。client容量超過、設定不備、runner通信失敗は
        対応する例外を送出し、cancel時もthread完了までslotを保持する。
        """
        if not self._slots.acquire(blocking=False):
            raise RunnerBusyError("runner client capacity reached")

        request_id = self._request_id_provider()
        release_when_done = False
        try:
            future = self.executor.submit(
                self._execute_sync,
                shellgei,
                problem_id,
                request_id,
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
            log_safe_event(
                logger,
                LogEvent.RUNNER_CLIENT_FAILED,
                LogComponent.SUBMISSION,
                request_id=request_id,
                level=logging.WARNING,
            )
            raise RunnerUnavailableError("runner request failed") from exc
        finally:
            if not release_when_done:
                self._slots.release()

    def close(self) -> None:
        """新規runner requestを停止し、実行中HTTP workerを待ってexecutorを閉じる。"""
        self.executor.shutdown(wait=True, cancel_futures=True)


runner_client = RunnerClient()
runner_gateway: RunnerGateway = runner_client
