from pathlib import PurePosixPath
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from scripts.input_validation import ProblemId


PROBLEM_SCHEMA_VERSION: Final = 3
PROBLEM_MANIFEST_VERSION: Final = 1
MAX_PROBLEM_TEXT_BYTES = 256_000
MAX_REFERENCE_SOLUTION_BYTES = 64_000
MAX_STDIN_BYTES = 1_000_000
MAX_FIXTURE_BYTES = 1_000_000
MAX_TOTAL_FIXTURE_BYTES = 1_000_000
MAX_FIXTURES = 16
MAX_PROBLEM_PATH_BYTES = 255
MAX_ARTIFACT_BYTES = 750_000

ProblemCategory = Literal["STANDARD", "PRACTICE", "IMAGE"]
ExitCodePolicy = Literal["ignore", "zero"]
StderrPolicy = Literal["merge", "ignore", "must_be_empty"]
ImageMediaType = Literal["image/jpeg", "image/gif"]


def _validate_text_bytes(value: str, *, field: str, maximum: int) -> str:
    """入力文字列のNUL有無とUTF-8 byte数を検証し、問題なければ同じ文字列を返す。"""
    if "\x00" in value:
        raise ValueError(f"{field} must not contain NUL bytes")
    if len(value.encode("utf-8")) > maximum:
        raise ValueError(f"{field} exceeds the {maximum}-byte limit")
    return value


def _validate_relative_path(value: str, *, field: str) -> str:
    """入力pathが安全な相対POSIX pathか検証し、正規化済みの同じ文字列を返す。"""
    if not value or "\x00" in value or "\\" in value:
        raise ValueError(f"{field} must be a non-empty POSIX path")
    if len(value.encode("utf-8")) > MAX_PROBLEM_PATH_BYTES:
        raise ValueError(f"{field} exceeds the {MAX_PROBLEM_PATH_BYTES}-byte limit")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in value.split("/")):
        raise ValueError(f"{field} must be a normalized relative path")
    if path.as_posix() != value:
        raise ValueError(f"{field} must be a normalized relative path")
    return value


class StrictProblemModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LocalizedText(StrictProblemModel):
    ja: str
    en: str

    @field_validator("ja", "en")
    @classmethod
    def validate_localized_text(cls, value: str) -> str:
        """入力された日英textが空でなく上限内なら、その文字列を返す。"""
        if not value:
            raise ValueError("localized text must not be empty")
        return _validate_text_bytes(
            value,
            field="localized text",
            maximum=MAX_PROBLEM_TEXT_BYTES,
        )


class FixtureDefinition(StrictProblemModel):
    path: str
    content: str

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        """入力されたfixture pathを検証し、安全なら同じ相対pathを返す。"""
        validated = _validate_relative_path(value, field="fixture path")
        if validated == "z.bash":
            raise ValueError(
                "fixture path z.bash is reserved for the submitted command"
            )
        return validated

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        """入力されたfixture内容が空でなく上限内なら、その文字列を返す。"""
        if not value:
            raise ValueError("fixture content must not be empty")
        return _validate_text_bytes(
            value,
            field="fixture content",
            maximum=MAX_FIXTURE_BYTES,
        )


class ExecutionSpecification(StrictProblemModel):
    stdin: str
    fixtures: tuple[FixtureDefinition, ...] = Field(max_length=MAX_FIXTURES)
    exit_code: ExitCodePolicy
    stderr: StderrPolicy

    @field_validator("stdin")
    @classmethod
    def validate_stdin(cls, value: str) -> str:
        """入力された標準入力のNULとbyte数を検証し、同じ文字列を返す。"""
        return _validate_text_bytes(value, field="stdin", maximum=MAX_STDIN_BYTES)

    @field_validator("fixtures")
    @classmethod
    def validate_fixtures(
        cls,
        value: tuple[FixtureDefinition, ...],
    ) -> tuple[FixtureDefinition, ...]:
        """入力fixture群のpath重複と合計byte数を検証し、同じtupleを返す。"""
        paths = [fixture.path for fixture in value]
        if len(paths) != len(set(paths)):
            raise ValueError("fixture paths must be unique")
        total_bytes = sum(len(fixture.content.encode("utf-8")) for fixture in value)
        if total_bytes > MAX_TOTAL_FIXTURE_BYTES:
            raise ValueError(
                f"fixture contents exceed the {MAX_TOTAL_FIXTURE_BYTES}-byte total limit"
            )
        return value


class TextJudgeSpecification(StrictProblemModel):
    type: Literal["text"]
    expected_output: str

    @field_validator("expected_output")
    @classmethod
    def validate_expected_output(cls, value: str) -> str:
        """入力された期待出力のNULとbyte数を検証し、同じ文字列を返す。"""
        return _validate_text_bytes(
            value,
            field="expected output",
            maximum=MAX_PROBLEM_TEXT_BYTES,
        )


class ImageArtifactSpecification(StrictProblemModel):
    path: str
    media_type: ImageMediaType
    max_bytes: int = Field(gt=0, le=MAX_ARTIFACT_BYTES)

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        """入力された画像artifact pathを検証し、安全なら同じ相対pathを返す。"""
        return _validate_relative_path(value, field="artifact path")

    @model_validator(mode="after")
    def validate_media_type_matches_path(self) -> "ImageArtifactSpecification":
        """artifactのMIME typeとpath拡張子を照合し、一致すれば検証済みmodelを返す。"""
        expected_suffix = ".jpg" if self.media_type == "image/jpeg" else ".gif"
        if not self.path.endswith(expected_suffix):
            raise ValueError("artifact path extension must match media_type")
        return self


class ImageJudgeSpecification(StrictProblemModel):
    type: Literal["image"]
    artifact: ImageArtifactSpecification


JudgeSpecification = Annotated[
    TextJudgeSpecification | ImageJudgeSpecification,
    Field(discriminator="type"),
]


class ProblemDefinitionV3(StrictProblemModel):
    schema_version: Literal[3]
    id: ProblemId
    category: ProblemCategory
    title: LocalizedText
    statement: LocalizedText
    reference_solution: str
    execution: ExecutionSpecification
    judge: JudgeSpecification

    @field_validator("reference_solution")
    @classmethod
    def validate_reference_solution(cls, value: str) -> str:
        """入力された参照解答のNULとbyte数を検証し、同じ文字列を返す。"""
        return _validate_text_bytes(
            value,
            field="reference solution",
            maximum=MAX_REFERENCE_SOLUTION_BYTES,
        )

    @model_validator(mode="after")
    def validate_category_matches_id(self) -> "ProblemDefinitionV3":
        """ID・category・judge種別の整合性を検証し、検証済みproblem modelを返す。"""
        if self.id.split("-", maxsplit=1)[0] != self.category:
            raise ValueError("category must match the problem ID prefix")
        if self.category == "IMAGE" and self.judge.type != "image":
            raise ValueError("IMAGE problems must use the image judge")
        if self.category != "IMAGE" and self.judge.type != "text":
            raise ValueError("non-IMAGE problems must use the text judge")
        return self


class ProblemManifestV1(StrictProblemModel):
    """問題数とdata revisionを保持する、version 1の不変manifest model。"""

    manifest_version: Literal[1]
    problem_schema_version: Literal[3]
    problem_count: int = Field(gt=0)
    revision: str = Field(pattern=r"^[0-9a-f]{64}$")
