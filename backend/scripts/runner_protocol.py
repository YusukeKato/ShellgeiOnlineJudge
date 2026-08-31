import os
import re
from typing import Final, Literal, Protocol

from pydantic import BaseModel, ConfigDict

from models.execution import (
    MAX_CAPTURED_OUTPUT_CHARS,
    MAX_RUNNER_IMAGE_BASE64_CHARS,
    ExecutionArtifact,
    ExecutionResult,
    ExecutionStatus,
)
from models.model_shellgei import ShellgeiData


__all__ = [
    "MAX_RUNNER_IMAGE_BASE64_CHARS",
    "MAX_CAPTURED_OUTPUT_CHARS",
    "ExecutionArtifact",
    "ExecutionResult",
    "ExecutionStatus",
]

RUNNER_EXECUTE_PATH = "/internal/execute"
RUNNER_HEALTH_PATH = "/internal/health"
RUNNER_SHARED_SECRET_ENVIRONMENT = "RUNNER_SHARED_SECRET"
RUNNER_SHARED_SECRET_PATTERN = re.compile(r"^[A-Za-z0-9_-]{32,256}$")
RUNNER_INSECURE_EXAMPLE_SECRET = "replace-with-at-least-32-random-characters"
RUNNER_PROTOCOL_VERSION: Final = 3


class RunnerConfigurationError(RuntimeError):
    """Raised when the private runner channel is not configured safely."""


class RunnerExecutionRequest(ShellgeiData):
    """version、command、problem IDを保持する不変な内部runner request。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol_version: Literal[3]


class RunnerExecutionResponse(BaseModel):
    """protocol versionとtyped resultを保持する不変な内部runner response。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol_version: Literal[3]
    result: ExecutionResult


class RunnerGateway(Protocol):
    """backendからprivate runnerへ実行を依頼する非同期境界。"""

    async def execute(self, shellgei: str, problem_id: str) -> ExecutionResult:
        """入力commandとproblem IDをrunnerへ送り、typed実行結果を返す。"""
        ...


def get_runner_shared_secret() -> str:
    """環境変数の共有secretを検証して返し、不正なら設定例外を送出する。"""
    secret = os.getenv(RUNNER_SHARED_SECRET_ENVIRONMENT, "")
    if (
        not RUNNER_SHARED_SECRET_PATTERN.fullmatch(secret)
        or secret == RUNNER_INSECURE_EXAMPLE_SECRET
    ):
        raise RunnerConfigurationError(
            f"{RUNNER_SHARED_SECRET_ENVIRONMENT} must contain 32 to 256 "
            "ASCII letters, digits, underscores, or hyphens"
        )
    return secret
