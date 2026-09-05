import os
import re
from enum import Enum
from typing import Annotated, Final, Literal, Protocol

from pydantic import BaseModel, ConfigDict, StringConstraints

from soj_shared.models.execution import (
    MAX_CAPTURED_OUTPUT_CHARS,
    MAX_RUNNER_IMAGE_BASE64_CHARS,
    ExecutionArtifact,
    ExecutionResult,
    ExecutionStatus,
)
from soj_shared.submission_request import ShellgeiData
from soj_shared.request_context import RequestId


__all__ = [
    "MAX_RUNNER_IMAGE_BASE64_CHARS",
    "MAX_CAPTURED_OUTPUT_CHARS",
    "ExecutionArtifact",
    "ExecutionResult",
    "ExecutionStatus",
]

RUNNER_EXECUTE_PATH = "/internal/execute"
RUNNER_HEALTH_PATH = "/internal/health"
RUNNER_READINESS_PATH = "/internal/ready"
RUNNER_SHARED_SECRET_ENVIRONMENT = "RUNNER_SHARED_SECRET"
RUNNER_SHARED_SECRET_PATTERN = re.compile(r"^[A-Za-z0-9_-]{32,256}$")
RUNNER_INSECURE_EXAMPLE_SECRET = "replace-with-at-least-32-random-characters"
RUNNER_PROTOCOL_VERSION: Final = 3
PROBLEM_REVISION_PATTERN_TEXT = r"^[0-9a-f]{64}$"
ProblemRevision = Annotated[
    str,
    StringConstraints(
        min_length=64,
        max_length=64,
        pattern=PROBLEM_REVISION_PATTERN_TEXT,
    ),
]


class RunnerConfigurationError(RuntimeError):
    """Raised when the private runner channel is not configured safely."""


class RunnerUnavailableError(RuntimeError):
    """private runnerが検証済み実行結果を返せない場合に送出する。"""


class RunnerBusyError(RuntimeError):
    """private runnerが新しい実行を受け付けられない場合に送出する。"""


class RunnerExecutionRequest(ShellgeiData):
    """request ID、version、problem revision、command、problem IDを保持する不変request。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol_version: Literal[3]
    request_id: RequestId
    problem_revision: ProblemRevision


class RunnerExecutionResponse(BaseModel):
    """request ID、protocol version、problem revision、typed resultを保持する不変response。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol_version: Literal[3]
    request_id: RequestId
    problem_revision: ProblemRevision
    result: ExecutionResult


class RunnerReadinessStatus(str, Enum):
    """runnerが実行受付可能か、再起動が必要な劣化状態かを表す。"""

    READY = "ready"
    DEGRADED = "degraded"


class RunnerReadinessResponse(BaseModel):
    """内部protocol・problem revisionとpool readinessを保持する。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol_version: Literal[3]
    problem_revision: ProblemRevision
    status: RunnerReadinessStatus


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
