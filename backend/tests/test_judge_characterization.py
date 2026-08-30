import base64
from pathlib import Path
from types import MappingProxyType

import pytest

from models.problem import TextJudgeSpecification
from scripts.judge import ShellgeiJudge
from scripts.problem_catalog import build_problem_catalog
from scripts.problem_repository import ProblemRecord, ProblemRepository
from scripts.problem_schema import load_problem_definition


PROBLEM_ID = "STANDARD-00000001"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BASE_DEFINITION = load_problem_definition(
    REPOSITORY_ROOT / "problems/v3" / f"{PROBLEM_ID}.yaml"
)


def _judge_fixture(
    *,
    expected_output: str = "expected",
    answer_image: bytes = b"answer-image" * 4,
) -> tuple[ShellgeiJudge, str]:
    # 任意の期待出力・画像を持つ不変repositoryを組み立て、judgeと比較用Base64画像を返す。
    definition = BASE_DEFINITION.model_copy(
        update={
            "judge": TextJudgeSpecification(
                type="text",
                expected_output=expected_output,
            )
        }
    )
    answer_image_base64 = base64.b64encode(answer_image).decode("ascii")
    record = ProblemRecord(
        definition=definition,
        answer_image=answer_image,
        answer_image_base64=answer_image_base64,
    )
    repository = ProblemRepository(
        records=MappingProxyType({PROBLEM_ID: record}),
        revision="test-revision",
        catalog=build_problem_catalog([definition]),
    )
    return ShellgeiJudge(repository), answer_image_base64


@pytest.mark.parametrize(
    "text_matches,image_matches,expected_verdict",
    [
        (True, True, "1"),
        (True, False, "2"),
        (False, True, "3"),
        (False, False, "4"),
    ],
)
def test_legacy_judge_verdict_truth_table(
    text_matches: bool,
    image_matches: bool,
    expected_verdict: str,
) -> None:
    # テキストと画像の一致・不一致の組み合わせが従来の判定番号になることを確認する。
    judge, matching_image = _judge_fixture()
    different_image = base64.b64encode(b"different-image" * 4).decode("ascii")

    assert (
        judge.judge(
            "expected" if text_matches else "different",
            matching_image if image_matches else different_image,
            PROBLEM_ID,
        )
        == expected_verdict
    )


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
def test_legacy_judge_ignores_carriage_returns_and_trailing_spaces_or_newlines(
    output: str,
) -> None:
    # CRと末尾の空白・改行を除外して比較する従来の文字列判定を確認する。
    judge, image = _judge_fixture(expected_output="expected\n")

    assert judge.judge(output, image, PROBLEM_ID) == "1"


def test_legacy_judge_keeps_tabs_significant() -> None:
    # タブは通常の空白と同一視されず、文字列不一致になることを確認する。
    judge, image = _judge_fixture(expected_output="a b")

    assert judge.judge("a\tb", image, PROBLEM_ID) == "3"


def test_legacy_judge_maps_empty_output_and_answer_to_null() -> None:
    # 利用者出力と期待出力が両方空の場合に正解となることを確認する。
    judge, image = _judge_fixture(expected_output="")

    assert judge.judge("", image, PROBLEM_ID) == "1"


@pytest.mark.xfail(
    strict=True,
    reason="SOJ-009: replacement tokens can collide with literal output",
)
def test_known_bug_replacement_token_must_not_false_accept() -> None:
    # 実際の空白と文字列SPACEが衝突して誤って正解になる既知不具合を追跡する。
    judge, image = _judge_fixture(expected_output="SPACE")

    assert judge.judge(" ", image, PROBLEM_ID) != "1"


@pytest.mark.xfail(
    strict=True,
    reason="SOJ-009: literal NULL collides with an empty expected output",
)
def test_known_bug_literal_null_must_not_match_empty_answer() -> None:
    # 空出力の内部表現と文字列NULLが衝突して誤って正解になる既知不具合を追跡する。
    judge, image = _judge_fixture(expected_output="")

    assert judge.judge("NULL", image, PROBLEM_ID) != "1"


@pytest.mark.xfail(
    strict=True,
    reason="SOJ-009: the first 28 Base64 characters are excluded from comparison",
)
def test_known_bug_image_prefix_difference_must_not_be_ignored() -> None:
    # 画像先頭21 byteだけの違いを検出できない既知不具合を追跡する。
    suffix = b"same-image-suffix"
    judge, _ = _judge_fixture(answer_image=b"A" * 21 + suffix)
    different_prefix = base64.b64encode(b"B" * 21 + suffix).decode("ascii")

    assert judge.judge("expected", different_prefix, PROBLEM_ID) != "1"
