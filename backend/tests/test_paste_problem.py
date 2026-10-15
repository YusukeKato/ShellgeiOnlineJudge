"""空行を項目として保持するpaste練習の期待値と、API・表示用dataを検査する。"""

import csv
import io
from pathlib import Path

from PIL import Image

from soj_shared.problem_repository import build_problem_repository
from soj_shared.problem_schema import load_problem_definition


PROBLEMS = Path(__file__).resolve().parents[2] / "problems"
PROBLEM_ID = "PRACTICE-paste-01"
INPUT = "pear\n\n\napple\npear\n\nplum\n"
EXPECTED = "pear,,,apple,pear,,plum\n"


def test_paste_expected_output_from_independent_csv_writer() -> None:
    # pasteを呼ばずCSV writerで期待値を求め、手確認した7項目と空欄の位置を照合する。
    definition = load_problem_definition(PROBLEMS / "v3" / f"{PROBLEM_ID}.yaml")
    fixture = definition.execution.fixtures[0].content
    fields = fixture.splitlines()
    assert fields == ["pear", "", "", "apple", "pear", "", "plum"]
    stream = io.StringIO(newline="")
    csv.writer(stream, lineterminator="\n").writerow(fields)
    assert definition.judge.type == "text"
    assert definition.judge.expected_output == stream.getvalue() == EXPECTED
    assert len(fixture.encode()) == len(EXPECTED.encode()) == 24


def test_paste_api_policy_and_preview() -> None:
    # 詳細APIが連続する空行と末尾LFを保持し、正常終了policyと白JPEGが画面に適合する。
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
