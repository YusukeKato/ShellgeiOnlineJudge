import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import Session

from models.execution_log import ExecutionLogEntry
from models.model_db import ExecutionLog
from scripts.async_thread import wait_for_thread_future
from scripts.database import SessionLocal
from scripts.execution_log_retention import prune_execution_logs


logger = logging.getLogger(__name__)

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
                    logger.exception("Execution log rollback failed")
            raise ExecutionLogRepositoryError(
                "execution log persistence failed"
            ) from exc
        finally:
            if db is not None:
                try:
                    db.close()
                except Exception:
                    logger.exception("Execution log session close failed")

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
                    logger.exception("Execution log prune rollback failed")
            raise ExecutionLogRepositoryError("execution log pruning failed") from exc
        finally:
            if db is not None:
                try:
                    db.close()
                except Exception:
                    logger.exception("Execution log prune session close failed")


execution_log_repo = ExecutionLogRepo()
_executor = ThreadPoolExecutor(
    max_workers=EXECUTION_LOG_WORKER_CAPACITY,
    thread_name_prefix="execution-log",
)


async def save_execution_log_async(
    entry: ExecutionLogEntry,
    *,
    persist_entry: PersistEntry | None = None,
) -> int:
    """typed entryの同期DB保存をevent loop外で実行し、採番IDを返す。"""
    persistence = persist_entry or execution_log_repo.save
    try:
        future = _executor.submit(persistence, entry)
        return await wait_for_thread_future(future)
    except ExecutionLogRepositoryError:
        raise
    except Exception as exc:
        raise ExecutionLogRepositoryError("execution log persistence failed") from exc


def close_execution_log_repository() -> None:
    """実行ログworkerへの新規受付を止め、処理中futureの終了を待って資源を閉じる。"""
    _executor.shutdown(wait=True, cancel_futures=True)
