import base64
from pathlib import Path
from types import MappingProxyType

import pytest

from soj_shared.models.problem import ExecutionSpecification, TextJudgeSpecification
from soj_shared.models.execution import (
    ExecutionArtifact,
    ExecutionResult,
    ExecutionStatus,
)
from soj_backend.judge import JudgeReason, JudgeResult, JudgeVerdict, ShellgeiJudge
from soj_shared.problem_catalog import build_problem_catalog
from soj_shared.problem_repository import ProblemRecord, ProblemRepository
from soj_shared.problem_schema import load_problem_definition


TEXT_PROBLEM_ID = "STANDARD-00000001"
IMAGE_PROBLEM_ID = "IMAGE-00000001"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TEXT_DEFINITION = load_problem_definition(
    REPOSITORY_ROOT / "problems/v3" / f"{TEXT_PROBLEM_ID}.yaml"
)
IMAGE_DEFINITION = load_problem_definition(
    REPOSITORY_ROOT / "problems/v3" / f"{IMAGE_PROBLEM_ID}.yaml"
)


def _execution_result(
    stdout: str,
    artifact: ExecutionArtifact | None = None,
    *,
    stderr: str = "",
    exit_code: int = 0,
) -> ExecutionResult:
    # 任意の分離出力・終了code・artifactから、正常完了した実行結果を返す。
    return ExecutionResult(
        status=ExecutionStatus.COMPLETED,
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        timed_out=False,
        truncated=False,
        duration_ms=1,
        artifact=artifact,
        error=None,
    )


def _repository_judge(
    *,
    expected_output: str = "expected",
    answer_image: bytes = b"answer-image" * 4,
    image_problem: bool = False,
) -> tuple[ShellgeiJudge, str, str]:
    # 任意のtext期待値または画像を持つ不変repositoryを作り、judge・画像・IDを返す。
    if image_problem:
        definition = IMAGE_DEFINITION
        problem_id = IMAGE_PROBLEM_ID
    else:
        definition = TEXT_DEFINITION.model_copy(
            update={
                "judge": TextJudgeSpecification(
                    type="text",
                    expected_output=expected_output,
                )
            }
        )
        problem_id = TEXT_PROBLEM_ID
    answer_image_base64 = base64.b64encode(answer_image).decode("ascii")
    record = ProblemRecord(
        definition=definition,
        answer_image=answer_image,
        answer_image_base64=answer_image_base64,
    )
    repository = ProblemRepository(
        records=MappingProxyType({problem_id: record}),
        revision="test-revision",
        catalog=build_problem_catalog([definition]),
    )
    return ShellgeiJudge(repository), answer_image_base64, problem_id


@pytest.mark.parametrize("image_matches", [True, False])
def test_text_judge_does_not_depend_on_image(image_matches: bool) -> None:
    # text問題では画像の一致状態にかかわらず、stdout一致だけで正解になることを確認する。
    judge, matching_image, problem_id = _repository_judge()
    artifact = ExecutionArtifact(
        path="media/output.jpg",
        media_type="image/jpeg",
        data=matching_image if image_matches else "different-image",
    )

    result = judge.judge(
        _execution_result("expected", artifact),
        problem_id,
    )

    assert result == JudgeResult(verdict=JudgeVerdict.ACCEPTED)


@pytest.mark.parametrize(
    "output",
    [
        "expected",
        "expected\n",
        "expected\n\n",
        "expected ",
        "expected\r\n",
    ],
)
def test_text_judge_ignores_carriage_returns_and_trailing_spaces_or_newlines(
    output: str,
) -> None:
    # CRと末尾の空白・改行だけを除外し、期待出力と比較することを確認する。
    judge, _, problem_id = _repository_judge(expected_output="expected\n")

    assert (
        judge.judge(_execution_result(output), problem_id).verdict
        is JudgeVerdict.ACCEPTED
    )


def test_text_judge_keeps_tabs_significant() -> None:
    # タブは通常の空白と同一視されず、文字列不一致になることを確認する。
    judge, _, problem_id = _repository_judge(expected_output="a b")

    result = judge.judge(_execution_result("a\tb"), problem_id)

    assert result.verdict is JudgeVerdict.WRONG_ANSWER
    assert result.reason is JudgeReason.OUTPUT_MISMATCH


def test_text_judge_accepts_empty_output_and_answer() -> None:
    # 利用者出力と期待出力が両方空の場合に正解となることを確認する。
    judge, _, problem_id = _repository_judge(expected_output="")

    assert (
        judge.judge(_execution_result(""), problem_id).verdict is JudgeVerdict.ACCEPTED
    )


def test_text_judge_does_not_collide_with_replacement_token_literals() -> None:
    # 実際の空白とliteral文字列SPACEを異なる出力として判定することを確認する。
    judge, _, problem_id = _repository_judge(expected_output="SPACE")

    assert (
        judge.judge(_execution_result(" "), problem_id).verdict
        is JudgeVerdict.WRONG_ANSWER
    )


def test_text_judge_does_not_match_literal_null_to_empty_answer() -> None:
    # 空出力とliteral文字列NULLを異なる出力として判定することを確認する。
    judge, _, problem_id = _repository_judge(expected_output="")

    assert (
        judge.judge(_execution_result("NULL"), problem_id).verdict
        is JudgeVerdict.WRONG_ANSWER
    )


def test_repository_adapter_applies_structured_exit_code_policy() -> None:
    # repository経由の判定が構造化された非0終了codeを実行失敗にすることを確認する。
    judge, _, problem_id = _repository_judge()
    assert judge.problem_repository is not None
    record = judge.problem_repository.require(problem_id)
    definition = record.definition.model_copy(
        update={
            "execution": ExecutionSpecification(
                stdin="",
                fixtures=(),
                exit_code="zero",
                stderr="merge",
            )
        }
    )
    repository = ProblemRepository(
        records=MappingProxyType(
            {
                problem_id: ProblemRecord(
                    definition=definition,
                    answer_image=record.answer_image,
                    answer_image_base64=record.answer_image_base64,
                )
            }
        ),
        revision="test-revision",
        catalog=build_problem_catalog([definition]),
    )

    result = ShellgeiJudge(repository).judge(
        _execution_result("expected", exit_code=7),
        problem_id,
    )

    assert result.verdict is JudgeVerdict.EXECUTION_FAILURE
    assert result.reason is JudgeReason.NON_ZERO_EXIT
