"""printfの期待値を独立に照合し、公開DTO・policy・表示画像を検査する。"""

import json
from pathlib import Path

from PIL import Image

from soj_shared.problem_repository import build_problem_repository
from soj_shared.problem_schema import load_problem_definition

PROBLEMS = Path(__file__).resolve().parents[2] / "problems"
PROBLEM_ID = "PRACTICE-printf-01"


def test_printf_problem_has_independently_verified_expected_output() -> None:
    """手確認した4行の表とJSON decoderから、タブ・改行・%・二重解釈の区別を確認する。"""
    definition = load_problem_definition(PROBLEMS / "v3" / f"{PROBLEM_ID}.yaml")
    fixture = definition.execution.fixtures[0].content
    rows = [
        ("name", "value"),
        ("rate", "100%"),
        ("path", r"C:\logs\app"),
        ("literal", r"\n"),
    ]
    expected = "".join(key + "\t" + value + "\n" for key, value in rows)
    assert json.loads('"' + fixture.rstrip("\n") + '"') == expected
    assert definition.judge.type == "text"
    assert definition.judge.expected_output == expected
    assert expected.count("\t") == expected.count("\n") == 4


def test_printf_problem_public_contract_and_preview() -> None:
    """日英の問題文・入出力・正常終了policyと白JPEGを公開契約どおりに保持する。"""
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(PROBLEM_ID)
    definition = record.definition
    assert definition.title.ja == definition.title.en == "printf 1"
    assert definition.statement.ja and definition.statement.en
    assert definition.execution.stdin == ""
    assert definition.execution.exit_code == "zero"
    assert definition.execution.stderr == "must_be_empty"
    assert len(definition.execution.fixtures) == 1
    fixture = definition.execution.fixtures[0]
    assert fixture.path == "input.txt"
    assert record.api_detail()["input"] == fixture.content
    assert record.api_detail()["expected_output"] == record.expected_output
    assert len(definition.reference_solution) <= 1000
    with Image.open(PROBLEMS / "image" / f"{PROBLEM_ID}.jpg") as image:
        image.load()
        assert image.format == "JPEG"
        assert image.convert("RGB").getextrema() == ((255, 255),) * 3
