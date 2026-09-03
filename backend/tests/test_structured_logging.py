import json
import logging

import pytest
from pydantic import ValidationError

from scripts.request_context import (
    REQUEST_ID_PATTERN,
    bind_request_id,
    current_request_id,
    new_request_id,
)
from scripts.structured_logging import (
    LogComponent,
    LogEvent,
    SAFE_EVENT_LOGGER_NAME,
    SafeLogEvent,
    log_safe_event,
)


TEST_REQUEST_ID = "a" * 32


def test_request_context_is_random_scoped_and_restored() -> None:
    # 新規IDが安全な形式で重複せず、bind中だけ参照できて終了後は元の未設定状態へ戻ることを確認する。
    first = new_request_id()
    second = new_request_id()

    assert REQUEST_ID_PATTERN.fullmatch(first)
    assert REQUEST_ID_PATTERN.fullmatch(second)
    assert first != second
    assert current_request_id() is None
    with bind_request_id(TEST_REQUEST_ID):
        assert current_request_id() == TEST_REQUEST_ID
    assert current_request_id() is None


@pytest.mark.parametrize(
    "unsafe_field",
    [
        "command",
        "stdout",
        "stderr",
        "secret",
        "ip_address",
        "headers",
        "problem_id",
    ],
)
def test_safe_log_schema_rejects_sensitive_or_unknown_fields(
    unsafe_field: str,
) -> None:
    # 利用者入力や個人識別情報を表すfieldを構造化eventへ追加できないことを確認する。
    payload = {
        "event": "submission_completed",
        "component": "submission",
        "request_id": TEST_REQUEST_ID,
        unsafe_field: "must-not-be-logged",
    }

    with pytest.raises(ValidationError):
        SafeLogEvent.model_validate(payload)


def test_safe_event_is_emitted_as_bounded_json(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # allowlist済みのevent・component・ID・statusだけが1つのJSON messageとして記録される。
    event_logger = logging.getLogger(SAFE_EVENT_LOGGER_NAME)
    caplog.set_level(logging.INFO, logger=SAFE_EVENT_LOGGER_NAME)

    log_safe_event(
        event_logger,
        LogEvent.HTTP_REQUEST_COMPLETED,
        LogComponent.BACKEND_HTTP,
        request_id=TEST_REQUEST_ID,
        http_status=200,
        duration_ms=12,
    )

    assert json.loads(caplog.records[-1].message) == {
        "event": "http_request_completed",
        "component": "backend_http",
        "request_id": TEST_REQUEST_ID,
        "http_status": 200,
        "duration_ms": 12,
    }
