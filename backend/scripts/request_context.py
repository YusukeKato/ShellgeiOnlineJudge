import re
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Annotated

from pydantic import StringConstraints


REQUEST_ID_BYTES = 16
REQUEST_ID_LENGTH = REQUEST_ID_BYTES * 2
REQUEST_ID_PATTERN_TEXT = rf"^[0-9a-f]{{{REQUEST_ID_LENGTH}}}$"
REQUEST_ID_PATTERN = re.compile(REQUEST_ID_PATTERN_TEXT)
RequestId = Annotated[
    str,
    StringConstraints(
        min_length=REQUEST_ID_LENGTH,
        max_length=REQUEST_ID_LENGTH,
        pattern=REQUEST_ID_PATTERN_TEXT,
    ),
]
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def new_request_id() -> str:
    """外部識別情報を含まない128-bitのランダムrequest IDを生成して返す。"""
    return secrets.token_hex(REQUEST_ID_BYTES)


def validate_request_id(request_id: str) -> str:
    """入力IDが32文字の小文字16進数なら返し、不正ならValueErrorを送出する。"""
    if REQUEST_ID_PATTERN.fullmatch(request_id) is None:
        raise ValueError("request_id must be a 128-bit lowercase hexadecimal value")
    return request_id


@contextmanager
def bind_request_id(request_id: str) -> Iterator[None]:
    """検証済みIDを現在の非同期contextへ設定し、終了時に元の値へ戻す。"""
    token = _request_id.set(validate_request_id(request_id))
    try:
        yield
    finally:
        _request_id.reset(token)


def current_request_id() -> str | None:
    """現在の非同期contextに紐付くrequest IDを返し、未設定ならNoneを返す。"""
    return _request_id.get()
