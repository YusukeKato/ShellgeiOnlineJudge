import asyncio
from datetime import datetime, timezone
from typing import cast

import pytest

from models.execution import ExecutionResult, ExecutionStatus
from models.execution_log import ExecutionLogEntry
from models.submission import (
    SubmissionPersistenceStatus,
    SubmissionStatus,
)
from scripts.execution_log_repository import ExecutionLogRepositoryError
from scripts.judge import JudgeReason, JudgeResult, JudgeVerdict
from scripts.problem_repository import ProblemRecord
from scripts.runner_protocol import RunnerBusyError, RunnerUnavailableError
from scripts.submit_solution import SubmitSolutionService


PROBLEM_ID = "STANDARD-00000001"
SUBMITTED_AT = datetime(2026, 9, 1, 12, 34, 56, tzinfo=timezone.utc)
PROBLEM_RECORD = cast(ProblemRecord, object())


def _completed_execution(stdout: str = "ok") -> ExecutionResult:
    """任意stdoutから、service test用の正常完了実行結果を返す。"""
    return ExecutionResult(
        status=ExecutionStatus.COMPLETED,
        stdout=stdout,
        stderr="",
        exit_code=0,
        timed_out=False,
        truncated=False,
        duration_ms=10,
        artifact=None,
        error=None,
    )


def _timed_out_execution() -> ExecutionResult:
    """timeout分岐を検証するため、出力付きの時間超過実行結果を返す。"""
    return ExecutionResult(
        status=ExecutionStatus.TIMED_OUT,
        stdout="partial",
        stderr="",
        exit_code=None,
        timed_out=True,
        truncated=False,
        duration_ms=10_000,
        artifact=None,
        error=None,
    )


class FakeProblemRepo:
    """検索結果と呼出し順を制御するproblem repositoryのfake。"""

    def __init__(
        self,
        events: list[str],
        record: ProblemRecord | None = PROBLEM_RECORD,
    ) -> None:
        """呼出し記録先と、getが返す任意recordを保持する。"""
        self.events = events
        self.record = record

    def get(self, problem_id: str) -> ProblemRecord | None:
        """入力IDを確認してproblem検索を記録し、設定済みrecordを返す。"""
        assert problem_id == PROBLEM_ID
        self.events.append("problem")
        return self.record


class FakeRunner:
    """実行結果またはrunner例外を返し、呼出し順を記録するfake。"""

    def __init__(
        self,
        events: list[str],
        result: ExecutionResult | None = None,
        error: Exception | None = None,
    ) -> None:
        """呼出し記録先と、返す結果または送出する例外を保持する。"""
        self.events = events
        self.result = result or _completed_execution()
        self.error = error

    async def execute(self, shellgei: str, problem_id: str) -> ExecutionResult:
        """入力command・IDを確認し、設定された実行結果または例外を返す。"""
        assert shellgei == "printf ok"
        assert problem_id == PROBLEM_ID
        self.events.append("runner")
        if self.error is not None:
            raise self.error
        return self.result


class FakeJudge:
    """判定結果または予期しない例外を返し、呼出し順を記録するfake。"""

    def __init__(
        self,
        events: list[str],
        result: JudgeResult | None = None,
        error: Exception | None = None,
    ) -> None:
        """呼出し記録先と、返す判定または送出する例外を保持する。"""
        self.events = events
        self.result = result or JudgeResult(verdict=JudgeVerdict.ACCEPTED)
        self.error = error

    def judge(self, execution: ExecutionResult, problem_id: str) -> JudgeResult:
        """入力結果・IDを確認し、設定された判定結果または例外を返す。"""
        assert isinstance(execution, ExecutionResult)
        assert problem_id == PROBLEM_ID
        self.events.append("judge")
        if self.error is not None:
            raise self.error
        return self.result


class FakeExecutionLogRepo:
    """保存IDまたはrepository例外を返し、entryと呼出し順を記録するfake。"""

    def __init__(
        self,
        events: list[str],
        log_id: int = 42,
        error: Exception | None = None,
    ) -> None:
        """呼出し記録先、採番ID、任意の保存例外を保持する。"""
        self.events = events
        self.log_id = log_id
        self.error = error
        self.entries: list[ExecutionLogEntry] = []

    async def save(self, entry: ExecutionLogEntry) -> int:
        """入力entryを記録し、設定された採番IDまたは例外を返す。"""
        self.events.append("log")
        self.entries.append(entry)
        if self.error is not None:
            raise self.error
        return self.log_id


def _service(
    events: list[str],
    *,
    problem_repository: FakeProblemRepo | None = None,
    runner: FakeRunner | None = None,
    judge: FakeJudge | None = None,
    execution_logs: FakeExecutionLogRepo | None = None,
) -> tuple[SubmitSolutionService, FakeExecutionLogRepo]:
    """任意fake境界でserviceを組み立て、serviceとログfakeを返す。"""
    log_repo = execution_logs or FakeExecutionLogRepo(events)
    return (
        SubmitSolutionService(
            problem_repository=problem_repository or FakeProblemRepo(events),
            runner=runner or FakeRunner(events),
            judge=judge or FakeJudge(events),
            execution_logs=log_repo,
            clock=lambda: SUBMITTED_AT,
        ),
        log_repo,
    )


