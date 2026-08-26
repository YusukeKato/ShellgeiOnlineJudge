import asyncio
from pathlib import Path

import main as backend_main
from starlette.types import Message, Scope


BACKEND_DOCKERFILE = Path(__file__).resolve().parents[1] / "Dockerfile"


def _request(
    path: str,
    host: str,
    extra_headers: list[tuple[bytes, bytes]] | None = None,
) -> tuple[int, dict[str, str]]:
    async def scenario() -> tuple[int, dict[str, str]]:
        messages: list[Message] = []
        request_delivered = False

        async def receive() -> Message:
            nonlocal request_delivered
            if request_delivered:
                return {"type": "http.disconnect"}
            request_delivered = True
            return {
                "type": "http.request",
                "body": b"",
                "more_body": False,
            }

        async def send(message: Message) -> None:
            messages.append(message)

        headers = [(b"host", host.encode("ascii"))]
        if extra_headers is not None:
            headers.extend(extra_headers)
        scope: Scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "root_path": "",
            "headers": headers,
            "client": ("127.0.0.1", 12345),
            "server": ("backend", 8000),
        }
        await backend_main.app(scope, receive, send)

        response_start = next(
            message for message in messages if message["type"] == "http.response.start"
        )
        response_headers = {
            key.decode("ascii"): value.decode("ascii")
            for key, value in response_start["headers"]
        }
        return response_start["status"], response_headers

    return asyncio.run(scenario())


def test_public_api_rejects_untrusted_host() -> None:
    status, headers = _request(
        "/api",
        "attacker.invalid",
        [(b"x-forwarded-host", b"backend")],
    )

    assert status == 400
    assert "location" not in headers


def test_public_api_does_not_redirect_trailing_slash() -> None:
    status, headers = _request(
        "/api/",
        "backend:8000",
        [
            (b"forwarded", b"host=attacker.invalid;proto=https"),
            (b"x-forwarded-host", b"attacker.invalid"),
            (b"x-forwarded-proto", b"https"),
        ],
    )

    assert status == 404
    assert "location" not in headers


def test_backend_runtime_disables_proxy_header_parsing() -> None:
    dockerfile = BACKEND_DOCKERFILE.read_text(encoding="utf-8")

    assert (
        'CMD ["uvicorn", "main:app", "--host", "0.0.0.0", '
        '"--port", "8000", "--no-proxy-headers"]' in dockerfile
    )
