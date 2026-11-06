"""stat問題の独立byte数、複数fixtureの公開説明と表示画像を検査する。"""

from pathlib import Path
from PIL import Image
from soj_shared.problem_repository import build_problem_repository
from soj_shared.problem_schema import load_problem_definition

PROBLEMS = Path(__file__).resolve().parents[2] / "problems"
PROBLEM_ID = "PRACTICE-stat-01"


def test_stat_sizes_include_utf8_bytes_and_line_feeds_in_input_order() -> None:
    """手計算の3/10/6/11byteとUTF-8長を照合し、重複pathとLFなしfileを保持する。"""
    definition = load_problem_definition(PROBLEMS / "v3" / f"{PROBLEM_ID}.yaml")
    fixtures = {
        fixture.path: fixture.content for fixture in definition.execution.fixtures
    }
    manual = {
        "data/short.txt": 3,
        "data/japanese.txt": 3 * 3 + 1,
        "data/two lines.txt": 2 + 1 + 2 + 1,
        "data/message.txt": 10 + 1,
    }
    for path, size in manual.items():
        assert len(fixtures[path].encode("utf-8")) == size
    assert fixtures["data/short.txt"] == "cat"
    assert fixtures["data/japanese.txt"] == "猫と犬\n"
    assert fixtures["data/two lines.txt"] == "ab\ncd\n"
    assert fixtures["data/message.txt"] == "Hello SOJ!\n"
    paths = fixtures["input.txt"].splitlines()
    assert paths == [
        "data/short.txt",
        "data/japanese.txt",
        "data/two lines.txt",
        "data/message.txt",
        "data/short.txt",
    ]
    assert definition.judge.type == "text"
    assert definition.judge.expected_output == "".join(
        f"{path} {manual[path]}\n" for path in paths
    )
    assert "data/unlisted.txt" in fixtures and "data/unlisted.txt" not in paths


def test_stat_public_fixture_explanation_policy_and_white_preview() -> None:
    """入力欄に出ない全fileを日英で説明し、公開DTOと正常終了policy・JPEGを照合する。"""
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(PROBLEM_ID)
    definition = record.definition
    assert definition.title.ja == definition.title.en == "stat 1"
    for statement in (definition.statement.ja, definition.statement.en):
        assert all(
            fixture.path in statement for fixture in definition.execution.fixtures
        )
        assert "UTF-8" in statement and "LF" in statement and r"\n" in statement
        assert all(
            text in statement
            for text in (
                r"Hello SOJ!\n",
                "cat",
                r"猫と犬\n",
                r"ab\ncd\n",
                r"not listed\n",
            )
        )
    assert definition.execution.stdin == ""
    assert (
        definition.execution.exit_code == "zero"
        and definition.execution.stderr == "must_be_empty"
    )
    assert len(definition.execution.fixtures) == 6
    detail = record.api_detail()
    assert detail["input"] == definition.execution.fixtures[0].content
    assert detail["expected_output"] == record.expected_output
    assert detail["answer"] == definition.reference_solution
    assert detail["image"] == f"/image/{PROBLEM_ID}.jpg"
    assert len(definition.reference_solution) <= 1000
    with Image.open(PROBLEMS / "image" / f"{PROBLEM_ID}.jpg") as image:
        image.load()
        assert (
            image.format == "JPEG"
            and image.convert("RGB").getextrema() == ((255, 255),) * 3
        )
