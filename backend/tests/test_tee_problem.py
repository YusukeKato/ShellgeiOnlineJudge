"""tee練習の独立期待値、公開契約と表示用白JPEGを検査する。"""

from pathlib import Path

from PIL import Image

from soj_shared.problem_repository import build_problem_repository
from soj_shared.problem_schema import load_problem_definition

PROBLEMS = Path(__file__).resolve().parents[2] / "problems"
PROBLEM_ID = "PRACTICE-tee-01"


def test_tee_problem_has_independently_verified_expected_output() -> None:
    """入力行の位置とLF数から、コメントだけを除いた本文と6行の件数を独立に照合する。"""
    definition = load_problem_definition(PROBLEMS / "v3" / f"{PROBLEM_ID}.yaml")
    fixture = definition.execution.fixtures[0].content
    lines = fixture.splitlines(keepends=True)
    retained = [(index, line) for index, line in enumerate(lines, 1) if line[:1] != "#"]
    assert [index for index, _ in retained] == [2, 4, 5, 6, 7, 8]
    body = "".join(line for _, line in retained)
    assert body == "start\nalpha beta\n\nstart\n  # keep\nend\n"
    count = body.count("\n")
    assert count == 6 and len(lines) == 9
    assert definition.judge.type == "text"
    assert definition.judge.expected_output == body + f"LINES {count}\n"


def test_tee_problem_public_contract_and_preview() -> None:
    """日英の説明・単一入力・公開回答例・正常終了policyと白JPEGを保持する。"""
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(PROBLEM_ID)
    definition = record.definition
    assert definition.title.ja == definition.title.en == "tee 1"
    for statement in (definition.statement.ja, definition.statement.en):
        assert "input.txt" in statement and "preview.txt" in statement
        assert "#" in statement and "LINES" in statement
    assert definition.execution.stdin == ""
    assert definition.execution.exit_code == "zero"
    assert definition.execution.stderr == "must_be_empty"
    assert len(definition.execution.fixtures) == 1
    fixture = definition.execution.fixtures[0]
    assert fixture.path == "input.txt" and fixture.content.endswith("\n")
    detail = record.api_detail()
    assert detail["input"] == fixture.content
    assert detail["expected_output"] == record.expected_output
    assert detail["answer"] == definition.reference_solution
    assert detail["image"] == f"/image/{PROBLEM_ID}.jpg"
    assert len(definition.reference_solution) <= 1000
    with Image.open(PROBLEMS / "image" / f"{PROBLEM_ID}.jpg") as image:
        image.load()
        assert image.format == "JPEG"
        assert image.convert("RGB").getextrema() == ((255, 255),) * 3
