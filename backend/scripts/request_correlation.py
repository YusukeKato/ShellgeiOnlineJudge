import logging
import time
from collections.abc import Awaitable, Callable

from starlette.types import Message, Receive, Scope, Send

from scripts.request_context import bind_request_id, new_request_id
from scripts.structured_logging import (
    LogComponent,
    LogEndpoint,
    LogEvent,
    SAFE_EVENT_LOGGER_NAME,
    log_safe_event,
)


REQUEST_ID_RESPONSE_HEADER = b"x-request-id"
PUBLIC_SUBMISSION_ENDPOINTS = {
    "/api/shellgei": LogEndpoint.LEGACY_SUBMISSION,
    "/api/v3/submissions": LogEndpoint.V3_SUBMISSION,
}
AsgiApp = Callable[[Scope, Receive, Send], Awaitable[None]]
RequestIdFactory = Callable[[], str]
MonotonicClock = Callable[[], int]
logger = logging.getLogger(SAFE_EVENT_LOGGER_NAME)


def _duration_ms(started_ns: int, finished_ns: int) -> int:
    """入力した開始・終了monotonic時刻から、負値にならない経過msを返す。"""
    return max(0, (finished_ns - started_ns) // 1_000_000)


class RequestCorrelationMiddleware:
    """提出requestにserver生成IDを付与し、安全な完了eventとresponse headerを追加する。"""

    def __init__(
        self,
        app: AsgiApp,
        request_id_factory: RequestIdFactory = new_request_id,
        clock_ns: MonotonicClock = time.monotonic_ns,
    ) -> None:
        """内側ASGI app、request ID生成関数、経過時間用clockを受け取り保持する。"""
        self._app = app
        self._request_id_factory = request_id_factory
        self._clock_ns = clock_ns

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """対象HTTP requestのcontextとresponseにIDを付け、status・所要時間だけをlogに残す。"""
        endpoint = PUBLIC_SUBMISSION_ENDPOINTS.get(scope.get("path", ""))
        if scope["type"] != "http" or endpoint is None:
            await self._app(scope, receive, send)
            return

        request_id = self._request_id_factory()
        started_ns = self._clock_ns()
        http_status = 500

        async def send_with_request_id(message: Message) -> None:
            """response開始messageにserver生成request IDを上書き追加して送信する。"""
            nonlocal http_status
            if message["type"] == "http.response.start":
                http_status = message["status"]
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() != REQUEST_ID_RESPONSE_HEADER
                ]
                headers.append((REQUEST_ID_RESPONSE_HEADER, request_id.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        with bind_request_id(request_id):
            try:
                await self._app(scope, receive, send_with_request_id)
            finally:
                log_safe_event(
                    logger,
                    LogEvent.HTTP_REQUEST_COMPLETED,
                    LogComponent.BACKEND_HTTP,
                    request_id=request_id,
                    endpoint=endpoint,
                    http_status=http_status,
                    duration_ms=_duration_ms(started_ns, self._clock_ns()),
                )
