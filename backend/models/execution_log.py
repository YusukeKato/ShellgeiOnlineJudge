from pydantic import BaseModel, ConfigDict, Field, model_validator

from models.execution import MAX_CAPTURED_OUTPUT_CHARS, ExecutionResult, ExecutionStatus
from scripts.input_validation import ProblemId
from scripts.judge import JudgeReason, JudgeResult, JudgeVerdict


class ExecutionLogEntry(BaseModel):
    """DBへ保存可能な最小限の提出・実行・判定fieldだけを不変に保持する。

    request ID、IP address、header、User-Agent、画像artifact、内部errorをfieldとして
    受け取らず、repository境界へ不要な情報を持ち込まない。
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    problem_id: ProblemId
    shellgei: str = Field(min_length=1, max_length=1_000)
    legacy_output: str = Field(max_length=MAX_CAPTURED_OUTPUT_CHARS + 3)
    legacy_judge: str = Field(min_length=1, max_length=1)
    execution_status: ExecutionStatus
    stdout: str = Field(max_length=MAX_CAPTURED_OUTPUT_CHARS)
    stderr: str = Field(max_length=MAX_CAPTURED_OUTPUT_CHARS)
    exit_code: int | None
    timed_out: bool
    truncated: bool
    duration_ms: int = Field(ge=0)
    verdict: JudgeVerdict
    judge_reason: JudgeReason | None

    @model_validator(mode="after")
    def validate_execution_fields(self) -> "ExecutionLogEntry":
        """分離出力の合計上限とstatus・flag・終了codeの整合性を検証して返す。"""
        if len(self.stdout) + len(self.stderr) > MAX_CAPTURED_OUTPUT_CHARS:
            raise ValueError("combined execution log output exceeds the limit")
        if self.execution_status is ExecutionStatus.COMPLETED:
            if self.exit_code is None or self.timed_out or self.truncated:
                raise ValueError("completed execution log is inconsistent")
        elif self.execution_status is ExecutionStatus.TIMED_OUT:
            if not self.timed_out:
                raise ValueError("timed out execution log is inconsistent")
        elif self.execution_status is ExecutionStatus.OUTPUT_LIMIT:
            if self.timed_out or not self.truncated:
                raise ValueError("output limited execution log is inconsistent")
        elif self.timed_out:
            raise ValueError("failed execution log is inconsistent")
        return self

    @classmethod
    def from_results(
        cls,
        problem_id: str,
        shellgei: str,
        execution: ExecutionResult,
        judge: JudgeResult,
    ) -> "ExecutionLogEntry":
        """typed実行・判定からartifactと内部errorを除いた保存entryを返す。

        入力は検証済みproblem ID・command・結果。戻り値にはDB保存対象だけを含み、
        画像binaryやrequest由来metadataをコピーしない。
        """
        legacy_output = (
            "Error during execution"
            if execution.status is ExecutionStatus.ERROR
            else execution.legacy_output()
        )
        return cls(
            problem_id=problem_id,
            shellgei=shellgei,
            legacy_output=legacy_output,
            legacy_judge=judge.legacy_code(),
            execution_status=execution.status,
            stdout=execution.stdout,
            stderr=execution.stderr,
            exit_code=execution.exit_code,
            timed_out=execution.timed_out,
            truncated=execution.truncated,
            duration_ms=execution.duration_ms,
            verdict=judge.verdict,
            judge_reason=judge.reason,
        )
