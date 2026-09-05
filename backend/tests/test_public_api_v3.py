import asyncio
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from starlette.types import Message, Scope

import soj_backend.api.api_shellgei as api_shellgei
import soj_backend.main as backend_main
from soj_shared.models.execution import (
    ExecutionArtifact,
    ExecutionResult,
    ExecutionStatus,
)
from soj_backend.models.public_api import MAX_PUBLIC_SUBMISSION_RESPONSE_BYTES
from soj_shared.submission_status import SubmissionPersistenceStatus, SubmissionStatus
from soj_backend.models.submission import SubmissionResult
from soj_backend.judge import JudgeReason, JudgeResult, JudgeVerdict
from soj_shared.request_context import current_request_id
from soj_shared.structured_logging import SAFE_EVENT_LOGGER_NAME


PROBLEM_ID = "STANDARD-00000001"
SUBMITTED_AT = datetime(2026, 9, 2, 12, 34, 56, tzinfo=ZoneInfo("Asia/Tokyo"))


def _completed_submission(
    *,
    execution: ExecutionResult | None = None,
    judgment: JudgeResult | None = None,
) -> SubmissionResult:
    """任意の実行・判定から、保存ID付きの完了提出結果を返す。"""
    return SubmissionResult(
        status=SubmissionStatus.COMPLETED,
        submitted_at=SUBMITTED_AT,
        execution=execution
        or ExecutionResult(
            status=ExecutionStatus.COMPLETED,
            stdout="ok",
            stderr="",
            exit_code=0,
            timed_out=False,
            truncated=False,
            duration_ms=12,
            artifact=None,
            error=None,
        ),
        judgment=judgment or JudgeResult(verdict=JudgeVerdict.ACCEPTED),
        log_id=42,
        persistence=SubmissionPersistenceStatus.SAVED,
    )


def _rejected_submission(status: SubmissionStatus) -> SubmissionResult:
    """入力statusから、実行・判定・保存を行っていない提出結果を返す。"""
    return SubmissionResult(
        status=status,
        submitted_at=SUBMITTED_AT,
        execution=None,
        judgment=None,
        persistence=SubmissionPersistenceStatus.NOT_ATTEMPTED,
    )


