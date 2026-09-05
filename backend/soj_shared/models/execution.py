from enum import Enum
from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from soj_shared.models.problem import ImageMediaType, MAX_PROBLEM_PATH_BYTES


MAX_CAPTURED_OUTPUT_CHARS = 1_000
MAX_EXECUTION_ERROR_CHARS = 1_000
MAX_RUNNER_IMAGE_BASE64_CHARS = 1_000_000


class ExecutionStatus(str, Enum):
    """sandbox実行の正常完了、制限終了、基盤errorを区別して表す。"""

    COMPLETED = "completed"
    TIMED_OUT = "timed_out"
    OUTPUT_LIMIT = "output_limit"
    ERROR = "error"


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
    """sandbox実行の状態、分離出力、終了code、時間、artifactを不変に保持する。"""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ExecutionStatus
    stdout: str = Field(max_length=MAX_CAPTURED_OUTPUT_CHARS)
    stderr: str = Field(max_length=MAX_CAPTURED_OUTPUT_CHARS)
    exit_code: int | None
    timed_out: bool
    truncated: bool
    duration_ms: int = Field(ge=0)
    artifact: ExecutionArtifact | None
    error: str | None = Field(max_length=MAX_EXECUTION_ERROR_CHARS)

    @model_validator(mode="after")
    def validate_consistent_outcome(self) -> "ExecutionResult":
        """出力合計上限とstatus・flag・終了code・errorの整合性を検証して返す。"""
        if len(self.stdout) + len(self.stderr) > MAX_CAPTURED_OUTPUT_CHARS:
            raise ValueError("combined execution output exceeds the character limit")
        if self.status is ExecutionStatus.COMPLETED:
            if (
                self.exit_code is None
                or self.timed_out
                or self.truncated
                or self.error is not None
            ):
                raise ValueError("completed execution result is inconsistent")
        elif self.status is ExecutionStatus.TIMED_OUT:
            if not self.timed_out:
                raise ValueError("timed out execution result is inconsistent")
        elif self.status is ExecutionStatus.OUTPUT_LIMIT:
            if self.timed_out or not self.truncated:
                raise ValueError("output limited execution result is inconsistent")
        elif self.timed_out or not self.error:
            raise ValueError("failed execution result is inconsistent")
        if self.status is not ExecutionStatus.COMPLETED and self.artifact is not None:
            raise ValueError("incomplete execution result must not contain an artifact")
        return self

    def legacy_output(self, limit_chars: int = MAX_CAPTURED_OUTPUT_CHARS) -> str:
        """構造化結果を既存public API互換の結合・制限済み表示文字列へ変換する。"""
        combined = self.stdout + self.stderr
        if self.status is ExecutionStatus.TIMED_OUT:
            suffix = "\n[Timed out]"
            return combined[: max(0, limit_chars - len(suffix))] + suffix
        if self.status is ExecutionStatus.OUTPUT_LIMIT:
            return combined[:limit_chars] + "..."
        if self.status is ExecutionStatus.ERROR:
            return f"Error during execution: {self.error}"[:limit_chars]
        if len(combined) > limit_chars:
            return combined[:limit_chars] + "..."
        return combined