def test_submit_solution_orders_problem_execution_judge_and_persistence() -> None:
    # 正常提出がproblem確認、runner、判定、保存の順で進み、型付き結果を返すことを確認する。
    events: list[str] = []
    service, logs = _service(events)

    result = asyncio.run(service.submit("printf ok", PROBLEM_ID))

    assert events == ["problem", "runner", "judge", "log"]
    assert result.status is SubmissionStatus.COMPLETED
    assert result.submitted_at == SUBMITTED_AT
    assert result.execution == _completed_execution()
    assert result.judgment == JudgeResult(verdict=JudgeVerdict.ACCEPTED)
    assert result.log_id == 42
    assert result.persistence is SubmissionPersistenceStatus.SAVED
    assert len(logs.entries) == 1
    assert logs.entries[0].problem_id == PROBLEM_ID
    assert logs.entries[0].shellgei == "printf ok"


def test_submit_solution_stops_when_problem_is_not_found() -> None:
    # 未登録problemではrunner・判定・保存へ進まず、problem未登録statusを返すことを確認する。
    events: list[str] = []
    service, _ = _service(
        events,
        problem_repository=FakeProblemRepo(events, record=None),
    )

    result = asyncio.run(service.submit("printf ok", PROBLEM_ID))

    assert events == ["problem"]
    assert result.status is SubmissionStatus.PROBLEM_NOT_FOUND
    assert result.execution is None
    assert result.judgment is None
    assert result.persistence is SubmissionPersistenceStatus.NOT_ATTEMPTED


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (RunnerBusyError("busy"), SubmissionStatus.RUNNER_BUSY),
        (RunnerUnavailableError("unavailable"), SubmissionStatus.RUNNER_UNAVAILABLE),
    ],
)
def test_submit_solution_separates_runner_failures_from_judgments(
    error: Exception,
    expected_status: SubmissionStatus,
) -> None:
    # runner混雑・停止を判定結果へ変換せず、判定・保存なしの専用statusにすることを確認する。
    events: list[str] = []
    service, _ = _service(events, runner=FakeRunner(events, error=error))

    result = asyncio.run(service.submit("printf ok", PROBLEM_ID))

    assert events == ["problem", "runner"]
    assert result.status is expected_status
    assert result.judgment is None
    assert result.persistence is SubmissionPersistenceStatus.NOT_ATTEMPTED


def test_submit_solution_judges_and_persists_timeout_result() -> None:
    # runnerが返したtimeoutを通信障害と混同せず、実行失敗判定として保存することを確認する。
    events: list[str] = []
    execution = _timed_out_execution()
    judgment = JudgeResult(
        verdict=JudgeVerdict.EXECUTION_FAILURE,
        reason=JudgeReason.TIMED_OUT,
    )
    service, logs = _service(
        events,
        runner=FakeRunner(events, result=execution),
        judge=FakeJudge(events, result=judgment),
    )

    result = asyncio.run(service.submit("printf ok", PROBLEM_ID))

    assert events == ["problem", "runner", "judge", "log"]
    assert result.status is SubmissionStatus.COMPLETED
    assert result.execution is execution
    assert result.judgment == judgment
    assert logs.entries[0].execution_status is ExecutionStatus.TIMED_OUT
    assert logs.entries[0].verdict is JudgeVerdict.EXECUTION_FAILURE


def test_submit_solution_does_not_convert_unexpected_judge_error_to_wrong_answer() -> (
    None
):
    # judgeの予期しない例外を不正解に偽装せず伝播し、実行ログも保存しないことを確認する。
    events: list[str] = []
    service, _ = _service(
        events,
        judge=FakeJudge(events, error=RuntimeError("judge failed")),
    )

    with pytest.raises(RuntimeError, match="judge failed"):
        asyncio.run(service.submit("printf ok", PROBLEM_ID))

    assert events == ["problem", "runner", "judge"]


def test_submit_solution_returns_results_when_persistence_is_unavailable() -> None:
    # DB保存だけが失敗した場合、IDなしのまま実行・判定結果を失わず返すことを確認する。
    events: list[str] = []
    service, _ = _service(
        events,
        execution_logs=FakeExecutionLogRepo(
            events,
            error=ExecutionLogRepositoryError("unavailable"),
        ),
    )

    result = asyncio.run(service.submit("printf ok", PROBLEM_ID))

    assert events == ["problem", "runner", "judge", "log"]
    assert result.status is SubmissionStatus.COMPLETED
    assert result.execution == _completed_execution()
    assert result.judgment == JudgeResult(verdict=JudgeVerdict.ACCEPTED)
    assert result.log_id is None
    assert result.persistence is SubmissionPersistenceStatus.UNAVAILABLE
