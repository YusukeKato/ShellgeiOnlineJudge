#!/usr/bin/env python3
from enum import Enum

from pydantic import BaseModel, ConfigDict

from models.problem import ExecutionSpecification, TextJudgeSpecification
from scripts.input_validation import validate_problem_id
from scripts.problem_repository import ProblemRepository, get_problem_repository


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
    NON_ZERO_EXIT = "non_zero_exit"
    STDERR_NOT_EMPTY = "stderr_not_empty"
    TIMED_OUT = "timed_out"
    OUTPUT_TRUNCATED = "output_truncated"
    STRUCTURED_EXECUTION_UNAVAILABLE = "structured_execution_unavailable"
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


def _normalize_image_text_legacy(value: str) -> str:
    """画像問題の文字列をR3-011まで従来の置換順で正規化して返す。"""
    normalized = value.replace("\r", "")
    for source, target in (
        (" ", "SPACE"),
        ("\n", "NEWLINE"),
        ("\t", "TAB"),
        ("<", "LT"),
        (">", "GT"),
    ):
        normalized = normalized.replace(source, target)
    while normalized.endswith("NEWLINE"):
        normalized = normalized.removesuffix("NEWLINE")
    while normalized.endswith("SPACE"):
        normalized = normalized.removesuffix("SPACE")
    return normalized


def judge_text(
    judge_specification: TextJudgeSpecification,
    execution_specification: ExecutionSpecification,
    execution: TextJudgeInput,
) -> JudgeResult:
    """text問題の仕様と実行結果を副作用なく比較し、型付き判定結果を返す。

    入力は期待出力、終了code・stderr policy、構造化されたstdout等。fileや
    repositoryを参照せず、timeout、切り詰め、policy違反、出力差を順に判定する。
    """
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


class ShellgeiJudge:
    """problem取得を行い、純粋text judgeまたはlegacy image judgeへ委譲する。"""

    def __init__(self, problem_repository: ProblemRepository | None = None) -> None:
        """任意の検証済みrepositoryを受け取り、未指定ならprocess globalを遅延参照する。"""
        self.problem_repository = problem_repository

    def _repository(self) -> ProblemRepository:
        """注入済みrepositoryを返し、未指定なら起動時にloadしたrepositoryを返す。"""
        return self.problem_repository or get_problem_repository()

    @staticmethod
    def _judge_image_legacy(
        output_str: str,
        output_image: str,
        answer_image: str,
    ) -> JudgeResult:
        """画像問題をR3-011まで従来方式で比較し、型付き判定結果を返す。"""
        text_matches = _normalize_image_text_legacy(output_str or "NULL") == "NULL"
        image_matches = output_image[28:] == answer_image[28:]
        if text_matches and image_matches:
            return JudgeResult(verdict=JudgeVerdict.ACCEPTED)
        if text_matches:
            return JudgeResult(
                verdict=JudgeVerdict.WRONG_IMAGE,
                reason=JudgeReason.IMAGE_MISMATCH,
            )
        if image_matches:
            return JudgeResult(
                verdict=JudgeVerdict.WRONG_ANSWER,
                reason=JudgeReason.OUTPUT_MISMATCH,
            )
        return JudgeResult(
            verdict=JudgeVerdict.WRONG_TEXT_AND_IMAGE,
            reason=JudgeReason.OUTPUT_AND_IMAGE_MISMATCH,
        )

    def judge(
        self,
        output_str: str,
        output_image: str,
        problem_id: str,
    ) -> JudgeResult:
        """実行出力とproblem IDを受け取り、型付き判定結果を返す。

        text問題は画像を参照せず純粋関数で比較する。画像問題はR3-011で置換する
        legacy比較へ委譲し、不正ID・未登録IDはjudge errorとして返す。
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
        if definition.judge.type == "text":
            if (
                definition.execution.exit_code != "ignore"
                or definition.execution.stderr != "merge"
            ):
                return JudgeResult(
                    verdict=JudgeVerdict.JUDGE_ERROR,
                    reason=JudgeReason.STRUCTURED_EXECUTION_UNAVAILABLE,
                )
            return judge_text(
                definition.judge,
                definition.execution,
                TextJudgeInput(stdout=output_str),
            )
        return self._judge_image_legacy(
            output_str,
            output_image,
            record.answer_image_base64,
        )
