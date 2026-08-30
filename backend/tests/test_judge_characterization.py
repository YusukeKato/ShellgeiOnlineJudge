import base64
from pathlib import Path
from types import MappingProxyType

import pytest

from models.problem import ExecutionSpecification, TextJudgeSpecification
from scripts.judge import JudgeReason, JudgeResult, JudgeVerdict, ShellgeiJudge
from scripts.problem_catalog import build_problem_catalog
from scripts.problem_repository import ProblemRecord, ProblemRepository
from scripts.problem_schema import load_problem_definition
from scripts.runner_protocol import ExecutionArtifact


TEXT_PROBLEM_ID = "STANDARD-00000001"
IMAGE_PROBLEM_ID = "IMAGE-00000001"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TEXT_DEFINITION = load_problem_definition(
    REPOSITORY_ROOT / "problems/v3" / f"{TEXT_PROBLEM_ID}.yaml"
)
IMAGE_DEFINITION = load_problem_definition(
    REPOSITORY_ROOT / "problems/v3" / f"{IMAGE_PROBLEM_ID}.yaml"
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
        "expected",
        artifact,
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

    assert judge.judge(output, None, problem_id).verdict is JudgeVerdict.ACCEPTED


def test_text_judge_keeps_tabs_significant() -> None:
    # タブは通常の空白と同一視されず、文字列不一致になることを確認する。
    judge, _, problem_id = _repository_judge(expected_output="a b")

    result = judge.judge("a\tb", None, problem_id)

    assert result.verdict is JudgeVerdict.WRONG_ANSWER
    assert result.reason is JudgeReason.OUTPUT_MISMATCH


def test_text_judge_accepts_empty_output_and_answer() -> None:
    # 利用者出力と期待出力が両方空の場合に正解となることを確認する。
    judge, _, problem_id = _repository_judge(expected_output="")

    assert judge.judge("", None, problem_id).verdict is JudgeVerdict.ACCEPTED


def test_text_judge_does_not_collide_with_replacement_token_literals() -> None:
    # 実際の空白とliteral文字列SPACEを異なる出力として判定することを確認する。
    judge, _, problem_id = _repository_judge(expected_output="SPACE")

    assert judge.judge(" ", None, problem_id).verdict is JudgeVerdict.WRONG_ANSWER


def test_text_judge_does_not_match_literal_null_to_empty_answer() -> None:
    # 空出力とliteral文字列NULLを異なる出力として判定することを確認する。
    judge, _, problem_id = _repository_judge(expected_output="")

    assert judge.judge("NULL", None, problem_id).verdict is JudgeVerdict.WRONG_ANSWER


def test_repository_adapter_fails_closed_for_not_yet_captured_policies() -> None:
    # runnerが構造化していない終了code policyを暗黙に成功扱いしないことを確認する。
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

    result = ShellgeiJudge(repository).judge("expected", None, problem_id)

    assert result.verdict is JudgeVerdict.JUDGE_ERROR
    assert result.reason is JudgeReason.STRUCTURED_EXECUTION_UNAVAILABLE
