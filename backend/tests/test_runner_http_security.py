import asyncio
from collections.abc import Sequence
from typing import cast

import pytest
from starlette.types import Message, Receive, Scope, Send

from soj_shared.submission_request import MAX_SHELLGEI_CHARS
from soj_runner.runner_http_security import (
    RUNNER_REQUEST_BODY_LIMIT_BYTES,
    RunnerRequestSecurityMiddleware,
)
from soj_shared.runner_protocol import (
    RUNNER_EXECUTE_PATH,
    RUNNER_PROTOCOL_VERSION,
    RunnerExecutionRequest,
)


VALID_SECRET = "a" * 64


async def _invoke_middleware(
    headers: Sequence[tuple[bytes, bytes]],
    incoming: Sequence[Message],
) -> tuple[list[Message], int, list[Message]]:
    """入力headerとASGI message列をmiddlewareへ渡し、応答・body読込数・内側入力を返す。"""
    messages = list(incoming)
    sent: list[Message] = []
    forwarded: list[Message] = []
    receive_count = 0

    async def receive() -> Message:
        """request body読込回数を記録し、入力messageを先頭から返す。"""
        nonlocal receive_count
        receive_count += 1
        if messages:
            return messages.pop(0)
        return {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        """middlewareまたは内側applicationが送信したmessageを記録する。"""
        sent.append(message)

    async def inner_app(
        _scope: Scope,
        inner_receive: Receive,
        inner_send: Send,
    ) -> None:
        """認証・上限検査後のbodyを記録し、固定204 responseを返す。"""
        forwarded.append(await inner_receive())
        await inner_send({"type": "http.response.start", "status": 204, "headers": []})
        await inner_send({"type": "http.response.body", "body": b""})

    scope = cast(
        Scope,
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": RUNNER_EXECUTE_PATH,
            "raw_path": RUNNER_EXECUTE_PATH.encode("ascii"),
            "query_string": b"",
            "headers": list(headers),
            "client": ("127.0.0.1", 12345),
            "server": ("runner", 8001),
        },
    )
    middleware = RunnerRequestSecurityMiddleware(inner_app)
    await middleware(scope, receive, send)
    return sent, receive_count, forwarded


@pytest.mark.parametrize(
    "authorization_headers",
    [
        [],
        [(b"authorization", b"Bearer " + b"b" * 64)],
        [
            (b"authorization", b"Bearer " + VALID_SECRET.encode("ascii")),
            (b"authorization", b"Bearer " + VALID_SECRET.encode("ascii")),
        ],
    ],
)
def test_unauthorized_large_body_is_rejected_before_reading(
    monkeypatch: pytest.MonkeyPatch,
    authorization_headers: list[tuple[bytes, bytes]],
) -> None:
    # 認証header欠落・不一致・重複時は、巨大bodyを読まず401を返すことを確認する。
    monkeypatch.setenv("RUNNER_SHARED_SECRET", VALID_SECRET)

    sent, receive_count, forwarded = asyncio.run(
        _invoke_middleware(
            authorization_headers,
            [
                {
                    "type": "http.request",
                    "body": b"x" * (RUNNER_REQUEST_BODY_LIMIT_BYTES + 1),
                    "more_body": False,
                }
            ],
        )
    )

    assert sent[0]["status"] == 401
    assert receive_count == 0
    assert forwarded == []


def test_declared_oversized_body_is_rejected_without_reading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 認証済みでもContent-Lengthが8 KiBを超えるrequestはbody読込前に413とする。
    monkeypatch.setenv("RUNNER_SHARED_SECRET", VALID_SECRET)
    headers = [
        (b"authorization", f"Bearer {VALID_SECRET}".encode("ascii")),
        (b"content-length", str(RUNNER_REQUEST_BODY_LIMIT_BYTES + 1).encode()),
    ]

    sent, receive_count, forwarded = asyncio.run(
        _invoke_middleware(
            headers,
            [{"type": "http.request", "body": b"unused", "more_body": False}],
        )
    )

    assert sent[0]["status"] == 413
    assert receive_count == 0
    assert forwarded == []


def test_chunked_oversized_body_is_rejected_at_the_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Content-Lengthのない分割bodyも合計8 KiB超過時に413とし、内側appへ渡さない。
    monkeypatch.setenv("RUNNER_SHARED_SECRET", VALID_SECRET)
    headers = [(b"authorization", f"Bearer {VALID_SECRET}".encode("ascii"))]

    sent, receive_count, forwarded = asyncio.run(
        _invoke_middleware(
            headers,
            [
                {
                    "type": "http.request",
                    "body": b"x" * RUNNER_REQUEST_BODY_LIMIT_BYTES,
                    "more_body": True,
                },
                {"type": "http.request", "body": b"x", "more_body": True},
                {"type": "http.request", "body": b"ignored", "more_body": False},
            ],
        )
    )

    assert sent[0]["status"] == 413
    assert receive_count == 2
    assert forwarded == []


def test_authenticated_bounded_body_is_replayed_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 認証済みで上限内の分割bodyを1つに結合し、内側appへ1回だけ渡す。
    monkeypatch.setenv("RUNNER_SHARED_SECRET", VALID_SECRET)
    headers = [(b"authorization", f"Bearer {VALID_SECRET}".encode("ascii"))]

    sent, receive_count, forwarded = asyncio.run(
        _invoke_middleware(
            headers,
            [
                {"type": "http.request", "body": b'{"shell', "more_body": True},
                {"type": "http.request", "body": b'gei":"true"}', "more_body": False},
            ],
        )
    )

    assert sent[0]["status"] == 204
    assert receive_count == 2
    assert forwarded == [
        {
            "type": "http.request",
            "body": b'{"shellgei":"true"}',
            "more_body": False,
        }
    ]


def test_largest_valid_runner_request_fits_body_limit() -> None:
    # 4 byte UTF-8文字でcommand上限まで使った正常requestも、内部8 KiB上限内に収まる。
    request = RunnerExecutionRequest(
        protocol_version=RUNNER_PROTOCOL_VERSION,
        request_id="b" * 32,
        problem_revision="a" * 64,
        shellgei="😀" * MAX_SHELLGEI_CHARS,
        problem_id="STANDARD-00000001",
    )

    assert len(request.model_dump_json().encode("utf-8")) <= (
        RUNNER_REQUEST_BODY_LIMIT_BYTES
    )
