"""行順を保つ文字反転の独立期待値・API・画像を検査する。"""

from pathlib import Path

from PIL import Image

from soj_shared.problem_repository import build_problem_repository
from soj_shared.problem_schema import load_problem_definition


PROBLEMS = Path(__file__).resolve().parents[2] / "problems"
PROBLEM_ID = "PRACTICE-rev-01"
INPUT = "A1-bC\nred  blue\n\n1221\nZ\n"
EXPECTED = "Cb-1A\neulb  der\n\n1221\nZ\n"


def test_rev_expected_output_from_independent_character_positions() -> None:
    # revを呼ばず元の行の対称位置を照合し、手確認した逆順と空行・内部スペースを検査する。
    definition = load_problem_definition(PROBLEMS / "v3" / f"{PROBLEM_ID}.yaml")
    fixture = definition.execution.fixtures[0].content
    assert fixture == INPUT
    lines = fixture.splitlines()
    reversed_lines = EXPECTED.splitlines()
    assert len(lines) == len(reversed_lines) == 5
    for original, reversed_line in zip(lines, reversed_lines, strict=True):
        assert len(original) == len(reversed_line)
        assert all(
            char == reversed_line[len(original) - index - 1]
            for index, char in enumerate(original)
        )
    assert lines[2] == reversed_lines[2] == ""
    assert reversed_lines[1] == "eulb  der"
    assert definition.judge.type == "text"
    assert definition.judge.expected_output == EXPECTED


def test_rev_api_policy_and_preview() -> None:
    # 詳細APIが内部スペース・空行を保持し、正常終了policyと白JPEGが画面に適合する。
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(PROBLEM_ID)
    definition = record.definition
    assert definition.category == "PRACTICE"
    assert definition.execution.stdin == ""
    assert definition.execution.exit_code == "zero"
    assert definition.execution.stderr == "must_be_empty"
    assert len(definition.execution.fixtures) == 1
    fixture = definition.execution.fixtures[0]
    assert fixture.path == "input.txt"
    assert fixture.content == INPUT
    assert record.api_detail()["input"] == INPUT
    assert record.api_detail()["expected_output"] == EXPECTED
    assert len(definition.reference_solution) <= 1000
    with Image.open(PROBLEMS / "image" / f"{PROBLEM_ID}.jpg") as image:
        image.load()
        assert image.format == "JPEG"
        assert image.convert("RGB").getextrema() == ((255, 255),) * 3
