"""カテゴリ別首位を全商品の比較から独立に確認し、表示と判定の契約を検査する。"""

from pathlib import Path

import pytest
from PIL import Image

from soj_backend.judge import JudgeVerdict, TextJudgeInput, judge_text
from soj_shared.problem_repository import build_problem_repository
from soj_shared.problem_schema import load_problem_definition


PROBLEMS = Path(__file__).resolve().parents[2] / "problems"
PROBLEM_ID = "STANDARD-00000069"
OUTPUT = (
    "books atlas 12\nbooks guide 12\nfood tea 7\ngames cards 12\n"
    "games chess 12\ngames word 12\ntools saw 100\n"
)


def test_sales_leaders_fixture_policy_and_preview() -> None:
    # 詳細APIが入力を保持し、正常終了policyと白JPEGが現行の問題画面に適合することを確認する。
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(PROBLEM_ID)
    definition = record.definition
    assert definition.category == "STANDARD"
    assert definition.judge.type == "text"
    assert definition.execution.stdin == ""
    assert definition.execution.exit_code == "zero"
    assert definition.execution.stderr == "must_be_empty"
    assert len(definition.execution.fixtures) == 1
    fixture = definition.execution.fixtures[0]
    assert fixture.path == "input.txt"
    assert record.api_detail()["input"] == fixture.content
    assert record.api_detail()["expected_output"] == OUTPUT
    assert len(definition.reference_solution) <= 1000
    with Image.open(PROBLEMS / "image" / f"{PROBLEM_ID}.jpg") as image:
        image.load()
        assert image.format == "JPEG"
        assert image.convert("RGB").getextrema() == ((255, 255),) * 3


def test_sales_leaders_expected_output_from_independent_comparisons() -> None:
    # 同カテゴリに売上が上回る商品がない行を選び、sortで先頭値を拾う参照解とは独立に確認する。
    definition = load_problem_definition(PROBLEMS / "v3" / f"{PROBLEM_ID}.yaml")
    rows = [
        (category, product, int(sales))
        for category, product, sales in (
            line.split()
            for line in definition.execution.fixtures[0].content.splitlines()
        )
    ]
    winners = [
        (category, product, sales)
        for category, product, sales in rows
        if not any(
            other_category == category and other_sales > sales
            for other_category, _, other_sales in rows
        )
    ]
    assert set(winners) == {
        ("books", "atlas", 12),
        ("books", "guide", 12),
        ("food", "tea", 7),
        ("games", "cards", 12),
        ("games", "chess", 12),
        ("games", "word", 12),
        ("tools", "saw", 100),
    }
    expected = "".join(
        f"{category} {product} {sales}\n"
        for category, product, sales in sorted(winners)
    )
    assert definition.judge.type == "text"
    assert definition.judge.expected_output == expected == OUTPUT
    assert len(rows) == 13
    assert len({(category, product) for category, product, _ in rows}) == len(rows)
    assert rows != sorted(rows)


@pytest.mark.parametrize(
    "execution,verdict",
    [
        (TextJudgeInput(stdout=OUTPUT), JudgeVerdict.ACCEPTED),
        (TextJudgeInput(stdout=OUTPUT.rstrip("\n")), JudgeVerdict.ACCEPTED),
        (
            TextJudgeInput(
                stdout="books atlas 12\nfood tea 7\ngames cards 12\ntools saw 100\n"
            ),
            JudgeVerdict.WRONG_ANSWER,
        ),
        (TextJudgeInput(stdout="tools saw 100\n"), JudgeVerdict.WRONG_ANSWER),
        (
            TextJudgeInput(stdout=OUTPUT.replace("tools saw 100", "tools plane 9")),
            JudgeVerdict.WRONG_ANSWER,
        ),
        (
            TextJudgeInput(
                stdout=OUTPUT.replace(
                    "books atlas 12\nbooks guide 12", "books guide 12\nbooks atlas 12"
                )
            ),
            JudgeVerdict.WRONG_ANSWER,
        ),
        (TextJudgeInput(stdout=OUTPUT, exit_code=1), JudgeVerdict.EXECUTION_FAILURE),
        (
            TextJudgeInput(stdout=OUTPUT, stderr="warning\n"),
            JudgeVerdict.EXECUTION_FAILURE,
        ),
    ],
)
def test_sales_leaders_judge_ties_numeric_values_order_and_execution(
    execution: TextJudgeInput, verdict: JudgeVerdict
) -> None:
    # 同率の欠落、全体最大値、辞書順の売上比較、商品順の逆転と非0終了・stderrを拒否する。
    definition = load_problem_definition(PROBLEMS / "v3" / f"{PROBLEM_ID}.yaml")
    assert definition.judge.type == "text"
    assert (
        judge_text(definition.judge, definition.execution, execution).verdict is verdict
    )
