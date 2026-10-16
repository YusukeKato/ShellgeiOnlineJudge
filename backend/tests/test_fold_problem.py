"""固定幅分割と先頭の0を保持するfold練習の期待値・API・画像を検査する。"""

import re
from pathlib import Path

from PIL import Image

from soj_shared.problem_repository import build_problem_repository
from soj_shared.problem_schema import load_problem_definition


PROBLEMS = Path(__file__).resolve().parents[2] / "problems"
PROBLEM_ID = "PRACTICE-fold-01"
INPUT = "AB12CD34EF56GH78Z9\n00012345XY9\nQ7R8S9T0\n"
EXPECTED = "AB12CD34\nEF56GH78\nZ9\n00012345\nXY9\nQ7R8S9T0\n"


def test_fold_expected_output_from_independent_chunks() -> None:
    # foldを呼ばず正規表現で区切り、手確認した6部分と元の行ごとの境界を照合する。
    definition = load_problem_definition(PROBLEMS / "v3" / f"{PROBLEM_ID}.yaml")
    fixture = definition.execution.fixtures[0].content
    lines = fixture.splitlines()
    assert [len(line) for line in lines] == [18, 11, 8]
    chunks = [re.findall(r".{1,8}", line) for line in lines]
    assert chunks == [
        ["AB12CD34", "EF56GH78", "Z9"],
        ["00012345", "XY9"],
        ["Q7R8S9T0"],
    ]
    assert ["".join(parts) for parts in chunks] == lines
    assert definition.judge.type == "text"
    assert (
        definition.judge.expected_output
        == "\n".join(part for parts in chunks for part in parts) + "\n"
        == EXPECTED
    )
    assert len(fixture.encode()) == 40
    assert len(EXPECTED.encode()) == 43


def test_fold_api_policy_and_preview() -> None:
    # 詳細APIが先頭の0・元の行境界と末尾LFを保持し、正常終了policyと白JPEGが画面に適合する。
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
