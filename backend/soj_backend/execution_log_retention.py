import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from soj_backend.models.model_db import ExecutionLog


DEFAULT_EXECUTION_LOG_RETENTION_DAYS = 365
DEFAULT_EXECUTION_LOG_MAX_ROWS = 10_000


def _positive_integer_from_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a positive integer") from exc
    if value < 1:
        raise RuntimeError(f"{name} must be a positive integer")
    return value


EXECUTION_LOG_RETENTION_DAYS = _positive_integer_from_env(
    "EXECUTION_LOG_RETENTION_DAYS",
    DEFAULT_EXECUTION_LOG_RETENTION_DAYS,
)
EXECUTION_LOG_MAX_ROWS = _positive_integer_from_env(
    "EXECUTION_LOG_MAX_ROWS",
    DEFAULT_EXECUTION_LOG_MAX_ROWS,
)


def prune_execution_logs(
    db: Session,
    *,
    now: datetime | None = None,
    retention_days: int = EXECUTION_LOG_RETENTION_DAYS,
    max_rows: int = EXECUTION_LOG_MAX_ROWS,
) -> int:
    """Delete execution logs outside the configured age or ID window."""
    if retention_days < 1 or max_rows < 1:
        raise ValueError("execution log retention limits must be positive")

    db.flush()
    current_time = now or datetime.now(timezone.utc)
    cutoff = current_time - timedelta(days=retention_days)
    newest_id = db.scalar(select(func.max(ExecutionLog.id)))

    delete_conditions = [ExecutionLog.created_at < cutoff]
    if newest_id is not None:
        oldest_retained_id = newest_id - max_rows + 1
        delete_conditions.append(ExecutionLog.id < oldest_retained_id)

    delete_statement = delete(ExecutionLog).where(or_(*delete_conditions))
    result = db.execute(delete_statement.execution_options(synchronize_session=False))
    return int(getattr(result, "rowcount", 0) or 0)
