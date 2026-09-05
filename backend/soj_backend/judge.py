#!/usr/bin/env python3
import base64
import binascii
import warnings
from enum import Enum
from io import BytesIO

from pydantic import BaseModel, ConfigDict
from PIL import Image, UnidentifiedImageError

from soj_shared.models.execution import (
    ExecutionArtifact,
    ExecutionResult,
    ExecutionStatus,
)
from soj_shared.models.problem import (
    ExecutionSpecification,
    ImageJudgeSpecification,
    TextJudgeSpecification,
)
from soj_shared.input_validation import validate_problem_id
from soj_shared.problem_repository import ProblemRepository, get_problem_repository


MAX_DECODED_IMAGE_PIXELS = 4_000_000


class JudgeVerdict(str, Enum):
    """判定結果の意味を、public APIの数字codeから独立して表す。"""

    ACCEPTED = "accepted"
    WRONG_ANSWER = "wrong_answer"
    WRONG_IMAGE = "wrong_image"
    WRONG_TEXT_AND_IMAGE = "wrong_text_and_image"
    EXECUTION_FAILURE = "execution_failure"
    JUDGE_ERROR = "judge_error"


class JudgeReason(str, Enum):
    """不正解・実行失敗・判定失敗の具体的な理由を表す。"""

    OUTPUT_MISMATCH = "output_mismatch"
    IMAGE_MISMATCH = "image_mismatch"
    OUTPUT_AND_IMAGE_MISMATCH = "output_and_image_mismatch"
    ARTIFACT_MISSING = "artifact_missing"
    ARTIFACT_PATH_MISMATCH = "artifact_path_mismatch"
    ARTIFACT_MEDIA_TYPE_MISMATCH = "artifact_media_type_mismatch"
    ARTIFACT_INVALID = "artifact_invalid"
    NON_ZERO_EXIT = "non_zero_exit"
    STDERR_NOT_EMPTY = "stderr_not_empty"
    TIMED_OUT = "timed_out"
    OUTPUT_TRUNCATED = "output_truncated"
    EXECUTION_ERROR = "execution_error"
    INVALID_PROBLEM_ID = "invalid_problem_id"
    PROBLEM_NOT_FOUND = "problem_not_found"


class JudgeResult(BaseModel):
    """verdictと任意の理由を保持する、不変な型付き判定結果。"""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    verdict: JudgeVerdict
    reason: JudgeReason | None = None

    def legacy_code(self) -> str:
        """型付きverdictを既存public APIの判定codeへ変換して返す。"""
        return {
            JudgeVerdict.ACCEPTED: "1",
            JudgeVerdict.WRONG_IMAGE: "2",
            JudgeVerdict.WRONG_ANSWER: "3",
            JudgeVerdict.WRONG_TEXT_AND_IMAGE: "4",
            JudgeVerdict.EXECUTION_FAILURE: "4",
            JudgeVerdict.JUDGE_ERROR: "4",
        }[self.verdict]


class TextJudgeInput(BaseModel):
    """純粋なtext judgeへ渡す、構造化された実行結果。"""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    stdout: str
    stderr: str = ""
    exit_code: int = 0
    timed_out: bool = False
    truncated: bool = False


def normalize_text_output(value: str) -> str:
    """入力文字列からCRと末尾のspace・newlineだけを除き、比較用文字列を返す。"""
    return value.replace("\r", "").rstrip(" \n")


def judge_text(
    judge_specification: TextJudgeSpecification,
    execution_specification: ExecutionSpecification,
    execution: TextJudgeInput,
) -> JudgeResult:
    """text問題の仕様と実行結果を副作用なく比較し、型付き判定結果を返す。

    入力は期待出力、終了code・stderr policy、構造化されたstdout等。fileや
    repositoryを参照せず、timeout、切り詰め、policy違反、出力差を順に判定する。
    """
    execution_failure = _execution_policy_failure(
        execution_specification,
        execution,
    )
    if execution_failure is not None:
        return execution_failure

    actual_output = execution.stdout
    if execution_specification.stderr == "merge":
        actual_output += execution.stderr
    if normalize_text_output(actual_output) == normalize_text_output(
        judge_specification.expected_output
    ):
        return JudgeResult(verdict=JudgeVerdict.ACCEPTED)
    return JudgeResult(
        verdict=JudgeVerdict.WRONG_ANSWER,
        reason=JudgeReason.OUTPUT_MISMATCH,
    )


def _execution_policy_failure(
    execution_specification: ExecutionSpecification,
    execution: TextJudgeInput,
) -> JudgeResult | None:
    """実行状態とproblem policyを検査し、失敗結果または問題なしのNoneを返す。"""
    if execution.timed_out:
        return JudgeResult(
            verdict=JudgeVerdict.EXECUTION_FAILURE,
            reason=JudgeReason.TIMED_OUT,
        )
    if execution.truncated:
        return JudgeResult(
            verdict=JudgeVerdict.EXECUTION_FAILURE,
            reason=JudgeReason.OUTPUT_TRUNCATED,
        )
    if execution_specification.exit_code == "zero" and execution.exit_code != 0:
        return JudgeResult(
            verdict=JudgeVerdict.EXECUTION_FAILURE,
            reason=JudgeReason.NON_ZERO_EXIT,
        )
    if execution_specification.stderr == "must_be_empty" and execution.stderr != "":
        return JudgeResult(
            verdict=JudgeVerdict.EXECUTION_FAILURE,
            reason=JudgeReason.STDERR_NOT_EMPTY,
        )
    return None


