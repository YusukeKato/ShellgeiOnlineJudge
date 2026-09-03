import logging
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from models.execution import ExecutionStatus
from models.submission import SubmissionPersistenceStatus, SubmissionStatus
from scripts.request_context import RequestId


# access logを再有効化せずINFO eventを出すため、Uvicornの非access logger配下を使う。
SAFE_EVENT_LOGGER_NAME = "uvicorn.error.shellgei.events"


class LogComponent(str, Enum):
    """個人情報を含まず、eventが発生したservice内境界を表す。"""

    BACKEND_HTTP = "backend_http"
    SUBMISSION = "submission"
    RUNNER = "runner"
    EXECUTION_LOG = "execution_log"


class LogEvent(str, Enum):
    """任意文字列を記録しないよう、許可するapplication eventを列挙する。"""

    HTTP_REQUEST_COMPLETED = "http_request_completed"
    SUBMISSION_COMPLETED = "submission_completed"
    SUBMISSION_FAILED = "submission_failed"
    RUNNER_CLIENT_FAILED = "runner_client_failed"
    RUNNER_EXECUTION_COMPLETED = "runner_execution_completed"
    EXECUTION_LOG_SAVE_COMPLETED = "execution_log_save_completed"
    EXECUTION_LOG_SAVE_FAILED = "execution_log_save_failed"
    EXECUTION_LOG_ROLLBACK_FAILED = "execution_log_rollback_failed"
    EXECUTION_LOG_SESSION_CLOSE_FAILED = "execution_log_session_close_failed"


class LogEndpoint(str, Enum):
    """raw URLやqueryを記録せずに、対象のpublic endpointを表す。"""

    LEGACY_SUBMISSION = "legacy_submission"
    V3_SUBMISSION = "v3_submission"


class SafeLogEvent(BaseModel):
    """利用者入力を保持できないallowlist形式の構造化log event。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event: LogEvent
    component: LogComponent
    request_id: RequestId | None = None
    endpoint: LogEndpoint | None = None
    http_status: int | None = Field(default=None, ge=100, le=599)
    duration_ms: int | None = Field(default=None, ge=0)
    submission_status: SubmissionStatus | None = None
    execution_status: ExecutionStatus | None = None
    persistence_status: SubmissionPersistenceStatus | None = None


def log_safe_event(
    logger: logging.Logger,
    event: LogEvent,
    component: LogComponent,
    *,
    request_id: str | None = None,
    endpoint: LogEndpoint | None = None,
    http_status: int | None = None,
    duration_ms: int | None = None,
    submission_status: SubmissionStatus | None = None,
    execution_status: ExecutionStatus | None = None,
    persistence_status: SubmissionPersistenceStatus | None = None,
    level: int = logging.INFO,
) -> None:
    """許可済みfieldだけを検証・JSON化し、入力loggerへ1件のeventとして出力する。"""
    payload = SafeLogEvent(
        event=event,
        component=component,
        request_id=request_id,
        endpoint=endpoint,
        http_status=http_status,
        duration_ms=duration_ms,
        submission_status=submission_status,
        execution_status=execution_status,
        persistence_status=persistence_status,
    )
    logger.log(level, payload.model_dump_json(exclude_none=True))
