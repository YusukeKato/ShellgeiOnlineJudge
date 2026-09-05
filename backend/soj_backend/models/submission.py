from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from soj_shared.models.execution import ExecutionResult
from soj_backend.judge import JudgeResult
from soj_shared.submission_status import SubmissionPersistenceStatus, SubmissionStatus


class SubmissionResult(BaseModel):
    """提出時刻、実行・判定結果、保存状態をHTTP表現から独立して保持する。"""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: SubmissionStatus
    submitted_at: datetime
    execution: ExecutionResult | None
    judgment: JudgeResult | None
    log_id: int | None = Field(default=None, gt=0)
    persistence: SubmissionPersistenceStatus

    @model_validator(mode="after")
    def validate_consistent_result(self) -> "SubmissionResult":
        """提出statusと結果・保存fieldの組合せを検証し、整合する自身を返す。"""
        if self.submitted_at.utcoffset() is None:
            raise ValueError("submission timestamp must include a timezone")
        if self.status is SubmissionStatus.COMPLETED:
            if self.execution is None or self.judgment is None:
                raise ValueError("completed submission must contain results")
            if self.persistence is SubmissionPersistenceStatus.SAVED:
                if self.log_id is None:
                    raise ValueError("saved submission must contain a log ID")
            elif self.persistence is SubmissionPersistenceStatus.UNAVAILABLE:
                if self.log_id is not None:
                    raise ValueError("unsaved submission must not contain a log ID")
            else:
                raise ValueError("completed submission must attempt persistence")
        elif (
            self.execution is not None
            or self.judgment is not None
            or self.log_id is not None
            or self.persistence is not SubmissionPersistenceStatus.NOT_ATTEMPTED
        ):
            raise ValueError("rejected submission must not contain execution results")
        return self
