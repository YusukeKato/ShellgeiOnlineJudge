import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor

from sqlalchemy.orm import Session

from soj_backend.models.execution_log import ExecutionLogEntry
from soj_backend.models.model_db import ExecutionLog
from soj_shared.async_thread import wait_for_thread_future
from soj_backend.database import SessionLocal
from soj_backend.execution_log_retention import prune_execution_logs
from soj_shared.structured_logging import (
    LogComponent,
    LogEvent,
    SAFE_EVENT_LOGGER_NAME,
    log_safe_event,
)


logger = logging.getLogger(SAFE_EVENT_LOGGER_NAME)

EXECUTION_LOG_OUTPUT_MAX_CHARS = 1_000
EXECUTION_LOG_WORKER_CAPACITY = 4
SessionFactory = Callable[[], Session]
PruneLogs = Callable[[Session], int]
PersistEntry = Callable[[ExecutionLogEntry], int]


class ExecutionLogRepositoryError(RuntimeError):
    """実行ログのtransaction、session、worker処理が安全に完了しない場合に送出する。"""


def normalize_execution_log_text(value: str) -> str:
    """入力文字列のPostgreSQL非対応NULを保存時だけ置換して返す。"""
    return value.replace("\x00", "\N{REPLACEMENT CHARACTER}")


class ExecutionLogRepo:
    """typed実行ログの保存、transaction、retention境界を提供するrepository。"""

    def __init__(
        self,
        session_factory: SessionFactory = SessionLocal,
        prune_logs: PruneLogs = prune_execution_logs,
    ) -> None:
        """Session生成関数と同一transactionで使う保持処理を受け取り初期化する。"""
        self._session_factory = session_factory
        self._prune_logs = prune_logs

    def save(self, entry: ExecutionLogEntry) -> int:
        """typed entryを正規化して保存し、採番IDを返す。

        画像artifactとrequest metadataはentry型に存在しないため保存しない。追加と
        retentionを同じtransactionでcommitし、失敗時はrollback後に例外を返す。
        """
        db: Session | None = None
        try:
            db = self._session_factory()
            execution_log = ExecutionLog(
                problem_id=normalize_execution_log_text(entry.problem_id),
                shellgei=normalize_execution_log_text(entry.shellgei),
                output=normalize_execution_log_text(entry.legacy_output)[
                    :EXECUTION_LOG_OUTPUT_MAX_CHARS
                ],
                judge=entry.legacy_judge,
                execution_status=entry.execution_status.value,
                stdout=normalize_execution_log_text(entry.stdout),
                stderr=normalize_execution_log_text(entry.stderr),
                exit_code=entry.exit_code,
                timed_out=entry.timed_out,
                truncated=entry.truncated,
                duration_ms=entry.duration_ms,
                verdict=entry.verdict.value,
                judge_reason=(
                    entry.judge_reason.value if entry.judge_reason is not None else None
                ),
            )
            db.add(execution_log)
            self._prune_logs(db)
            if execution_log.id is None:
                raise RuntimeError("execution log ID was not assigned")
            log_id = int(execution_log.id)
            db.commit()
            return log_id
        except Exception as exc:
            if db is not None:
                try:
                    db.rollback()
                except Exception:
                    log_safe_event(
                        logger,
                        LogEvent.EXECUTION_LOG_ROLLBACK_FAILED,
                        LogComponent.EXECUTION_LOG,
                        level=logging.ERROR,
                    )
            raise ExecutionLogRepositoryError(
                "execution log persistence failed"
            ) from exc
        finally:
            if db is not None:
                try:
                    db.close()
                except Exception:
                    log_safe_event(
                        logger,
                        LogEvent.EXECUTION_LOG_SESSION_CLOSE_FAILED,
                        LogComponent.EXECUTION_LOG,
                        level=logging.ERROR,
                    )

    def prune(self) -> int:
        """独立transactionで期限・件数超過ログを削除し、削除件数を返す。"""
        db: Session | None = None
        try:
            db = self._session_factory()
            deleted = self._prune_logs(db)
            db.commit()
            return deleted
        except Exception as exc:
            if db is not None:
                try:
                    db.rollback()
                except Exception:
                    log_safe_event(
                        logger,
                        LogEvent.EXECUTION_LOG_ROLLBACK_FAILED,
                        LogComponent.EXECUTION_LOG,
                        level=logging.ERROR,
                    )
            raise ExecutionLogRepositoryError("execution log pruning failed") from exc
        finally:
            if db is not None:
                try:
                    db.close()
                except Exception:
                    log_safe_event(
                        logger,
                        LogEvent.EXECUTION_LOG_SESSION_CLOSE_FAILED,
                        LogComponent.EXECUTION_LOG,
                        level=logging.ERROR,
                    )


