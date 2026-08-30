import os
import re
from pathlib import PurePosixPath
from typing import Final, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from models.model_shellgei import ShellgeiData
from models.problem import ImageMediaType, MAX_PROBLEM_PATH_BYTES

RUNNER_EXECUTE_PATH = "/internal/execute"
RUNNER_HEALTH_PATH = "/internal/health"
RUNNER_SHARED_SECRET_ENVIRONMENT = "RUNNER_SHARED_SECRET"
RUNNER_SHARED_SECRET_PATTERN = re.compile(r"^[A-Za-z0-9_-]{32,256}$")
RUNNER_INSECURE_EXAMPLE_SECRET = "replace-with-at-least-32-random-characters"
RUNNER_PROTOCOL_VERSION: Final = 2
MAX_RUNNER_OUTPUT_CHARS = 1_003
MAX_RUNNER_IMAGE_BASE64_CHARS = 1_000_000


class RunnerConfigurationError(RuntimeError):
    """Raised when the private runner channel is not configured safely."""


class RunnerExecutionRequest(ShellgeiData):
    """version、command、problem IDを保持する不変な内部runner request。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol_version: Literal[2]


class ExecutionArtifact(BaseModel):
    """runnerが取得した画像artifactのpath・MIME・Base64 dataを不変に保持する。"""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    path: str = Field(max_length=MAX_PROBLEM_PATH_BYTES)
    media_type: ImageMediaType
    data: str = Field(max_length=MAX_RUNNER_IMAGE_BASE64_CHARS)

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        """入力pathが正規化済み相対POSIX pathなら同じ文字列を返す。"""
        path = PurePosixPath(value)
        if (
            not value
            or "\\" in value
            or path.is_absolute()
            or any(part in {"", ".", ".."} for part in value.split("/"))
            or path.as_posix() != value
        ):
            raise ValueError("artifact path must be a normalized relative POSIX path")
        return value


class ExecutionResult(BaseModel):
    """runnerからbackendへ返す、上限検証済みの文字列・artifact実行結果。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    output: str = Field(max_length=MAX_RUNNER_OUTPUT_CHARS)
    artifact: ExecutionArtifact | None


class RunnerExecutionResponse(BaseModel):
    """protocol versionとtyped resultを保持する不変な内部runner response。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol_version: Literal[2]
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
