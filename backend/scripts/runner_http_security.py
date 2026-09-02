import secrets
from collections.abc import Awaitable, Callable

from starlette.types import Message, Receive, Scope, Send

from scripts.runner_protocol import RUNNER_EXECUTE_PATH, get_runner_shared_secret


RUNNER_REQUEST_BODY_LIMIT_BYTES = 8 * 1024
AsgiApp = Callable[[Scope, Receive, Send], Awaitable[None]]


async def _send_error(send: Send, status_code: int, detail: str) -> None:
    """入力statusと固定detailから、内部API用の小さいJSON responseを送信する。"""
    body = f'{{"detail":"{detail}"}}'.encode("ascii")
    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


def _single_header(scope: Scope, name: bytes) -> bytes | None:
    """入力ASGI scopeから指定headerを1個だけ返し、欠落・重複時はNoneを返す。"""
    values = [
        value
        for header_name, value in scope.get("headers", [])
        if header_name.lower() == name
    ]
    return values[0] if len(values) == 1 else None


def _authenticated(scope: Scope) -> bool:
    """Authorizationが共有secretのBearer値と定数時間一致する場合だけTrueを返す。"""
    authorization = _single_header(scope, b"authorization")
    if authorization is None:
        return False
    expected = f"Bearer {get_runner_shared_secret()}".encode("ascii")
    return secrets.compare_digest(authorization, expected)


def _declared_content_length(scope: Scope) -> int | None:
    """単一Content-Lengthを非負整数で返し、欠落時はNone、不正時はValueErrorを送出する。"""
    value = _single_header(scope, b"content-length")
    if value is None:
        if any(
            name.lower() == b"content-length" for name, _ in scope.get("headers", [])
        ):
            raise ValueError("duplicate content length")
        return None
    try:
        length = int(value)
    except ValueError as exc:
        raise ValueError("invalid content length") from exc
    if length < 0:
        raise ValueError("invalid content length")
    return length


async def _read_bounded_body(receive: Receive) -> tuple[bytes | None, Message | None]:
    """ASGI bodyを上限まで読み、超過ならNone、途中切断なら最後のmessageとともに返す。"""
    body = bytearray()
    while True:
        message = await receive()
        if message["type"] != "http.request":
            return bytes(body), message
        body.extend(message.get("body", b""))
        if len(body) > RUNNER_REQUEST_BODY_LIMIT_BYTES:
            return None, None
        if not message.get("more_body", False):
            return bytes(body), None


class RunnerRequestSecurityMiddleware:
    """runner実行pathをbody parse前に認証し、認証後のbodyを上限内へ制限する。"""

    def __init__(self, app: AsgiApp) -> None:
        """認証・body検査成功後に呼ぶ内側ASGI applicationを保持する。"""
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """実行requestだけを認証・bufferingし、再生可能なbodyを内側appへ渡す。"""
        if scope["type"] != "http" or scope.get("path") != RUNNER_EXECUTE_PATH:
            await self._app(scope, receive, send)
            return
        if not _authenticated(scope):
            await _send_error(send, 401, "Unauthorized")
            return
        try:
            declared_length = _declared_content_length(scope)
        except ValueError:
            await _send_error(send, 400, "Invalid Content-Length")
            return
        if (
            declared_length is not None
            and declared_length > RUNNER_REQUEST_BODY_LIMIT_BYTES
        ):
            await _send_error(send, 413, "Request body too large")
            return

        body, terminal_message = await _read_bounded_body(receive)
        if body is None:
            await _send_error(send, 413, "Request body too large")
            return
        body_replayed = False

        async def replay_receive() -> Message:
            """buffer済みbodyを1回返し、その後は切断messageまたは元receiveへ委譲する。"""
            nonlocal body_replayed
            if not body_replayed:
                body_replayed = True
                return {
                    "type": "http.request",
                    "body": body,
                    "more_body": False,
                }
            if terminal_message is not None:
                return terminal_message
            return await receive()

        await self._app(scope, replay_receive, send)
