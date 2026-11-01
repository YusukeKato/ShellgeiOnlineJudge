"""親pathとfile内容の独立期待値、公開契約、白JPEGを検査する。"""

from pathlib import Path
import posixpath

from PIL import Image
import pytest

from soj_shared.problem_repository import build_problem_repository
from soj_shared.problem_schema import load_problem_definition

PROBLEMS = Path(__file__).resolve().parents[2] / "problems"
IDS = ("STANDARD-00000071", "PRACTICE-dirname-01")


def test_duplicate_files_expected_output_uses_complete_contents() -> None:
    """全内容で分類し、一覧外・大文字小文字・拡張子・表示順を区別する。"""
    definition = load_problem_definition(PROBLEMS / "v3/STANDARD-00000071.yaml")
    fixtures = {item.path: item.content for item in definition.execution.fixtures}
    paths = fixtures.pop("input.txt").splitlines()
    groups: dict[str, list[str]] = {}
    for path in paths:
        groups.setdefault(fixtures[path], []).append(path)
    names = sorted(sorted(group) for group in groups.values() if len(group) >= 2)
    assert names == [
        ["data/blue.txt", "data/copy blue.log", "data/third blue.txt"],
        ["data/green.txt", "data/other green.txt"],
    ]
    assert fixtures["data/red.txt"] != fixtures["data/red upper.txt"]
    assert "data/unlisted.txt" not in paths
    assert fixtures["data/unlisted.txt"] == fixtures["data/blue.txt"]
    assert definition.judge.type == "text"
    assert definition.judge.expected_output == "".join(
        " | ".join(group) + "\n" for group in names
    )
    for path, content in fixtures.items():
        for statement in (definition.statement.ja, definition.statement.en):
            assert f"{path}: {content.rstrip(chr(10))}" in statement


def test_dirname_expected_output_uses_parent_components() -> None:
    """空白・/なし・root直下・./と、入力順・重複を保持した親pathを独立計算する。"""
    definition = load_problem_definition(PROBLEMS / "v3/PRACTICE-dirname-01.yaml")
    paths = definition.execution.fixtures[0].content.splitlines()
    parents = [posixpath.dirname(path) or "." for path in paths]
    assert parents == [
        "logs",
        "logs/archive",
        "draft notes",
        ".",
        "/etc/soj",
        "/",
        "logs",
        "./docs",
    ]
    assert definition.judge.type == "text"
    assert definition.judge.expected_output == "".join(
        parent + "\n" for parent in parents
    )
    assert definition.title.ja == definition.title.en == "dirname 1"


@pytest.mark.parametrize("problem_id", IDS)
def test_new_problem_public_contract_and_preview(problem_id: str) -> None:
    """複数fixtureでも入力欄はinput.txtとし、公開解答・policy・白JPEGを確認する。"""
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(problem_id)
    definition = record.definition
    fixtures = {item.path: item.content for item in definition.execution.fixtures}
    assert definition.statement.ja and definition.statement.en
    assert definition.execution.stdin == ""
    assert definition.execution.exit_code == "zero"
    assert definition.execution.stderr == "must_be_empty"
    detail = record.api_detail()
    assert detail["input"] == fixtures["input.txt"]
    assert detail["expected_output"] == record.expected_output
    assert detail["answer"] == definition.reference_solution
    assert detail["image"] == f"/image/{problem_id}.jpg"
    assert len(definition.reference_solution) <= 1000
    with Image.open(PROBLEMS / "image" / f"{problem_id}.jpg") as image:
        image.load()
        assert image.format == "JPEG"
        assert image.convert("RGB").getextrema() == ((255, 255),) * 3
