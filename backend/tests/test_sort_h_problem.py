"""単位付きサイズの独立期待値、公開契約と白JPEGを検査する。"""

from pathlib import Path

from PIL import Image

from soj_shared.problem_repository import build_problem_repository
from soj_shared.problem_schema import load_problem_definition

PROBLEMS = Path(__file__).resolve().parents[2] / "problems"
PROBLEM_ID = "PRACTICE-sort-04"


def test_sort_h_problem_has_independently_verified_expected_output() -> None:
    """手換算したbyte数と各値より小さい要素数で、名前や桁数に影響されない順序を照合する。"""
    definition = load_problem_definition(PROBLEMS / "v3" / f"{PROBLEM_ID}.yaml")
    lines = definition.execution.fixtures[0].content.splitlines()
    units = {"K": 1024, "M": 1024**2, "G": 1024**3}
    values = []
    for line in lines:
        size = line.split()[1]
        values.append(
            int(size[:-1]) * units[size[-1]] if size[-1] in units else int(size)
        )
    assert values == [1073741824, 972800, 12582912, 800, 2097152, 102400, 1048576, 900]
    ranks = [sum(other < value for other in values) for value in values]
    assert ranks == [7, 3, 6, 0, 5, 2, 4, 1]
    by_rank = dict(zip(ranks, lines, strict=True))
    expected = "".join(by_rank[index] + "\n" for index in range(len(lines)))
    assert expected == (
        "tiny.dat 800\ncache.bin 900\nlogs.tar 100K\nnotes.txt 950K\n"
        "bundle.bin 1M\narchive.zip 2M\nimage.raw 12M\nbackup.tar 1G\n"
    )
    assert definition.judge.type == "text"
    assert definition.judge.expected_output == expected


def test_sort_h_problem_public_contract_and_preview() -> None:
    """日英の単位説明、入力・回答例、正常終了policyと表示用白JPEGを保持する。"""
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(PROBLEM_ID)
    definition = record.definition
    assert definition.title.ja == definition.title.en == "sort 4"
    for statement in (definition.statement.ja, definition.statement.en):
        assert "input.txt" in statement and "1024" in statement
        assert all(unit in statement for unit in ("K", "M", "G"))
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
    assert detail["image"] == f"/image/{PROBLEM_ID}.jpg"
    assert len(definition.reference_solution) <= 1000
    with Image.open(PROBLEMS / "image" / f"{PROBLEM_ID}.jpg") as image:
        image.load()
        assert image.format == "JPEG"
        assert image.convert("RGB").getextrema() == ((255, 255),) * 3
