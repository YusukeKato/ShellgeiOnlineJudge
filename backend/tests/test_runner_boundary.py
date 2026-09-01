import asyncio
import json
from email.message import Message
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request

import pytest
from fastapi import HTTPException

import api.api_shellgei as api_shellgei
import runner_main
import scripts.runner_client as runner_client_module
from models.execution_log import ExecutionLogEntry
from models.model_shellgei import ShellgeiData
from scripts.judge import JudgeResult, JudgeVerdict
from scripts.runner_client import (
    RUNNER_BASE_URL,
    RunnerBusyError,
    RunnerClient,
    RunnerUnavailableError,
)
from scripts.runner_protocol import (
    RUNNER_EXECUTE_PATH,
    RUNNER_PROTOCOL_VERSION,
    ExecutionArtifact,
    ExecutionResult,
    ExecutionStatus,
    RunnerConfigurationError,
    RunnerExecutionRequest,
    RunnerExecutionResponse,
    get_runner_shared_secret,
)


VALID_SECRET = "a" * 64


def _completed_result(
    stdout: str = "ok",
    *,
    stderr: str = "",
    artifact: ExecutionArtifact | None = None,
) -> ExecutionResult:
    # 任意の分離出力とartifactから、境界test用の正常完了結果を返す。
    return ExecutionResult(
        status=ExecutionStatus.COMPLETED,
        stdout=stdout,
        stderr=stderr,
        exit_code=0,
        timed_out=False,
        truncated=False,
        duration_ms=1,
        artifact=artifact,
        error=None,
    )


def _runner_response_bytes(stdout: str) -> bytes:
    # 任意stdoutをprotocol version 3の正常runner response JSONへ変換する。
    return (
        RunnerExecutionResponse(
            protocol_version=RUNNER_PROTOCOL_VERSION,
            result=_completed_result(stdout),
        )
        .model_dump_json()
        .encode("utf-8")
    )


def _runner_request(
    shellgei: str = "true",
    problem_id: str = "STANDARD-00000001",
) -> RunnerExecutionRequest:
    """入力command・problem IDから、現行versionの内部runner requestを返す。"""
    return RunnerExecutionRequest(
        protocol_version=RUNNER_PROTOCOL_VERSION,
        shellgei=shellgei,
        problem_id=problem_id,
    )


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        """runner応答bodyのbytesを受け取り、模擬HTTP responseとして保持する。"""
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        """context manager開始時に自身をresponseとして返す。"""
        return self

    def __exit__(self, *_args: object) -> None:
        """context manager終了時に追加処理を行わずNoneを返す。"""
        return None

    def read(self, amount: int) -> bytes:
        """入力読込上限がprotocol値であることを確認し、保持したpayloadを返す。"""
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
    # 空・短すぎる・長すぎる・空白入り・placeholder secretを拒否することを確認する。
    monkeypatch.setenv("RUNNER_SHARED_SECRET", secret)

    with pytest.raises(RunnerConfigurationError):
        get_runner_shared_secret()


def test_runner_authentication_uses_constant_time_secret_comparison(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 欠落・不一致secretを401にし、一致secretだけを許可することを確認する。
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
) -> None:
    # 登録済み問題だけを固定引数でDocker clientへ渡し、typed responseを返すことを確認する。
    class AllowStart:
        def try_acquire(self) -> bool:
            """sandbox開始token取得を常に許可し、Trueを返す。"""
            return True

    calls: list[tuple[str, str]] = []

    async def run_with_timeout(shellgei: str, problem_id: str) -> ExecutionResult:
        """入力command・IDを記録し、固定の構造化結果を返す。"""
        calls.append((shellgei, problem_id))
        return _completed_result("output")

    monkeypatch.setattr(
        runner_main,
        "get_problem_repository",
        lambda: SimpleNamespace(
            get=lambda _problem_id: SimpleNamespace(
                definition=SimpleNamespace(judge=SimpleNamespace(type="text"))
            )
        ),
    )
    monkeypatch.setattr(runner_main, "sandbox_start_rate_limiter", AllowStart())
    monkeypatch.setattr(
        runner_main.docker_client,
        "run_with_timeout",
        run_with_timeout,
    )

    result = asyncio.run(
        runner_main.execute_shellgei(
            _runner_request(
                shellgei="printf output",
                problem_id="STANDARD-00000001",
            )
        )
    )

    assert result.model_dump() == {
        "protocol_version": 3,
        "result": {
            "status": "completed",
            "stdout": "output",
            "stderr": "",
            "exit_code": 0,
            "timed_out": False,
            "truncated": False,
            "duration_ms": 1,
            "artifact": None,
            "error": None,
        },
    }
    assert calls == [("printf output", "STANDARD-00000001")]


