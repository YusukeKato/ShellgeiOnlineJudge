from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from soj_shared.models.execution import (
    MAX_CAPTURED_OUTPUT_CHARS,
    MAX_RUNNER_IMAGE_BASE64_CHARS,
    ExecutionResult,
    ExecutionStatus,
)
from soj_shared.submission_request import ShellgeiData
from soj_shared.models.problem import ImageMediaType
from soj_shared.submission_status import SubmissionPersistenceStatus, SubmissionStatus
from soj_backend.models.submission import SubmissionResult
from soj_backend.judge import JudgeReason, JudgeVerdict


PUBLIC_API_VERSION: Literal[3] = 3
MAX_PUBLIC_SUBMISSION_RESPONSE_BYTES = 1_025_000


class SubmitSolutionRequestV3(ShellgeiData):
    """v3公開APIが受け付けるcommandとproblem IDを不変に保持する。"""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class PublicArtifactV3(BaseModel):
    """browserへ返す画像の許可済みMIMEとBase64 dataだけを保持する。"""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    media_type: ImageMediaType
    data: str = Field(
        min_length=4,
        max_length=MAX_RUNNER_IMAGE_BASE64_CHARS,
        pattern=r"^[A-Za-z0-9+/]*={0,2}$",
    )


class PublicExecutionResultV3(BaseModel):
    """内部error詳細とartifact pathを除いた公開用の構造化実行結果。"""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: ExecutionStatus
    stdout: str = Field(max_length=MAX_CAPTURED_OUTPUT_CHARS)
    stderr: str = Field(max_length=MAX_CAPTURED_OUTPUT_CHARS)
    exit_code: int | None
    timed_out: bool
    truncated: bool
    duration_ms: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_output_limit(self) -> "PublicExecutionResultV3":
        """公開するstdout・stderrの合計文字数がprotocol上限内なら自身を返す。"""
        if len(self.stdout) + len(self.stderr) > MAX_CAPTURED_OUTPUT_CHARS:
            raise ValueError("combined public execution output exceeds the limit")
        return self

    @classmethod
    def from_execution(cls, execution: ExecutionResult) -> "PublicExecutionResultV3":
        """内部実行結果から利用者入力由来の出力と安全なmetadataだけを返す。"""
        return cls(
            status=execution.status,
            stdout=execution.stdout,
            stderr=execution.stderr,
            exit_code=execution.exit_code,
            timed_out=execution.timed_out,
            truncated=execution.truncated,
            duration_ms=execution.duration_ms,
        )


class PublicPersistenceStatusV3(str, Enum):
    """公開可能な提出ログの保存済み・保存不能状態を表す。"""

    SAVED = "saved"
    UNAVAILABLE = "unavailable"


class SubmitSolutionResponseV3(BaseModel):
    """typed判定、実行結果、artifact、保存状態を返すv3成功response。"""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    api_version: Literal[3] = PUBLIC_API_VERSION
    submission_id: int | None = Field(default=None, gt=0)
    submitted_at: datetime
    verdict: JudgeVerdict
    reason: JudgeReason | None
    execution: PublicExecutionResultV3
    artifact: PublicArtifactV3 | None
    persistence: PublicPersistenceStatusV3

    @model_validator(mode="after")
    def validate_persistence(self) -> "SubmitSolutionResponseV3":
        """保存statusとsubmission IDおよびtimezoneの整合性を検証して自身を返す。"""
        if self.submitted_at.utcoffset() is None:
            raise ValueError("submission timestamp must include a timezone")
        if self.persistence is PublicPersistenceStatusV3.SAVED:
            if self.submission_id is None:
                raise ValueError("saved response must contain a submission ID")
        elif self.submission_id is not None:
            raise ValueError("unsaved response must not contain a submission ID")
        return self

    @classmethod
    def from_submission(cls, result: SubmissionResult) -> "SubmitSolutionResponseV3":
        """完了したapplication結果を、内部errorとartifact pathなしのv3 DTOへ変換する。"""
        if result.status is not SubmissionStatus.COMPLETED:
            raise ValueError("submission result is not completed")
        if result.execution is None or result.judgment is None:
            raise ValueError("completed submission result is inconsistent")
        artifact = result.execution.artifact
        if result.persistence is SubmissionPersistenceStatus.SAVED:
            persistence = PublicPersistenceStatusV3.SAVED
        elif result.persistence is SubmissionPersistenceStatus.UNAVAILABLE:
            persistence = PublicPersistenceStatusV3.UNAVAILABLE
        else:
            raise ValueError("completed submission did not attempt persistence")
        return cls(
            submission_id=result.log_id,
            submitted_at=result.submitted_at,
            verdict=result.judgment.verdict,
            reason=result.judgment.reason,
            execution=PublicExecutionResultV3.from_execution(result.execution),
            artifact=(
                PublicArtifactV3(
                    media_type=artifact.media_type,
                    data=artifact.data,
                )
                if artifact is not None
                else None
            ),
            persistence=persistence,
        )


class PublicApiErrorCodeV3(str, Enum):
    """v3 submission APIがHTTP statusとともに返す安全なerror code。"""

    PROBLEM_NOT_FOUND = "problem_not_found"
    RUNNER_BUSY = "runner_busy"
    RUNNER_UNAVAILABLE = "runner_unavailable"


class PublicApiErrorV3(BaseModel):
    """内部例外や利用者入力を含まないv3公開error response。"""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    api_version: Literal[3] = PUBLIC_API_VERSION
    code: PublicApiErrorCodeV3
    message: str = Field(min_length=1, max_length=128)
