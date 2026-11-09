"""cmp問題の独立byte位置と、追加fixture・DTO・画像の整合を確認する。"""

from pathlib import Path
from PIL import Image
from soj_shared.problem_repository import build_problem_repository
from soj_shared.problem_schema import load_problem_definition

PROBLEMS = Path(__file__).resolve().parents[2] / "problems"
PROBLEM_ID = "PRACTICE-cmp-01"


def test_cmp_positions_count_utf8_bytes_and_line_feeds() -> None:
    """日本語3byteとLFを含む25byte同士を、手計算8/14/23と独立比較で照合する。"""
    definition = load_problem_definition(PROBLEMS / "v3" / f"{PROBLEM_ID}.yaml")
    fixtures = {f.path: f.content for f in definition.execution.fixtures}
    assert fixtures == {
        "input.txt": "alpha=12\n色=red\nbeta=34\n",
        "updated.txt": "alpha=17\n色=Red\nbeta=94\n",
    }
    original = fixtures["input.txt"].encode("utf-8")
    updated = fixtures["updated.txt"].encode("utf-8")
    assert len(original) == len(updated) == 25
    assert len("alpha=12\n".encode("utf-8")) == 9
    assert len("色=red\n".encode("utf-8")) == 8
    assert [(original[p - 1], updated[p - 1]) for p in (8, 14, 23)] == [
        (ord("2"), ord("7")),
        (ord("r"), ord("R")),
        (ord("3"), ord("9")),
    ]
    positions = [
        position
        for position, (before, after) in enumerate(zip(original, updated), 1)
        if before != after
    ]
    assert positions == [8, 14, 23]
    assert definition.judge.type == "text"
    assert definition.judge.expected_output == "".join(f"{p}\n" for p in positions)


def test_cmp_public_fixture_description_policy_and_preview() -> None:
    """入力欄外のupdated.txt全文・UTF-8/LF・日英titleと公開DTO・白JPEGを確認する。"""
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(PROBLEM_ID)
    definition = record.definition
    fixtures = {f.path: f.content for f in definition.execution.fixtures}
    assert definition.title.ja == definition.title.en == "cmp 1"
    for statement in (definition.statement.ja, definition.statement.en):
        assert "input.txt" in statement and "updated.txt" in statement
        assert "UTF-8" in statement and "LF" in statement
        assert fixtures["updated.txt"] in statement
    assert definition.execution.stdin == ""
    assert definition.execution.exit_code == "zero"
    assert definition.execution.stderr == "must_be_empty"
    detail = record.api_detail()
    assert detail["input"] == fixtures["input.txt"]
    assert detail["expected_output"] == record.expected_output
    assert detail["answer"] == definition.reference_solution
    assert detail["image"] == f"/image/{PROBLEM_ID}.jpg"
    assert len(definition.reference_solution) <= 1000
    with Image.open(PROBLEMS / "image" / f"{PROBLEM_ID}.jpg") as image:
        image.load()
        assert image.format == "JPEG"
        assert image.convert("RGB").getextrema() == ((255, 255),) * 3
