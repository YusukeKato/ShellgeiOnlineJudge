"""巡回配分とBash引数表記の独立期待値、公開契約と白JPEGを検査する。"""

from pathlib import Path
from PIL import Image
import pytest
from soj_shared.problem_repository import build_problem_repository
from soj_shared.problem_schema import load_problem_definition

PROBLEMS = Path(__file__).resolve().parents[2] / "problems"
IDS = ("PRACTICE-split-01", "PRACTICE-printf-02")


def test_split_expected_output_uses_independent_line_positions() -> None:
    """空行も数えて1/4/7・2/5/8・3/6行目へ配分し、重複と元の順序を保つ。"""
    definition = load_problem_definition(PROBLEMS / "v3/PRACTICE-split-01.yaml")
    lines = definition.execution.fixtures[0].content.split("\n")[:-1]
    lanes = [
        [lines[index - 1] for index in positions]
        for positions in ((1, 4, 7), (2, 5, 8), (3, 6))
    ]
    assert lanes == [
        ["build api", "lint backend", "scan image"],
        ["test ui", "build api", "test api"],
        ["", "deploy docs"],
    ]
    expected = "".join(
        f"[part_{index}]\n" + "".join(line + "\n" for line in lane)
        for index, lane in enumerate(lanes)
    )
    assert definition.judge.type == "text"
    assert definition.judge.expected_output == expected


def test_printf_q_expected_output_uses_manual_character_mapping() -> None:
    """空文字・行頭space・各記号の対応を手で固定し、printfの実行結果に依存しない。"""
    definition = load_problem_definition(PROBLEMS / "v3/PRACTICE-printf-02.yaml")
    lines = definition.execution.fixtures[0].content.split("\n")[:-1]
    expected = [
        ("annual report.txt", r"annual\ report.txt"),
        ("plain.txt", "plain.txt"),
        ("draft[old].txt", r"draft\[old\].txt"),
        ("price$usd.txt", r"price\$usd.txt"),
        ("O'Reilly.txt", r"O\'Reilly.txt"),
        ("", "''"),
        ("notes\\backup.txt", r"notes\\backup.txt"),
        ("*.log", r"\*.log"),
        ("  draft.txt", r"\ \ draft.txt"),
    ]
    assert lines == [source for source, _ in expected]
    assert definition.judge.type == "text"
    assert definition.judge.expected_output == "".join(
        target + "\n" for _, target in expected
    )


@pytest.mark.parametrize("problem_id", IDS)
def test_split_and_printf_public_contract_and_preview(problem_id: str) -> None:
    """日英の形式説明、入力・回答例、正常終了policyと表示用白JPEGを保持する。"""
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(problem_id)
    definition = record.definition
    assert (
        definition.title.ja
        == definition.title.en
        == ("split 1" if problem_id == IDS[0] else "printf 2")
    )
    for statement in (definition.statement.ja, definition.statement.en):
        assert "input.txt" in statement
        assert all(
            value in statement
            for value in (
                ("part_0", "part_1", "part_2") if problem_id == IDS[0] else ("%q", "''")
            )
        )
    assert definition.execution.stdin == ""
    assert definition.execution.exit_code == "zero"
    assert definition.execution.stderr == "must_be_empty"
    assert len(definition.execution.fixtures) == 1
    fixture = definition.execution.fixtures[0]
    assert fixture.path == "input.txt"
    detail = record.api_detail()
    assert detail["input"] == fixture.content
    assert detail["expected_output"] == record.expected_output
    assert detail["answer"] == definition.reference_solution
    assert detail["image"] == f"/image/{problem_id}.jpg"
    assert len(definition.reference_solution) <= 1000
    with Image.open(PROBLEMS / "image" / f"{problem_id}.jpg") as image:
        image.load()
        assert image.format == "JPEG"
        assert image.convert("RGB").getextrema() == ((255, 255),) * 3
