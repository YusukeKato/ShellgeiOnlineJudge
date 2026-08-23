import asyncio
import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request
from email.message import Message

import pytest
from fastapi import HTTPException

import api.api_shellgei as api_shellgei
import runner_main
import scripts.runner_client as runner_client_module
from models.model_shellgei import ShellgeiData
from scripts.runner_client import (
    RUNNER_BASE_URL,
    RunnerBusyError,
    RunnerClient,
    RunnerUnavailableError,
)
from scripts.runner_protocol import (
    RUNNER_EXECUTE_PATH,
    RunnerConfigurationError,
    get_runner_shared_secret,
)


VALID_SECRET = "a" * 64


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, amount: int) -> bytes:
        assert amount == runner_client_module.RUNNER_RESPONSE_LIMIT_BYTES + 1
        return self.payload


@pytest.mark.parametrize(
    "secret",
    [
        "",
        "short",
        "a" * 31,
        "a" * 257,
        "contains whitespace" + "x" * 32,
        "replace-with-at-least-32-random-characters",
    ],
)
def test_runner_shared_secret_rejects_unsafe_values(
    monkeypatch: pytest.MonkeyPatch,
    secret: str,
) -> None:
    monkeypatch.setenv("RUNNER_SHARED_SECRET", secret)

    with pytest.raises(RunnerConfigurationError):
        get_runner_shared_secret()


