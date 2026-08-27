import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import Session

from models.model_db import ExecutionLog
from scripts.async_thread import wait_for_thread_future
from scripts.database import SessionLocal
from scripts.execution_log_retention import prune_execution_logs


logger = logging.getLogger(__name__)

EXECUTION_LOG_OUTPUT_MAX_CHARS = 1000
EXECUTION_LOG_WORKER_CAPACITY = 4
SessionFactory = Callable[[], Session]
PruneLogs = Callable[[Session], int]
PersistLog = Callable[[str, str, str, str], int]
_executor = ThreadPoolExecutor(
    max_workers=EXECUTION_LOG_WORKER_CAPACITY,
    thread_name_prefix="execution-log",
)


class ExecutionLogPersistenceError(RuntimeError):
    """Raised when an execution log cannot be saved safely."""


def normalize_execution_log_text(value: str) -> str:
    """Replace PostgreSQL-incompatible NUL characters for storage only."""
    return value.replace("\x00", "\N{REPLACEMENT CHARACTER}")


def persist_execution_log(
    problem_id: str,
    shellgei: str,
    output: str,
    judge: str,
    *,
    session_factory: SessionFactory = SessionLocal,
    prune_logs: PruneLogs = prune_execution_logs,
) -> int:
    """Save and prune execution logs in one rollback-safe transaction."""
    db: Session | None = None
    try:
        db = session_factory()
        execution_log = ExecutionLog(
            problem_id=normalize_execution_log_text(problem_id),
            shellgei=normalize_execution_log_text(shellgei),
            output=normalize_execution_log_text(output)[
                :EXECUTION_LOG_OUTPUT_MAX_CHARS
            ],
            judge=normalize_execution_log_text(judge),
        )
        db.add(execution_log)
        prune_logs(db)
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
        raise ExecutionLogPersistenceError("execution log persistence failed") from exc
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                logger.exception("Execution log session close failed")


async def persist_execution_log_async(
    problem_id: str,
    shellgei: str,
    output: str,
    judge: str,
    *,
    persist_log: PersistLog = persist_execution_log,
) -> int:
    """Run synchronous SQLAlchemy work outside the request event loop."""
    try:
        future = _executor.submit(
            persist_log,
            problem_id,
            shellgei,
            output,
            judge,
        )
        return await wait_for_thread_future(future)
    except ExecutionLogPersistenceError:
        raise
    except Exception as exc:
        raise ExecutionLogPersistenceError("execution log persistence failed") from exc


def close_execution_log_persistence() -> None:
    _executor.shutdown(wait=True, cancel_futures=True)
