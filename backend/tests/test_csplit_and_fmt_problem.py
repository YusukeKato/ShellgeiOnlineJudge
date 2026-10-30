"""見出し分割と段落整形の独立期待値、公開契約と白JPEGを検査する。"""

from pathlib import Path

from PIL import Image
import pytest

from soj_shared.problem_repository import build_problem_repository
from soj_shared.problem_schema import load_problem_definition

PROBLEMS = Path(__file__).resolve().parents[2] / "problems"
IDS = ("PRACTICE-csplit-01", "PRACTICE-fmt-01")


def test_csplit_expected_output_matches_heading_ranges() -> None:
    """見出しの位置1・4・9と区間長3・5・4を、行位置から独立に照合する。"""
    definition = load_problem_definition(PROBLEMS / "v3/PRACTICE-csplit-01.yaml")
    lines = definition.execution.fixtures[0].content.splitlines()
    starts = [i for i, line in enumerate(lines) if line.startswith("## ")]
    assert starts == [0, 3, 8]
    sizes = [stop - start for start, stop in zip(starts, starts[1:] + [len(lines)])]
    assert sizes == [3, 5, 4]
    assert sum(sizes) == len(lines) == 12
    assert lines[2] == "note ## build is text" and lines[5] == ""
    assert definition.judge.type == "text"
    assert definition.judge.expected_output == "".join(
        f"section{i:02d} {size}\n" for i, size in enumerate(sizes)
    )
    assert definition.title.ja == definition.title.en == "csplit 1"


def test_fmt_expected_output_matches_paragraph_words() -> None:
    """段落の単語列と順序を独立に組み直し、段落間の空行と空白統一を確認する。"""
    definition = load_problem_definition(PROBLEMS / "v3/PRACTICE-fmt-01.yaml")
    fixture = definition.execution.fixtures[0].content
    paragraphs = [" ".join(part.split()) for part in fixture.rstrip("\n").split("\n\n")]
    assert paragraphs == [
        "Small tools can turn a long list of steps into a clear report without changing the order of the words",
        "Keep each paragraph on one line",
        "Small tools can work together",
    ]
    assert len(paragraphs[0]) > 75 and "   " in fixture
    assert definition.judge.type == "text"
    assert definition.judge.expected_output == "\n\n".join(paragraphs) + "\n"
    assert definition.title.ja == definition.title.en == "fmt 1"


@pytest.mark.parametrize("problem_id", IDS)
def test_new_problem_public_contract_and_preview(problem_id: str) -> None:
    """日英問題文とinput.txtを公開し、正常終了・stderr空のpolicyと白JPEGを保持する。"""
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(problem_id)
    definition = record.definition
    assert definition.statement.ja and definition.statement.en
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
