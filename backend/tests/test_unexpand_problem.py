"""行頭の空白数から公開問題の想定出力を独立に確認する。"""

from pathlib import Path

from soj_shared.problem_repository import build_problem_repository


PROBLEMS = Path(__file__).resolve().parents[2] / "problems"
PROBLEM_ID = "PRACTICE-unexpand-01"


def visible_indents(original: str) -> str:
    """行頭スペース数を4で割った商と余りから表示を作り、本文と改行を保つ。"""
    result = []
    for line in original.splitlines(keepends=True):
        body = line.lstrip(" ")
        tabs, spaces = divmod(len(line) - len(body), 4)
        result.append("^I" * tabs + " " * spaces + body)
    return "".join(result)


def test_public_unexpand_example() -> None:
    """公開fixtureの字下げと本文の空白を固定し、日英タイトル・入力・想定出力を確認する。"""
    repo = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repo.require(PROBLEM_ID)
    detail = record.api_detail()
    fixture = "    alpha    beta\n        gamma delta\n      epsilon   zeta\n  eta theta\nplain   text\n"
    assert detail["input"] == fixture
    assert detail["expected_output"] == visible_indents(fixture)
    assert detail["title_ja"] == detail["title_en"] == "unexpand 1"
    assert record.definition.execution.exit_code == "zero"
    assert record.definition.execution.stderr == "must_be_empty"
