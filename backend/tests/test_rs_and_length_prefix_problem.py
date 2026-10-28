"""転置と長さ付き本文の独立期待値、公開契約と白JPEGを検査する。"""

from pathlib import Path

from PIL import Image
import pytest

from soj_shared.problem_repository import build_problem_repository
from soj_shared.problem_schema import load_problem_definition

PROBLEMS = Path(__file__).resolve().parents[2] / "problems"
IDS = ("PRACTICE-rs-01", "STANDARD-00000070")


def test_rs_expected_output_matches_original_columns() -> None:
    """手確認した3列と独立した列添字の計算で、見出し・時刻・値の対応を確認する。"""
    definition = load_problem_definition(PROBLEMS / "v3/PRACTICE-rs-01.yaml")
    rows = [
        line.split() for line in definition.execution.fixtures[0].content.splitlines()
    ]
    assert rows == [
        ["time", "north", "south"],
        ["06:00", "12", "8"],
        ["12:00", "18", "15"],
        ["18:00", "10", "9"],
    ]
    expected = "time 06:00 12:00 18:00\nnorth 12 18 10\nsouth 8 15 9\n"
    calculated = "".join(
        " ".join(row[column] for row in rows) + "\n" for column in range(len(rows[0]))
    )
    assert calculated == expected
    assert definition.judge.type == "text"
    assert definition.judge.expected_output == expected
    assert definition.title.ja == definition.title.en == "rs 1"


def test_length_prefix_expected_output_matches_utf8_byte_slice() -> None:
    """日本語9bytes・LF1byte・ASCII5bytesの手計算とbyte配列の範囲を照合する。"""
    definition = load_problem_definition(PROBLEMS / "v3/STANDARD-00000070.yaml")
    fixture = definition.execution.fixtures[0].content
    assert fixture == "15\n青い空\nhelloworld\n"
    header, body = fixture.encode().split(b"\n", 1)
    assert header == b"15"
    assert [len(value.encode()) for value in ("青", "い", "空", "\n", "hello")] == [
        3,
        3,
        3,
        1,
        5,
    ]
    expected = "青い空\nhello"
    assert len(expected.encode()) == 15
    assert body[: int(header)].decode() == expected
    assert body[int(header) :] == b"world\n"
    assert definition.judge.type == "text"
    assert definition.judge.expected_output == expected
    assert not expected.endswith("\n")


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
