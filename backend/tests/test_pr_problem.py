"""prの列ごとの読順を独立に照合し、公開DTOと実行policyを検査する。"""

from pathlib import Path

from PIL import Image

from soj_shared.problem_repository import build_problem_repository
from soj_shared.problem_schema import load_problem_definition

PROBLEMS = Path(__file__).resolve().parents[2] / "problems"
PROBLEM_ID = "PRACTICE-pr-01"


def test_pr_problem_has_independently_verified_expected_output() -> None:
    """手確認した左右の対応と行番号の計算で、奇数の余り・順序・重複を照合する。"""
    definition = load_problem_definition(PROBLEMS / "v3" / f"{PROBLEM_ID}.yaml")
    left = ["oak", "maple tree", "elm", "cedar", "pine"]
    right = ["ash", "birch", "oak", "willow"]
    fixture = definition.execution.fixtures[0].content
    assert fixture.splitlines() == left + right
    expected = "oak | ash\nmaple tree | birch\nelm | oak\ncedar | willow\npine\n"
    lines = fixture.splitlines()
    split = (len(lines) + 1) // 2
    calculated = "".join(
        value + (" | " + lines[i + split] if i + split < len(lines) else "") + "\n"
        for i, value in enumerate(lines[:split])
    )
    assert calculated == expected
    assert definition.judge.type == "text"
    assert definition.judge.expected_output == expected
    assert len(fixture.encode()) == 51
    assert len(expected.encode()) == 59


def test_pr_problem_public_contract_and_preview() -> None:
    """日英の説明・入出力・正常終了policyと白JPEGを公開契約どおりに保持する。"""
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(PROBLEM_ID)
    definition = record.definition
    assert definition.title.ja == definition.title.en == "pr 1"
    assert definition.statement.ja and definition.statement.en
    assert definition.execution.stdin == ""
    assert definition.execution.exit_code == "zero"
    assert definition.execution.stderr == "must_be_empty"
    assert len(definition.execution.fixtures) == 1
    fixture = definition.execution.fixtures[0]
    assert fixture.path == "input.txt"
    assert record.api_detail()["input"] == fixture.content
    assert record.api_detail()["expected_output"] == record.expected_output
    assert record.api_detail()["answer"] == definition.reference_solution
    assert len(definition.reference_solution) <= 1000
    with Image.open(PROBLEMS / "image" / f"{PROBLEM_ID}.jpg") as image:
        image.load()
        assert image.format == "JPEG"
        assert image.convert("RGB").getextrema() == ((255, 255),) * 3