class AsyncExecutionLogRepo:
    """同期ExecutionLogRepoを専用workerで呼び出す非同期application adapter。"""

    def __init__(self, repository: ExecutionLogRepo) -> None:
        """入力の同期repositoryを、非同期saveが委譲する保存先として保持する。"""
        self._repository = repository

    async def save(self, entry: ExecutionLogEntry, *, request_id: str) -> int:
        """入力entryをthreadで保存し、request IDは安全なeventの紐付けだけに使う。"""
        return await save_execution_log_async(
            entry,
            request_id=request_id,
            persist_entry=self._repository.save,
        )


class _ExecutionLogExecutor:
    """受付済み保存の寿命を管理し、切断後も未完了件数をworker数以下に保つ。"""

    def __init__(self) -> None:
        """プロセス共通の保存worker、非待機の受付枠、終了状態を用意する。"""
        self._pool = ThreadPoolExecutor(
            max_workers=EXECUTION_LOG_WORKER_CAPACITY,
            thread_name_prefix="execution-log",
        )
        self._slots = threading.BoundedSemaphore(EXECUTION_LOG_WORKER_CAPACITY)
        self._admission_lock = threading.Lock()
        self._closing = False

    def submit(
        self, persistence: PersistEntry, entry: ExecutionLogEntry
    ) -> Future[int]:
        """待たずに保存を受け付け、満杯・終了中ならrepository例外を返す。

        返すfutureをrequestのキャンセル時にcancelしないこと。実保存の終了まで
        枠を保持し、キャンセル済みwork itemを内部queueへ蓄積させない。
        """
        with self._admission_lock:
            if self._closing or not self._slots.acquire(blocking=False):
                raise ExecutionLogRepositoryError("execution log worker unavailable")
            try:
                future = self._pool.submit(persistence, entry)
            except BaseException:
                # Thread.start失敗はqueue投入後にも起こる。投入有無が不明なため
                # 再受付を閉じ、残ったwork itemを繰り返し積まない。
                self._closing = True
                self._slots.release()
                raise
            future.add_done_callback(self._release_slot)
            return future

    def _release_slot(self, _future: Future[int]) -> None:
        """保存・rollback・closeまで終了したfutureの受付枠を一度だけ返す。"""
        self._slots.release()

    def shutdown(self) -> None:
        """新規受付を閉じてから保存終了を待つ。繰り返しの終了要求も許容する。"""
        with self._admission_lock:
            self._closing = True
        # callbackは受付lockを取らない。shutdown中のcancelによる解放も安全に行う。
        self._pool.shutdown(wait=True, cancel_futures=True)


execution_log_repo = ExecutionLogRepo()
_executor = _ExecutionLogExecutor()


async def save_execution_log_async(
    entry: ExecutionLogEntry,
    *,
    request_id: str | None = None,
    persist_entry: PersistEntry | None = None,
) -> int:
    """typed entryをthreadで保存し、ID付き安全eventと採番IDを返す。"""
    persistence = persist_entry or execution_log_repo.save
    started_ns = time.monotonic_ns()
    try:
        future = _executor.submit(persistence, entry)
        log_id = await wait_for_thread_future(future)
    except ExecutionLogRepositoryError:
        log_safe_event(
            logger,
            LogEvent.EXECUTION_LOG_SAVE_FAILED,
            LogComponent.EXECUTION_LOG,
            request_id=request_id,
            duration_ms=max(0, (time.monotonic_ns() - started_ns) // 1_000_000),
            level=logging.WARNING,
        )
        raise
    except Exception as exc:
        log_safe_event(
            logger,
            LogEvent.EXECUTION_LOG_SAVE_FAILED,
            LogComponent.EXECUTION_LOG,
            request_id=request_id,
            duration_ms=max(0, (time.monotonic_ns() - started_ns) // 1_000_000),
            level=logging.WARNING,
        )
        raise ExecutionLogRepositoryError("execution log persistence failed") from exc
    log_safe_event(
        logger,
        LogEvent.EXECUTION_LOG_SAVE_COMPLETED,
        LogComponent.EXECUTION_LOG,
        request_id=request_id,
        duration_ms=max(0, (time.monotonic_ns() - started_ns) // 1_000_000),
    )
    return log_id


def close_execution_log_repository() -> None:
    """実行ログworkerへの新規受付を止め、処理中futureの終了を待って資源を閉じる。"""
    _executor.shutdown()


async_execution_log_repo = AsyncExecutionLogRepo(execution_log_repo)