def test_runner_returns_schema_path_and_media_type_with_image_artifact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 画像問題の取得dataへschema由来のpath・MIMEを付けたtyped responseを返すことを確認する。
    class AllowStart:
        def try_acquire(self) -> bool:
            """sandbox開始token取得を常に許可し、Trueを返す。"""
            return True

    async def run_with_timeout(
        _shellgei: str,
        _problem_id: str,
    ) -> ExecutionResult:
        """入力command・IDを使用せず、固定の画像artifact付き結果を返す。"""
        return _completed_result(
            "",
            artifact=ExecutionArtifact(
                path="media/output.jpg",
                media_type="image/jpeg",
                data="encoded-image",
            ),
        )

    artifact_specification = SimpleNamespace(
        path="media/output.jpg",
        media_type="image/jpeg",
    )
    record = SimpleNamespace(
        definition=SimpleNamespace(
            judge=SimpleNamespace(type="image", artifact=artifact_specification)
        )
    )
    monkeypatch.setattr(
        runner_main,
        "get_problem_repository",
        lambda: SimpleNamespace(get=lambda _problem_id: record),
    )
    monkeypatch.setattr(runner_main, "sandbox_start_rate_limiter", AllowStart())
    monkeypatch.setattr(
        runner_main.docker_client,
        "run_with_timeout",
        run_with_timeout,
    )

    result = asyncio.run(
        runner_main.execute_shellgei(_runner_request(problem_id="IMAGE-00000001"))
    )

    assert result.model_dump() == {
        "protocol_version": 3,
        "result": {
            "status": "completed",
            "stdout": "",
            "stderr": "",
            "exit_code": 0,
            "timed_out": False,
            "truncated": False,
            "duration_ms": 1,
            "artifact": {
                "path": "media/output.jpg",
                "media_type": "image/jpeg",
                "data": "encoded-image",
            },
            "error": None,
        },
    }


