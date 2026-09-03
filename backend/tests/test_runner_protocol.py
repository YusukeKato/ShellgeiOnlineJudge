import asyncio

import pytest
from pydantic import ValidationError

from scripts.runner_protocol import (
    MAX_CAPTURED_OUTPUT_CHARS,
    MAX_RUNNER_IMAGE_BASE64_CHARS,
    RUNNER_PROTOCOL_VERSION,
    ExecutionArtifact,
    ExecutionResult,
    ExecutionStatus,
    RunnerExecutionRequest,
    RunnerExecutionResponse,
    RunnerGateway,
)

TEST_PROBLEM_REVISION = "a" * 64
TEST_REQUEST_ID = "b" * 32


def _completed_result(
    stdout: str = "ok",
    *,
    stderr: str = "",
    artifact: ExecutionArtifact | None = None,
) -> ExecutionResult:
    # 任意の分離出力とartifactから、正常完了した構造化実行結果を返す。
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


def test_runner_protocol_round_trip_preserves_versioned_request_and_result() -> None:
    # versionとproblem revision付きrequest・responseをJSON往復し、実行内容が保持されることを確認する。
    request = RunnerExecutionRequest(
        protocol_version=RUNNER_PROTOCOL_VERSION,
        request_id=TEST_REQUEST_ID,
        problem_revision=TEST_PROBLEM_REVISION,
        shellgei="printf ok",
        problem_id="STANDARD-00000001",
    )
    response = RunnerExecutionResponse(
        protocol_version=RUNNER_PROTOCOL_VERSION,
        request_id=TEST_REQUEST_ID,
        problem_revision=TEST_PROBLEM_REVISION,
        result=_completed_result(
            artifact=ExecutionArtifact(
                path="media/output.jpg",
                media_type="image/jpeg",
                data="base64-image",
            ),
        ),
    )

    assert RunnerExecutionRequest.model_validate_json(request.model_dump_json()) == (
        request
    )
    assert RunnerExecutionResponse.model_validate_json(response.model_dump_json()) == (
        response
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"shellgei": "true", "problem_id": "STANDARD-00000001"},
        {
            "protocol_version": 2,
            "request_id": TEST_REQUEST_ID,
            "problem_revision": TEST_PROBLEM_REVISION,
            "shellgei": "true",
            "problem_id": "STANDARD-00000001",
        },
        {
            "protocol_version": 3,
            "request_id": TEST_REQUEST_ID,
            "problem_revision": TEST_PROBLEM_REVISION,
            "shellgei": "true",
            "problem_id": "STANDARD-00000001",
            "unknown": "value",
        },
        {
            "protocol_version": 3,
            "request_id": TEST_REQUEST_ID,
            "problem_revision": "not-a-sha256-digest",
            "shellgei": "true",
            "problem_id": "STANDARD-00000001",
        },
        {
            "protocol_version": 3,
            "request_id": "attacker-controlled",
            "problem_revision": TEST_PROBLEM_REVISION,
            "shellgei": "true",
            "problem_id": "STANDARD-00000001",
        },
    ],
)
def test_runner_request_rejects_missing_wrong_version_and_unknown_fields(
    payload: dict[str, object],
) -> None:
    # version欠落・未知version・不正ID/revision・追加fieldを内部request schemaが拒否する。
    with pytest.raises(ValidationError):
        RunnerExecutionRequest.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {
            "result": {
                "status": "completed",
                "stdout": "ok",
                "stderr": "",
                "exit_code": 0,
                "timed_out": False,
                "truncated": False,
                "duration_ms": 1,
                "artifact": None,
                "error": None,
            }
        },
        {
            "protocol_version": 2,
            "request_id": TEST_REQUEST_ID,
            "problem_revision": TEST_PROBLEM_REVISION,
            "result": {
                "status": "completed",
                "stdout": "ok",
                "stderr": "",
                "exit_code": 0,
                "timed_out": False,
                "truncated": False,
                "duration_ms": 1,
                "artifact": None,
                "error": None,
            },
        },
        {
            "protocol_version": 3,
            "request_id": TEST_REQUEST_ID,
            "problem_revision": TEST_PROBLEM_REVISION,
            "result": {
                "status": "completed",
                "stdout": "ok",
                "stderr": "",
                "exit_code": 0,
                "timed_out": False,
                "truncated": False,
                "duration_ms": 1,
                "artifact": None,
                "error": None,
                "unknown": "value",
            },
        },
        {
            "protocol_version": 3,
            "request_id": TEST_REQUEST_ID,
            "problem_revision": TEST_PROBLEM_REVISION,
            "result": {
                "status": "completed",
                "stdout": "ok",
                "stderr": "",
                "exit_code": 0,
                "timed_out": False,
                "truncated": False,
                "duration_ms": 1,
                "artifact": None,
                "error": None,
            },
            "unknown": "value",
        },
        {
            "protocol_version": 3,
            "request_id": TEST_REQUEST_ID,
            "problem_revision": "A" * 64,
            "result": _completed_result().model_dump(),
        },
        {
            "protocol_version": 3,
            "request_id": "invalid-request-id",
            "problem_revision": TEST_PROBLEM_REVISION,
            "result": _completed_result().model_dump(),
        },
    ],
)
def test_runner_response_rejects_missing_wrong_version_and_unknown_fields(
    payload: dict[str, object],
) -> None:
    # version欠落・未知version・不正ID/revisionと、response内外の追加fieldを拒否する。
    with pytest.raises(ValidationError):
        RunnerExecutionResponse.model_validate(payload)


