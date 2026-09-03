import logging
from collections.abc import Callable
from datetime import datetime
from typing import Protocol
from zoneinfo import ZoneInfo

from models.execution import ExecutionResult
from models.execution_log import ExecutionLogEntry
from models.submission import (
    SubmissionPersistenceStatus,
    SubmissionResult,
    SubmissionStatus,
)
from scripts.execution_log_repository import ExecutionLogRepositoryError
from scripts.judge import JudgeResult
from scripts.problem_repository import ProblemRecord
from scripts.request_context import bind_request_id, current_request_id, new_request_id
from scripts.runner_protocol import (
    RunnerBusyError,
    RunnerGateway,
    RunnerUnavailableError,
)
from scripts.structured_logging import (
    LogComponent,
    LogEvent,
    SAFE_EVENT_LOGGER_NAME,
    log_safe_event,
)


logger = logging.getLogger(SAFE_EVENT_LOGGER_NAME)
JAPAN_TIMEZONE = ZoneInfo("Asia/Tokyo")
Clock = Callable[[], datetime]


class ProblemRepo(Protocol):
    """検証済みproblem recordをIDで参照するapplication境界。"""

    def get(self, problem_id: str) -> ProblemRecord | None:
        """入力IDのproblem recordを返し、未登録ならNoneを返す。"""
        ...


class Judge(Protocol):
    """構造化実行結果をproblem IDの規則で判定するapplication境界。"""

    def judge(self, execution: ExecutionResult, problem_id: str) -> JudgeResult:
        """入力実行結果とproblem IDから型付き判定結果を返す。"""
        ...


class ExecutionLogRepo(Protocol):
    """event loopを停止させずに最小限の実行ログを保存するapplication境界。"""

    async def save(self, entry: ExecutionLogEntry, *, request_id: str) -> int:
        """入力entryを保存し、request IDはDBではなくevent logの紐付けにだけ使う。"""
        ...


def current_japan_time() -> datetime:
    """現在時刻をtimezone付き日本標準時として返す。"""
    return datetime.now(JAPAN_TIMEZONE)


class SubmitSolutionService:
    """problem確認、runner実行、判定、ログ保存を順に編成するuse case。"""

    def __init__(
        self,
        problem_repository: ProblemRepo,
        runner: RunnerGateway,
        judge: Judge,
        execution_logs: ExecutionLogRepo,
        clock: Clock = current_japan_time,
    ) -> None:
        """4つの外部境界と提出時刻を得るclockを受け取り初期化する。"""
        self._problem_repository = problem_repository
        self._runner = runner
        self._judge = judge
        self._execution_logs = execution_logs
        self._clock = clock

    async def submit(self, shellgei: str, problem_id: str) -> SubmissionResult:
        """検証済みcommand・problem IDを処理し、HTTP非依存の提出結果を返す。

        問題未登録とrunnerの混雑・停止では後続処理を行わない。実行できた場合は
        判定後にログを保存し、保存だけが失敗した場合も実行・判定結果を返す。
        judgeの予期しない例外はwrong answerへ変換せず、呼び出し側へ伝播する。
        """
        request_id = current_request_id() or new_request_id()
        with bind_request_id(request_id):
            try:
                return await self._submit(shellgei, problem_id, request_id)
            except Exception:
                log_safe_event(
                    logger,
                    LogEvent.SUBMISSION_FAILED,
                    LogComponent.SUBMISSION,
                    request_id=request_id,
                    level=logging.ERROR,
                )
                raise

    async def _submit(
        self,
        shellgei: str,
        problem_id: str,
        request_id: str,
    ) -> SubmissionResult:
        """入力提出を実行・判定・保存し、各終了経路を安全なeventと結果で返す。"""
        submitted_at = self._clock()
        if self._problem_repository.get(problem_id) is None:
            return self._record_result(
                self._rejected(SubmissionStatus.PROBLEM_NOT_FOUND, submitted_at),
                request_id,
            )

        try:
            execution = await self._runner.execute(shellgei, problem_id)
        except RunnerBusyError:
            return self._record_result(
                self._rejected(SubmissionStatus.RUNNER_BUSY, submitted_at),
                request_id,
            )
        except RunnerUnavailableError:
            return self._record_result(
                self._rejected(SubmissionStatus.RUNNER_UNAVAILABLE, submitted_at),
                request_id,
            )

        judgment = self._judge.judge(execution, problem_id)
        entry = ExecutionLogEntry.from_results(
            problem_id,
            shellgei,
            execution,
            judgment,
        )
        try:
            log_id = await self._execution_logs.save(entry, request_id=request_id)
        except ExecutionLogRepositoryError:
            return self._record_result(
                SubmissionResult(
                    status=SubmissionStatus.COMPLETED,
                    submitted_at=submitted_at,
                    execution=execution,
                    judgment=judgment,
                    persistence=SubmissionPersistenceStatus.UNAVAILABLE,
                ),
                request_id,
                level=logging.WARNING,
            )
        return self._record_result(
            SubmissionResult(
                status=SubmissionStatus.COMPLETED,
                submitted_at=submitted_at,
                execution=execution,
                judgment=judgment,
                log_id=log_id,
                persistence=SubmissionPersistenceStatus.SAVED,
            ),
            request_id,
        )

    @staticmethod
    def _record_result(
        result: SubmissionResult,
        request_id: str,
        *,
        level: int = logging.INFO,
    ) -> SubmissionResult:
        """入力結果の安全なstatusだけをrequest IDと記録し、同じ結果を返す。"""
        execution = result.execution
        log_safe_event(
            logger,
            LogEvent.SUBMISSION_COMPLETED,
            LogComponent.SUBMISSION,
            request_id=request_id,
            submission_status=result.status,
            execution_status=(execution.status if execution is not None else None),
            duration_ms=(execution.duration_ms if execution is not None else None),
            persistence_status=result.persistence,
            level=level,
        )
        return result

    @staticmethod
    def _rejected(status: SubmissionStatus, submitted_at: datetime) -> SubmissionResult:
        """入力拒否statusと時刻から、後続結果を持たない提出結果を返す。"""
        return SubmissionResult(
            status=status,
            submitted_at=submitted_at,
            execution=None,
            judgment=None,
            persistence=SubmissionPersistenceStatus.NOT_ATTEMPTED,
        )
