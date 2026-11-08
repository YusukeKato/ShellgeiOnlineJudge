"""各メモの最初の見出しを独立に求め、公開fixture・DTO・画像を検査する。"""

from pathlib import Path
from PIL import Image
from soj_shared.problem_repository import build_problem_repository
from soj_shared.problem_schema import load_problem_definition

PROBLEMS = Path(__file__).resolve().parents[2] / "problems"
PROBLEM_ID = "STANDARD-00000072"


def test_first_heading_uses_first_matching_line_per_listed_file() -> None:
    """行頭記号・fileごとの最小行番号・入力順と重複を手計算と独立照合する。"""
    definition = load_problem_definition(PROBLEMS / "v3" / f"{PROBLEM_ID}.yaml")
    fixtures = {f.path: f.content for f in definition.execution.fixtures}
    first_lines = {
        "notes/beta.txt": (3, "# Beta overview"),
        "notes/alpha memo.txt": (1, "# Alpha memo"),
        "notes/gamma.txt": (3, "# Gamma start"),
    }
    paths = fixtures["input.txt"].splitlines()
    assert paths == [
        "notes/beta.txt",
        "notes/alpha memo.txt",
        "notes/gamma.txt",
        "notes/beta.txt",
    ]
    independent = []
    for path in paths:
        lines = fixtures[path].splitlines()
        positions = [i for i, line in enumerate(lines) if line[:2] == "# "]
        line_number, heading = first_lines[path]
        assert min(positions) + 1 == line_number
        assert lines[min(positions)] == heading
        assert len(positions) == 2
        independent.append(f"{path}:{heading}\n")
    assert definition.judge.type == "text"
    assert definition.judge.expected_output == "".join(independent)
    assert "notes/unlisted.txt" not in paths and "notes/unlisted.txt" in fixtures
    assert fixtures["notes/beta.txt"].startswith("draft for # overview\n  # indented\n")
    assert fixtures["notes/gamma.txt"].splitlines()[1] == "## Internal section"


def test_first_heading_public_fixture_explanation_and_preview() -> None:
    """入力欄外の全file本文を日英で示し、公開DTO・終了policy・白JPEGを維持する。"""
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(PROBLEM_ID)
    definition = record.definition
    assert definition.title.ja == "各メモの最初の見出し"
    assert definition.title.en == "First Heading from Each Note"
    for statement in (definition.statement.ja, definition.statement.en):
        assert "input.txt" in statement
        for fixture in definition.execution.fixtures[1:]:
            assert f"[{fixture.path}]\n{fixture.content}" in statement
    assert definition.execution.stdin == ""
    assert definition.execution.exit_code == "zero"
    assert definition.execution.stderr == "must_be_empty"
    detail = record.api_detail()
    assert detail["input"] == definition.execution.fixtures[0].content
    assert detail["expected_output"] == record.expected_output
    assert detail["answer"] == definition.reference_solution
    assert detail["image"] == f"/image/{PROBLEM_ID}.jpg"
    assert len(definition.reference_solution) <= 1000
    with Image.open(PROBLEMS / "image" / f"{PROBLEM_ID}.jpg") as image:
        image.load()
        assert image.format == "JPEG"
        assert image.convert("RGB").getextrema() == ((255, 255),) * 3