def test_runner_authentication_uses_constant_time_secret_comparison(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUNNER_SHARED_SECRET", VALID_SECRET)

    with pytest.raises(HTTPException) as missing:
        runner_main.require_runner_authentication(None)
    with pytest.raises(HTTPException) as incorrect:
        runner_main.require_runner_authentication("Bearer " + "b" * 64)

    runner_main.require_runner_authentication(f"Bearer {VALID_SECRET}")
    assert missing.value.status_code == 401
    assert incorrect.value.status_code == 401


def test_runner_accepts_only_registered_problem_and_fixed_execution_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class AllowStart:
        def try_acquire(self) -> bool:
            return True

    calls: list[tuple[str, str]] = []

    async def run_with_timeout(shellgei: str, problem_id: str) -> list[str]:
        calls.append((shellgei, problem_id))
        return ["output", "image"]

    yaml_dir = tmp_path / "problems" / "yaml_data"
    yaml_dir.mkdir(parents=True)
    (yaml_dir / "STANDARD-00000001.yaml").touch()
    monkeypatch.setattr(runner_main, "__file__", str(tmp_path / "runner_main.py"))
    monkeypatch.setattr(runner_main, "sandbox_start_rate_limiter", AllowStart())
    monkeypatch.setattr(
        runner_main.docker_client,
        "run_with_timeout",
        run_with_timeout,
    )

    result = asyncio.run(
        runner_main.execute_shellgei(
            ShellgeiData(
                shellgei="printf output",
                problem_id="STANDARD-00000001",
            )
        )
    )

    assert result.model_dump() == {"output": "output", "image": "image"}
    assert calls == [("printf output", "STANDARD-00000001")]


def test_runner_rejects_unknown_problem_before_admission_or_docker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class UnusedAdmissionControl:
        def try_acquire(self) -> bool:
            raise AssertionError("unknown problems must not consume admission tokens")

    async def unexpected_execution(*_args: object) -> list[str]:
        raise AssertionError("unknown problems must not reach Docker")

    monkeypatch.setattr(runner_main, "__file__", str(tmp_path / "runner_main.py"))
    monkeypatch.setattr(
        runner_main,
        "sandbox_start_rate_limiter",
        UnusedAdmissionControl(),
    )
    monkeypatch.setattr(
        runner_main.docker_client,
        "run_with_timeout",
        unexpected_execution,
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            runner_main.execute_shellgei(
                ShellgeiData(
                    shellgei="true",
                    problem_id="MISSING-00000001",
                )
            )
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Problem not found"


def test_runner_lifespan_owns_the_docker_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class FakeManager:
        def initialize_pool(self) -> None:
            events.append("pool_initialize")

        def shutdown_pool(self) -> None:
            events.append("pool_shutdown")

    class FakeDockerClient:
        def close(self) -> None:
            events.append("docker_client_close")

    monkeypatch.setenv("RUNNER_SHARED_SECRET", VALID_SECRET)
    monkeypatch.setattr(runner_main, "manager", FakeManager())
    monkeypatch.setattr(runner_main, "docker_client", FakeDockerClient())

    async def run_lifespan() -> None:
        async with runner_main.lifespan(runner_main.app):
            events.append("serving")

    asyncio.run(run_lifespan())

    assert events == [
        "pool_initialize",
        "serving",
        "pool_shutdown",
        "docker_client_close",
    ]


def test_backend_runner_client_sends_only_the_fixed_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[Request] = []

    def fake_urlopen(request: Request, timeout: int) -> FakeResponse:
        assert timeout == runner_client_module.RUNNER_REQUEST_TIMEOUT_SECONDS
        captured.append(request)
        return FakeResponse(b'{"output":"ok","image":""}')

    monkeypatch.setenv("RUNNER_SHARED_SECRET", VALID_SECRET)
    monkeypatch.setattr(runner_client_module, "urlopen", fake_urlopen)
    client = RunnerClient()
    try:
        result = asyncio.run(client.run("printf ok", "STANDARD-00000001"))
    finally:
        client.close()

    assert result == ["ok", ""]
    assert len(captured) == 1
    request = captured[0]
    assert request.full_url == f"{RUNNER_BASE_URL}{RUNNER_EXECUTE_PATH}"
    assert request.get_method() == "POST"
    assert request.get_header("Authorization") == f"Bearer {VALID_SECRET}"
    assert isinstance(request.data, bytes)
    assert json.loads(request.data) == {
        "shellgei": "printf ok",
        "problem_id": "STANDARD-00000001",
    }


def test_backend_runner_client_maps_busy_without_accepting_error_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(request: Request, timeout: int) -> FakeResponse:
        raise HTTPError(request.full_url, 429, "busy", Message(), None)

    monkeypatch.setenv("RUNNER_SHARED_SECRET", VALID_SECRET)
    monkeypatch.setattr(runner_client_module, "urlopen", fake_urlopen)
    client = RunnerClient()
    try:
        with pytest.raises(RunnerBusyError):
            asyncio.run(client.run("true", "STANDARD-00000001"))
    finally:
        client.close()


@pytest.mark.parametrize(
    "payload",
    [b"not-json", b'{"output":"ok","image":"","extra":"value"}'],
)
def test_backend_runner_client_rejects_invalid_responses(
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
) -> None:
    monkeypatch.setenv("RUNNER_SHARED_SECRET", VALID_SECRET)
    monkeypatch.setattr(
        runner_client_module,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(payload),
    )
    client = RunnerClient()
    try:
        with pytest.raises(RunnerUnavailableError):
            asyncio.run(client.run("true", "STANDARD-00000001"))
    finally:
        client.close()


def test_backend_runner_client_rejects_oversized_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    oversized = b"x" * (runner_client_module.RUNNER_RESPONSE_LIMIT_BYTES + 1)
    monkeypatch.setenv("RUNNER_SHARED_SECRET", VALID_SECRET)
    monkeypatch.setattr(
        runner_client_module,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(oversized),
    )
    client = RunnerClient()
    try:
        with pytest.raises(RunnerUnavailableError):
            asyncio.run(client.run("true", "STANDARD-00000001"))
    finally:
        client.close()


def test_public_api_maps_runner_failure_without_database_work(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class UnusedDatabase:
        def __getattr__(self, name: str) -> Any:
            raise AssertionError(f"database must not be used: {name}")

    async def unavailable(*_args: object) -> list[str]:
        raise RunnerUnavailableError("unavailable")

    yaml_dir = tmp_path / "problems" / "yaml_data"
    yaml_dir.mkdir(parents=True)
    (yaml_dir / "STANDARD-00000001.yaml").touch()
    monkeypatch.setattr(
        api_shellgei,
        "__file__",
        str(tmp_path / "api" / "api_shellgei.py"),
    )
    monkeypatch.setattr(api_shellgei.runner_client, "run", unavailable)

    response = asyncio.run(
        api_shellgei.post_shellgei(
            ShellgeiData(shellgei="true", problem_id="STANDARD-00000001"),
            UnusedDatabase(),  # type: ignore[arg-type]
        )
    )

    assert response.output == "Error: runner is unavailable."
    assert response.id == "-1"
    assert response.image == ""
    assert response.judge == "4"


def test_public_api_preserves_busy_response_for_runner_capacity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class UnusedDatabase:
        def __getattr__(self, name: str) -> Any:
            raise AssertionError(f"database must not be used: {name}")

    async def busy(*_args: object) -> list[str]:
        raise RunnerBusyError("busy")

    yaml_dir = tmp_path / "problems" / "yaml_data"
    yaml_dir.mkdir(parents=True)
    (yaml_dir / "STANDARD-00000001.yaml").touch()
    monkeypatch.setattr(
        api_shellgei,
        "__file__",
        str(tmp_path / "api" / "api_shellgei.py"),
    )
    monkeypatch.setattr(api_shellgei.runner_client, "run", busy)

    response = asyncio.run(
        api_shellgei.post_shellgei(
            ShellgeiData(shellgei="true", problem_id="STANDARD-00000001"),
            UnusedDatabase(),  # type: ignore[arg-type]
        )
    )

    assert response.output == "Error: server is busy."
    assert response.id == "-1"
    assert response.image == ""
    assert response.judge == "4"