def _matches_media_type(payload: bytes, media_type: str) -> bool:
    """入力画像bytesが宣言MIMEの完全なJPEG/GIF外形ならTrueを返す。"""
    if media_type == "image/jpeg":
        return (
            len(payload) >= 4
            and payload.startswith(b"\xff\xd8")
            and payload.endswith(b"\xff\xd9")
        )
    return (
        len(payload) >= 7
        and payload[:6] in {b"GIF87a", b"GIF89a"}
        and payload.endswith(b";")
    )


def _decode_image_pixels(
    payload: bytes,
    media_type: str,
) -> tuple[tuple[int, int], tuple[bytes, ...]] | None:
    """JPEG/GIF bytesを上限内でdecodeし、寸法と全frameのRGBA画素列を返す。"""
    expected_format = "JPEG" if media_type == "image/jpeg" else "GIF"
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(payload)) as image:
                if image.format != expected_format:
                    return None
                width, height = image.size
                frame_count = getattr(image, "n_frames", 1)
                if width * height * frame_count > MAX_DECODED_IMAGE_PIXELS:
                    return None
                frames: list[bytes] = []
                for frame_index in range(frame_count):
                    image.seek(frame_index)
                    frames.append(image.convert("RGBA").tobytes())
                return (width, height), tuple(frames)
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        OSError,
        UnidentifiedImageError,
        ValueError,
    ):
        return None


def judge_image(
    judge_specification: ImageJudgeSpecification,
    expected_artifact: bytes,
    actual_artifact: ExecutionArtifact | None,
) -> JudgeResult:
    """画像仕様・正解bytes・取得artifactを副作用なく全画素比較して結果を返す。

    入力artifactの欠損、path・MIME不一致、Base64・画像形式破損はwrong imageとし、
    schemaで明示されたexact_pixels方式では寸法・frame数・RGBA画素の一致を要求する。
    """
    if actual_artifact is None:
        return JudgeResult(
            verdict=JudgeVerdict.WRONG_IMAGE,
            reason=JudgeReason.ARTIFACT_MISSING,
        )
    specification = judge_specification.artifact
    if actual_artifact.path != specification.path:
        return JudgeResult(
            verdict=JudgeVerdict.WRONG_IMAGE,
            reason=JudgeReason.ARTIFACT_PATH_MISMATCH,
        )
    if actual_artifact.media_type != specification.media_type:
        return JudgeResult(
            verdict=JudgeVerdict.WRONG_IMAGE,
            reason=JudgeReason.ARTIFACT_MEDIA_TYPE_MISMATCH,
        )
    try:
        payload = base64.b64decode(actual_artifact.data, validate=True)
    except (binascii.Error, ValueError):
        return JudgeResult(
            verdict=JudgeVerdict.WRONG_IMAGE,
            reason=JudgeReason.ARTIFACT_INVALID,
        )
    if not _matches_media_type(payload, specification.media_type):
        return JudgeResult(
            verdict=JudgeVerdict.WRONG_IMAGE,
            reason=JudgeReason.ARTIFACT_INVALID,
        )
    actual_pixels = _decode_image_pixels(payload, specification.media_type)
    expected_pixels = _decode_image_pixels(
        expected_artifact,
        specification.media_type,
    )
    if actual_pixels is None or expected_pixels is None:
        return JudgeResult(
            verdict=JudgeVerdict.WRONG_IMAGE,
            reason=JudgeReason.ARTIFACT_INVALID,
        )
    if actual_pixels == expected_pixels:
        return JudgeResult(verdict=JudgeVerdict.ACCEPTED)
    return JudgeResult(
        verdict=JudgeVerdict.WRONG_IMAGE,
        reason=JudgeReason.IMAGE_MISMATCH,
    )


class ShellgeiJudge:
    """problem取得を行い、純粋なtextまたはimage judgeへ委譲する。"""

    def __init__(self, problem_repository: ProblemRepository | None = None) -> None:
        """任意の検証済みrepositoryを受け取り、未指定ならprocess globalを遅延参照する。"""
        self.problem_repository = problem_repository

    def _repository(self) -> ProblemRepository:
        """注入済みrepositoryを返し、未指定なら起動時にloadしたrepositoryを返す。"""
        return self.problem_repository or get_problem_repository()

    def judge(
        self,
        execution: ExecutionResult,
        problem_id: str,
    ) -> JudgeResult:
        """構造化実行結果とproblem IDを受け取り、型付き判定結果を返す。

        text問題はartifactを参照せず、画像問題はstdoutを参照しない純粋関数へ
        委譲する。不正ID・未登録IDはjudge errorとして返す。
        """
        try:
            validate_problem_id(problem_id)
        except ValueError:
            return JudgeResult(
                verdict=JudgeVerdict.JUDGE_ERROR,
                reason=JudgeReason.INVALID_PROBLEM_ID,
            )
        record = self._repository().get(problem_id)
        if record is None:
            return JudgeResult(
                verdict=JudgeVerdict.JUDGE_ERROR,
                reason=JudgeReason.PROBLEM_NOT_FOUND,
            )
        definition = record.definition
        if execution.status is ExecutionStatus.ERROR:
            return JudgeResult(
                verdict=JudgeVerdict.EXECUTION_FAILURE,
                reason=JudgeReason.EXECUTION_ERROR,
            )
        policy_input = TextJudgeInput(
            stdout=execution.stdout,
            stderr=execution.stderr,
            exit_code=execution.exit_code or 0,
            timed_out=execution.timed_out,
            truncated=execution.truncated,
        )
        if definition.judge.type == "text":
            return judge_text(
                definition.judge,
                definition.execution,
                policy_input,
            )
        execution_failure = _execution_policy_failure(
            definition.execution,
            policy_input,
        )
        if execution_failure is not None:
            return execution_failure
        return judge_image(
            definition.judge,
            record.answer_image,
            execution.artifact,
        )