def test_execution_result_is_immutable_and_enforces_wire_limits() -> None:
    # typed resultが変更不能で、文字列・画像のprotocol上限超過を拒否することを確認する。
    result = _completed_result()

    with pytest.raises(ValidationError):
        result.stdout = "changed"
    with pytest.raises(ValidationError):
        _completed_result(stdout="x" * (MAX_CAPTURED_OUTPUT_CHARS + 1))
    with pytest.raises(ValidationError):
        ExecutionArtifact(
            path="media/output.jpg",
            media_type="image/jpeg",
            data="x" * (MAX_RUNNER_IMAGE_BASE64_CHARS + 1),
        )


@pytest.mark.parametrize(
    "updates",
    [
        {"exit_code": None},
        {"timed_out": True},
        {"truncated": True},
        {"error": "unexpected"},
        {
            "status": ExecutionStatus.TIMED_OUT,
            "timed_out": False,
            "exit_code": None,
        },
        {
            "status": ExecutionStatus.OUTPUT_LIMIT,
            "truncated": False,
            "exit_code": None,
        },
        {
            "status": ExecutionStatus.ERROR,
            "exit_code": None,
            "error": None,
        },
    ],
)
def test_execution_result_rejects_inconsistent_status_fields(
    updates: dict[str, object],
) -> None:
    # statusと終了code・timeout・切り詰め・errorが矛盾する組合せを拒否する。
    payload = _completed_result().model_dump()
    payload.update(updates)

    with pytest.raises(ValidationError):
        ExecutionResult.model_validate(payload)


def test_execution_result_enforces_combined_output_limit() -> None:
    # stdoutとstderrが個別上限内でも、合計文字数上限を超える結果を拒否する。
    with pytest.raises(ValidationError):
        _completed_result(
            stdout="x" * MAX_CAPTURED_OUTPUT_CHARS,
            stderr="y",
        )


def test_runner_gateway_returns_execution_result_without_sequence_contract() -> None:
    # Gateway interfaceがlistではなくExecutionResultを返す非同期境界であることを確認する。
    class FakeGateway:
        async def execute(self, shellgei: str, problem_id: str) -> ExecutionResult:
            """入力command・IDを結果へ埋め込み、typed ExecutionResultを返す。"""
            return _completed_result(stdout=f"{problem_id}:{shellgei}")

    gateway: RunnerGateway = FakeGateway()
    result = asyncio.run(gateway.execute("true", "STANDARD-00000001"))

    assert result.stdout == "STANDARD-00000001:true"
    assert result.artifact is None
