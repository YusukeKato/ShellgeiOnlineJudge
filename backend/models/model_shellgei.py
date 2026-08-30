from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from scripts.input_validation import ProblemId
from models.problem import ImageMediaType


MAX_SHELLGEI_CHARS = 1000


class ShellgeiData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shellgei: str = Field(min_length=1, max_length=MAX_SHELLGEI_CHARS)
    problem_id: ProblemId

    @field_validator("shellgei", mode="before")
    @classmethod
    def normalize_shellgei(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.replace("\r", "")
        return value

    @field_validator("shellgei")
    @classmethod
    def validate_shellgei(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("shellgei must not contain NUL bytes")
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ValueError("shellgei must be valid UTF-8") from exc
        return value


class ShellgeiResultResponse(BaseModel):
    output: str
    id: str
    date: str
    image: str
    image_media_type: ImageMediaType | None
    judge: str
