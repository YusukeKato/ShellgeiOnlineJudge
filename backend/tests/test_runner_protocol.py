import asyncio

import pytest
from pydantic import ValidationError

from scripts.runner_protocol import (
    MAX_RUNNER_IMAGE_BASE64_CHARS,
    MAX_RUNNER_OUTPUT_CHARS,
    RUNNER_PROTOCOL_VERSION,
    ExecutionResult,
    RunnerExecutionRequest,
    RunnerExecutionResponse,
    RunnerGateway,
)


def test_runner_protocol_round_trip_preserves_versioned_request_and_result() -> None:
    # version付きrequest・responseをJSON往復し、command・ID・実行結果が保持されることを確認する。
    request = RunnerExecutionRequest(
        protocol_version=RUNNER_PROTOCOL_VERSION,
        shellgei="printf ok",
        problem_id="STANDARD-00000001",
    )
    response = RunnerExecutionResponse(
        protocol_version=RUNNER_PROTOCOL_VERSION,
        result=ExecutionResult(output="ok", image="base64-image"),
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
            "shellgei": "true",
            "problem_id": "STANDARD-00000001",
        },
        {
            "protocol_version": 1,
            "shellgei": "true",
            "problem_id": "STANDARD-00000001",
            "unknown": "value",
        },
    ],
)
def test_runner_request_rejects_missing_wrong_version_and_unknown_fields(
    payload: dict[str, object],
) -> None:
    # version欠落・未知version・追加fieldを内部request schemaが拒否することを確認する。
    with pytest.raises(ValidationError):
        RunnerExecutionRequest.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"result": {"output": "ok", "image": ""}},
        {
            "protocol_version": 2,
            "result": {"output": "ok", "image": ""},
        },
        {
            "protocol_version": 1,
            "result": {"output": "ok", "image": "", "unknown": "value"},
        },
        {
            "protocol_version": 1,
            "result": {"output": "ok", "image": ""},
            "unknown": "value",
        },
    ],
)
def test_runner_response_rejects_missing_wrong_version_and_unknown_fields(
    payload: dict[str, object],
) -> None:
    # version欠落・未知versionと、response内外の追加fieldを拒否することを確認する。
    with pytest.raises(ValidationError):
        RunnerExecutionResponse.model_validate(payload)


def test_execution_result_is_immutable_and_enforces_wire_limits() -> None:
    # typed resultが変更不能で、文字列・画像のprotocol上限超過を拒否することを確認する。
    result = ExecutionResult(output="ok", image="")

    with pytest.raises(ValidationError):
        result.output = "changed"
    with pytest.raises(ValidationError):
        ExecutionResult(output="x" * (MAX_RUNNER_OUTPUT_CHARS + 1), image="")
    with pytest.raises(ValidationError):
        ExecutionResult(
            output="ok",
            image="x" * (MAX_RUNNER_IMAGE_BASE64_CHARS + 1),
        )


def test_runner_gateway_returns_execution_result_without_sequence_contract() -> None:
    # Gateway interfaceがlistではなくExecutionResultを返す非同期境界であることを確認する。
    class FakeGateway:
        async def execute(self, shellgei: str, problem_id: str) -> ExecutionResult:
            """入力command・IDを結果へ埋め込み、typed ExecutionResultを返す。"""
            return ExecutionResult(output=f"{problem_id}:{shellgei}", image="")

    gateway: RunnerGateway = FakeGateway()
    result = asyncio.run(gateway.execute("true", "STANDARD-00000001"))

    assert result.output == "STANDARD-00000001:true"
    assert result.image == ""