def _post_json(
    path: str,
    payload: dict[str, object],
    extra_headers: list[tuple[bytes, bytes]] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    """入力path・JSON・任意headerでASGI POSTし、status・header・結合済みbodyを返す。"""

    async def scenario() -> tuple[int, dict[str, str], bytes]:
        """ASGI messageを送受信し、1回のHTTP応答を組み立てて返す。"""
        messages: list[Message] = []
        request_delivered = False
        request_body = json.dumps(payload).encode("utf-8")

        async def receive() -> Message:
            """最初の呼出しでrequest bodyを返し、その後は切断を通知する。"""
            nonlocal request_delivered
            if request_delivered:
                return {"type": "http.disconnect"}
            request_delivered = True
            return {
                "type": "http.request",
                "body": request_body,
                "more_body": False,
            }

        async def send(message: Message) -> None:
            """applicationが送信したresponse messageを順番どおり記録する。"""
            messages.append(message)

        scope: Scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "root_path": "",
            "headers": [
                (b"host", b"backend:8000"),
                (b"content-type", b"application/json"),
                (b"content-length", str(len(request_body)).encode("ascii")),
                *(extra_headers or []),
            ],
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
        response_body = b"".join(
            message.get("body", b"")
            for message in messages
            if message["type"] == "http.response.body"
        )
        return response_start["status"], response_headers, response_body

    return asyncio.run(scenario())


def test_submission_uses_server_request_id_and_logs_only_safe_fields(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # client指定IDを無視してserver生成IDをresponse・contextへ渡し、commandや接続情報をlogへ残さない。
    observed_request_ids: list[str | None] = []

    async def submit(_shellgei: str, _problem_id: str) -> SubmissionResult:
        """現在のrequest IDを記録し、固定のrunner混雑結果を返す。"""
        observed_request_ids.append(current_request_id())
        return _rejected_submission(SubmissionStatus.RUNNER_BUSY)

    caplog.set_level("INFO", logger=SAFE_EVENT_LOGGER_NAME)
    monkeypatch.setattr(api_shellgei.submit_solution_service, "submit", submit)

    status, headers, _ = _post_json(
        "/api/v3/submissions",
        {"shellgei": "printf PRIVATE-COMMAND", "problem_id": PROBLEM_ID},
        extra_headers=[
            (b"x-request-id", b"attacker-request-id"),
            (b"origin", b"https://shellgei-online-judge.com"),
        ],
    )

    response_request_id = headers["x-request-id"]
    assert status == 429
    assert re.fullmatch(r"[0-9a-f]{32}", response_request_id)
    assert headers["access-control-expose-headers"] == "X-Request-ID"
    assert observed_request_ids == [response_request_id]
    event = json.loads(caplog.records[-1].message)
    assert event == {
        "event": "http_request_completed",
        "component": "backend_http",
        "request_id": response_request_id,
        "endpoint": "v3_submission",
        "http_status": 429,
        "duration_ms": event["duration_ms"],
    }
    assert event["duration_ms"] >= 0
    serialized_event = caplog.records[-1].message
    assert "PRIVATE-COMMAND" not in serialized_event
    assert "attacker-request-id" not in serialized_event
    assert "127.0.0.1" not in serialized_event


def test_legacy_submission_also_returns_server_request_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 移行中のlegacy提出APIにも、v3と同じserver生成request IDをresponseで返す。
    async def submit(_shellgei: str, _problem_id: str) -> SubmissionResult:
        """入力を使わず、legacy response変換用のrunner混雑結果を返す。"""
        return _rejected_submission(SubmissionStatus.RUNNER_BUSY)

    monkeypatch.setattr(api_shellgei.submit_solution_service, "submit", submit)

    status, headers, _ = _post_json(
        "/api/shellgei",
        {"shellgei": "true", "problem_id": PROBLEM_ID},
    )

    assert status == 200
    assert re.fullmatch(r"[0-9a-f]{32}", headers["x-request-id"])


def test_v3_submission_returns_typed_success_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 正常提出をtyped verdict・execution・保存ID付きのHTTP 200として返すことを確認する。
    calls: list[tuple[str, str]] = []

    async def submit(shellgei: str, problem_id: str) -> SubmissionResult:
        """入力command・IDを記録し、固定の正常提出結果を返す。"""
        calls.append((shellgei, problem_id))
        return _completed_submission()

    monkeypatch.setattr(api_shellgei.submit_solution_service, "submit", submit)

    status, headers, body = _post_json(
        "/api/v3/submissions",
        {"shellgei": "printf ok", "problem_id": PROBLEM_ID},
    )
    response = json.loads(body)

    assert calls == [("printf ok", PROBLEM_ID)]
    assert status == 200
    assert headers["cache-control"] == "no-store"
    assert headers["x-content-type-options"] == "nosniff"
    assert response == {
        "api_version": 3,
        "submission_id": 42,
        "submitted_at": "2026-09-02T12:34:56+09:00",
        "verdict": "accepted",
        "reason": None,
        "execution": {
            "status": "completed",
            "stdout": "ok",
            "stderr": "",
            "exit_code": 0,
            "timed_out": False,
            "truncated": False,
            "duration_ms": 12,
        },
        "artifact": None,
        "persistence": "saved",
    }


def test_v3_submission_exposes_safe_execution_failure_without_internal_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # sandbox内部error文字列を公開せず、typed status・verdict・reasonだけを返すことを確認する。
    execution = ExecutionResult(
        status=ExecutionStatus.ERROR,
        stdout="",
        stderr="",
        exit_code=None,
        timed_out=False,
        truncated=False,
        duration_ms=3,
        artifact=None,
        error="sensitive internal Docker detail",
    )
    judgment = JudgeResult(
        verdict=JudgeVerdict.EXECUTION_FAILURE,
        reason=JudgeReason.EXECUTION_ERROR,
    )

    async def submit(_shellgei: str, _problem_id: str) -> SubmissionResult:
        """入力を使わず、内部errorを持つ固定の実行失敗結果を返す。"""
        return _completed_submission(execution=execution, judgment=judgment)

    monkeypatch.setattr(api_shellgei.submit_solution_service, "submit", submit)

    status, _, body = _post_json(
        "/api/v3/submissions",
        {"shellgei": "false", "problem_id": PROBLEM_ID},
    )
    response = json.loads(body)

    assert status == 200
    assert response["verdict"] == "execution_failure"
    assert response["reason"] == "execution_error"
    assert response["execution"]["status"] == "error"
    assert "error" not in response["execution"]
    assert b"sensitive internal Docker detail" not in body


@pytest.mark.parametrize(
    ("submission_status", "expected_http", "expected_code"),
    [
        (SubmissionStatus.PROBLEM_NOT_FOUND, 404, "problem_not_found"),
        (SubmissionStatus.RUNNER_BUSY, 429, "runner_busy"),
        (SubmissionStatus.RUNNER_UNAVAILABLE, 503, "runner_unavailable"),
    ],
)
def test_v3_submission_maps_application_failures_to_http_status(
    monkeypatch: pytest.MonkeyPatch,
    submission_status: SubmissionStatus,
    expected_http: int,
    expected_code: str,
) -> None:
    # problem未登録・runner混雑・停止を、それぞれ404・429・503と安全なcodeへ変換する。
    async def submit(_shellgei: str, _problem_id: str) -> SubmissionResult:
        """入力を使わず、parameterで指定された未完了提出結果を返す。"""
        return _rejected_submission(submission_status)

    monkeypatch.setattr(api_shellgei.submit_solution_service, "submit", submit)

    status, headers, body = _post_json(
        "/api/v3/submissions",
        {"shellgei": "true", "problem_id": PROBLEM_ID},
    )
    response = json.loads(body)

    assert status == expected_http
    assert response["api_version"] == 3
    assert response["code"] == expected_code
    assert headers["cache-control"] == "no-store"
    assert headers["x-content-type-options"] == "nosniff"
    if expected_http in {429, 503}:
        assert headers["retry-after"] == "1"
    else:
        assert "retry-after" not in headers


@pytest.mark.parametrize(
    "payload",
    [
        {"problem_id": PROBLEM_ID},
        {"shellgei": "", "problem_id": PROBLEM_ID},
        {"shellgei": "true", "problem_id": PROBLEM_ID, "unknown": "value"},
    ],
)
def test_v3_submission_rejects_invalid_requests_before_use_case(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, object],
) -> None:
    # command欠落・空文字・追加fieldをHTTP 422とし、use caseを呼ばないことを確認する。
    async def unused(_shellgei: str, _problem_id: str) -> SubmissionResult:
        """validationを通過して呼ばれた場合にtestを失敗させる。"""
        raise AssertionError("invalid request must not reach the use case")

    monkeypatch.setattr(api_shellgei.submit_solution_service, "submit", unused)

    status, headers, _ = _post_json("/api/v3/submissions", payload)

    assert status == 422
    assert headers["cache-control"] == "no-store"
    assert headers["x-content-type-options"] == "nosniff"
    assert re.fullmatch(r"[0-9a-f]{32}", headers["x-request-id"])


def test_v3_openapi_fixes_typed_contract_and_error_statuses() -> None:
    # OpenAPIがv3 DTO、field上限、typed enum、200・404・422・429・503を公開することを確認する。
    schema = backend_main.app.openapi()
    operation = schema["paths"]["/api/v3/submissions"]["post"]
    schemas = schema["components"]["schemas"]

    assert operation["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/SubmitSolutionRequestV3"
    }
    assert set(operation["responses"]) >= {"200", "404", "422", "429", "503"}
    assert schemas["SubmitSolutionRequestV3"]["additionalProperties"] is False
    assert (
        schemas["SubmitSolutionRequestV3"]["properties"]["shellgei"]["maxLength"]
        == 1000
    )
    assert (
        schemas["PublicExecutionResultV3"]["properties"]["stdout"]["maxLength"] == 1000
    )
    assert "error" not in schemas["PublicExecutionResultV3"]["properties"]
    assert schemas["PublicArtifactV3"]["properties"]["data"]["maxLength"] == 1_000_000
    assert set(schemas["JudgeVerdict"]["enum"]) >= {
        "accepted",
        "wrong_answer",
        "execution_failure",
    }


def test_v3_submission_response_is_bounded_and_omits_artifact_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 最大Base64 artifactでも公開上限内となり、内部取得pathを返さないことを確認する。
    execution = ExecutionResult(
        status=ExecutionStatus.COMPLETED,
        stdout="x" * 1000,
        stderr="",
        exit_code=0,
        timed_out=False,
        truncated=False,
        duration_ms=1,
        artifact=ExecutionArtifact(
            path="media/output.jpg",
            media_type="image/jpeg",
            data="A" * 1_000_000,
        ),
        error=None,
    )

    async def submit(_shellgei: str, _problem_id: str) -> SubmissionResult:
        """入力を使わず、最大長artifactを持つ固定の正常提出結果を返す。"""
        return _completed_submission(execution=execution)

    monkeypatch.setattr(api_shellgei.submit_solution_service, "submit", submit)

    status, headers, body = _post_json(
        "/api/v3/submissions",
        {"shellgei": "true", "problem_id": PROBLEM_ID},
    )
    response = json.loads(body)

    assert status == 200
    assert len(body) <= MAX_PUBLIC_SUBMISSION_RESPONSE_BYTES
    assert int(headers["content-length"]) == len(body)
    assert response["artifact"]["media_type"] == "image/jpeg"
    assert "path" not in response["artifact"]


def test_legacy_submission_response_also_disables_caching(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 移行中のlegacy提出responseにもcommand・出力をcacheさせないheaderを付けることを確認する。
    async def submit(_shellgei: str, _problem_id: str) -> SubmissionResult:
        """入力を使わず、legacy mapper用の固定正常提出結果を返す。"""
        return _completed_submission()

    monkeypatch.setattr(api_shellgei.submit_solution_service, "submit", submit)

    status, headers, _ = _post_json(
        "/api/shellgei",
        {"shellgei": "true", "problem_id": PROBLEM_ID},
    )

    assert status == 200
    assert headers["cache-control"] == "no-store"
    assert headers["x-content-type-options"] == "nosniff"