def test_runner_rejects_unknown_problem_before_admission_or_docker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 未登録問題をadmission token取得やDocker処理より前に404にすることを確認する。
    class UnusedAdmissionControl:
        def try_acquire(self) -> bool:
            """呼び出された場合にtestを失敗させ、token状態は返さない。"""
            raise AssertionError("unknown problems must not consume admission tokens")

    async def unexpected_execution(*_args: object) -> ExecutionResult:
        """Docker実行へ到達した場合にtestを失敗させ、結果は返さない。"""
        raise AssertionError("unknown problems must not reach Docker")

    monkeypatch.setattr(
        runner_main,
        "get_problem_repository",
        lambda: SimpleNamespace(get=lambda _problem_id: None),
    )
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
                _runner_request(
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
    # runner lifespanがrepository読込とDocker poolの開始・終了を所定順で行うことを確認する。
    events: list[str] = []

    class FakeManager:
        def initialize_pool(self) -> None:
            """pool初期化の呼出しをeventへ記録する。"""
            events.append("pool_initialize")

        def begin_shutdown(self) -> None:
            """pool終了開始の呼出しをeventへ記録する。"""
            events.append("pool_begin_shutdown")

        def shutdown_pool(self) -> None:
            """pool破棄の呼出しをeventへ記録する。"""
            events.append("pool_shutdown")

    class FakeDockerClient:
        def close(self) -> None:
            """Docker client終了の呼出しをeventへ記録する。"""
            events.append("docker_client_close")

    monkeypatch.setenv("RUNNER_SHARED_SECRET", VALID_SECRET)
    monkeypatch.setattr(runner_main, "manager", FakeManager())
    monkeypatch.setattr(runner_main, "docker_client", FakeDockerClient())
    monkeypatch.setattr(
        runner_main,
        "load_problem_repository",
        lambda: events.append("repository_load"),
    )

    async def run_lifespan() -> None:
        """runner lifespanへ入り、request受付期間をeventへ記録して終了する。"""
        async with runner_main.lifespan(runner_main.app):
            events.append("serving")

    asyncio.run(run_lifespan())

    assert events == [
        "repository_load",
        "pool_initialize",
        "serving",
        "pool_begin_shutdown",
        "docker_client_close",
        "pool_shutdown",
    ]


def test_runner_startup_stops_before_docker_when_repository_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # repository検証失敗時にDocker poolを初期化せず、runner起動を中止することを確認する。
    events: list[str] = []

    class UnusedManager:
        def initialize_pool(self) -> None:
            """問題data不正時に呼ばれてはならないpool初期化をeventへ記録する。"""
            events.append("pool_initialize")

    def fail_repository_load() -> None:
        """runnerの起動時問題data検証失敗をeventへ記録して例外を送出する。"""
        events.append("repository_load")
        raise RuntimeError("invalid problem data")

    monkeypatch.setenv("RUNNER_SHARED_SECRET", VALID_SECRET)
    monkeypatch.setattr(runner_main, "manager", UnusedManager())
    monkeypatch.setattr(
        runner_main,
        "load_problem_repository",
        fail_repository_load,
    )

    async def run_lifespan() -> None:
        """runner lifespanへ入り、起動処理が受付状態まで進むか確認する。"""
        async with runner_main.lifespan(runner_main.app):
            events.append("serving")

    with pytest.raises(RuntimeError, match="invalid problem data"):
        asyncio.run(run_lifespan())

    assert events == ["repository_load"]


def test_backend_runner_client_sends_only_the_fixed_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # backend clientが認証headerと固定JSON schemaだけをrunnerへ送ることを確認する。
    captured: list[Request] = []

    def fake_urlopen(request: Request, timeout: int) -> FakeResponse:
        """入力requestとtimeoutを記録し、固定runner responseを返す。"""
        assert timeout == runner_client_module.RUNNER_REQUEST_TIMEOUT_SECONDS
        captured.append(request)
        return FakeResponse(_runner_response_bytes("ok"))

    monkeypatch.setenv("RUNNER_SHARED_SECRET", VALID_SECRET)
    client = RunnerClient()
    monkeypatch.setattr(client._opener, "open", fake_urlopen)
    try:
        result = asyncio.run(client.execute("printf ok", "STANDARD-00000001"))
    finally:
        client.close()

    assert result == _completed_result("ok")
    assert len(captured) == 1
    request = captured[0]
    assert request.full_url == f"{RUNNER_BASE_URL}{RUNNER_EXECUTE_PATH}"
    assert request.get_method() == "POST"
    assert request.get_header("Authorization") == f"Bearer {VALID_SECRET}"
    assert isinstance(request.data, bytes)
    assert json.loads(request.data) == {
        "shellgei": "printf ok",
        "problem_id": "STANDARD-00000001",
        "protocol_version": 3,
    }


def test_backend_runner_client_disables_environment_proxies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # proxy環境変数があってもprivate runner通信が直接接続を使用することを確認する。
    configured_handlers: list[object] = []
    captured_requests: list[Request] = []

    class FakeOpener:
        def open(self, request: Request, timeout: int) -> FakeResponse:
            """入力requestとtimeoutを記録し、直接接続の固定responseを返す。"""
            assert timeout == runner_client_module.RUNNER_REQUEST_TIMEOUT_SECONDS
            captured_requests.append(request)
            return FakeResponse(_runner_response_bytes("direct"))

    def fake_build_opener(*handlers: object) -> FakeOpener:
        """入力handler群を記録し、観測用の模擬openerを返す。"""
        configured_handlers.extend(handlers)
        return FakeOpener()

    proxy_url = "http://attacker.invalid:8080"
    for variable in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy"):
        monkeypatch.setenv(variable, proxy_url)
    monkeypatch.setenv("ALL_PROXY", proxy_url)
    monkeypatch.setenv("all_proxy", proxy_url)
    monkeypatch.setenv("NO_PROXY", "")
    monkeypatch.setenv("no_proxy", "")
    monkeypatch.setenv("RUNNER_SHARED_SECRET", VALID_SECRET)
    monkeypatch.setattr(runner_client_module, "build_opener", fake_build_opener)

    client = RunnerClient()
    try:
        result = asyncio.run(client.execute("true", "STANDARD-00000001"))
    finally:
        client.close()

    assert result == _completed_result("direct")
    assert len(configured_handlers) == 1
    proxy_handler = configured_handlers[0]
    assert isinstance(proxy_handler, ProxyHandler)
    assert not hasattr(proxy_handler, "http_open")
    assert not hasattr(proxy_handler, "https_open")
    assert not hasattr(proxy_handler, "all_open")
    assert len(captured_requests) == 1
    assert captured_requests[0].full_url == f"{RUNNER_BASE_URL}{RUNNER_EXECUTE_PATH}"


def test_backend_runner_client_maps_busy_without_accepting_error_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # runnerのHTTP 429をresponse bodyへ依存せずRunnerBusyErrorへ変換することを確認する。
    def fake_urlopen(request: Request, timeout: int) -> FakeResponse:
        """入力request URLを使用してHTTP 429例外を送出し、responseは返さない。"""
        raise HTTPError(request.full_url, 429, "busy", Message(), None)

    monkeypatch.setenv("RUNNER_SHARED_SECRET", VALID_SECRET)
    client = RunnerClient()
    monkeypatch.setattr(client._opener, "open", fake_urlopen)
    try:
        with pytest.raises(RunnerBusyError):
            asyncio.run(client.execute("true", "STANDARD-00000001"))
    finally:
        client.close()


@pytest.mark.parametrize(
    "payload",
    [
        b"not-json",
        b'{"stdout":"ok","artifact":null}',
        b'{"protocol_version":2,"result":{"stdout":"ok"}}',
        b'{"protocol_version":3,"result":{"stdout":"ok"},"extra":"value"}',
        b'{"protocol_version":3,"result":{"stdout":"ok","extra":"value"}}',
    ],
)
def test_backend_runner_client_rejects_invalid_responses(
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
) -> None:
    # JSON不正、field不正、型不正のrunner responseをunavailableとして拒否することを確認する。
    monkeypatch.setenv("RUNNER_SHARED_SECRET", VALID_SECRET)
    client = RunnerClient()
    monkeypatch.setattr(
        client._opener,
        "open",
        lambda *_args, **_kwargs: FakeResponse(payload),
    )
    try:
        with pytest.raises(RunnerUnavailableError):
            asyncio.run(client.execute("true", "STANDARD-00000001"))
    finally:
        client.close()


def test_backend_runner_client_rejects_oversized_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # protocol上限を超えるrunner responseを読込後に拒否することを確認する。
    oversized = b"x" * (runner_client_module.RUNNER_RESPONSE_LIMIT_BYTES + 1)
    monkeypatch.setenv("RUNNER_SHARED_SECRET", VALID_SECRET)
    client = RunnerClient()
    monkeypatch.setattr(
        client._opener,
        "open",
        lambda *_args, **_kwargs: FakeResponse(oversized),
    )
    try:
        with pytest.raises(RunnerUnavailableError):
            asyncio.run(client.execute("true", "STANDARD-00000001"))
    finally:
        client.close()


def test_public_api_preserves_artifact_data_and_media_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # typed runner artifactを既存画像dataと追加MIME fieldへ変換して返すことを確認する。
    saved_entries: list[ExecutionLogEntry] = []

    async def execute(_shellgei: str, _problem_id: str) -> ExecutionResult:
        """入力command・IDを使用せず、固定JPEG artifact付き実行結果を返す。"""
        return _completed_result(
            "",
            artifact=ExecutionArtifact(
                path="media/output.jpg",
                media_type="image/jpeg",
                data="encoded-image",
            ),
        )

    def judge(_execution: ExecutionResult, _problem_id: str) -> JudgeResult:
        """入力を使用せず、固定の模擬判定結果を返す。"""
        return JudgeResult(verdict=JudgeVerdict.ACCEPTED)

    async def persist(entry: ExecutionLogEntry) -> int:
        """保存entryを記録し、固定保存IDを返す。"""
        saved_entries.append(entry)
        return 42

    monkeypatch.setattr(
        api_shellgei,
        "get_problem_repository",
        lambda: SimpleNamespace(get=lambda _problem_id: object()),
    )
    monkeypatch.setattr(api_shellgei.runner_gateway, "execute", execute)
    monkeypatch.setattr(api_shellgei.shellgei_judge, "judge", judge)
    monkeypatch.setattr(api_shellgei, "save_execution_log_async", persist)

    response = asyncio.run(
        api_shellgei.post_shellgei(
            ShellgeiData(shellgei="true", problem_id="IMAGE-00000001")
        )
    )

    assert response.output == ""
    assert response.image == "encoded-image"
    assert response.image_media_type == "image/jpeg"
    assert response.judge == "1"
    assert len(saved_entries) == 1
    assert "artifact" not in saved_entries[0].model_dump()
    assert "encoded-image" not in str(saved_entries[0].model_dump())


def test_public_api_maps_runner_failure_without_database_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # runner停止をpublic error responseへ変換し、DB保存を行わないことを確認する。
    async def unavailable(*_args: object) -> ExecutionResult:
        """runner停止を再現するRunnerUnavailableErrorを送出する。"""
        raise RunnerUnavailableError("unavailable")

    async def unused_persistence(*_args: object) -> int:
        """DB保存へ到達した場合にtestを失敗させ、IDは返さない。"""
        raise AssertionError("runner failure must not reach database persistence")

    monkeypatch.setattr(
        api_shellgei,
        "get_problem_repository",
        lambda: SimpleNamespace(get=lambda _problem_id: object()),
    )
    monkeypatch.setattr(api_shellgei.runner_gateway, "execute", unavailable)
    monkeypatch.setattr(
        api_shellgei,
        "save_execution_log_async",
        unused_persistence,
    )

    response = asyncio.run(
        api_shellgei.post_shellgei(
            ShellgeiData(shellgei="true", problem_id="STANDARD-00000001")
        )
    )

    assert response.output == "Error: runner is unavailable."
    assert response.id == "-1"
    assert response.image == ""
    assert response.judge == "4"


def test_public_api_preserves_busy_response_for_runner_capacity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # runner混雑を既存public responseへ変換し、DB保存を行わないことを確認する。
    async def busy(*_args: object) -> ExecutionResult:
        """runner混雑を再現するRunnerBusyErrorを送出する。"""
        raise RunnerBusyError("busy")

    async def unused_persistence(*_args: object) -> int:
        """混雑時にDB保存へ到達した場合にtestを失敗させ、IDは返さない。"""
        raise AssertionError("busy response must not reach database persistence")

    monkeypatch.setattr(
        api_shellgei,
        "get_problem_repository",
        lambda: SimpleNamespace(get=lambda _problem_id: object()),
    )
    monkeypatch.setattr(api_shellgei.runner_gateway, "execute", busy)
    monkeypatch.setattr(
        api_shellgei,
        "save_execution_log_async",
        unused_persistence,
    )

    response = asyncio.run(
        api_shellgei.post_shellgei(
            ShellgeiData(shellgei="true", problem_id="STANDARD-00000001")
        )
    )

    assert response.output == "Error: server is busy."
    assert response.id == "-1"
    assert response.image == ""
    assert response.judge == "4"
