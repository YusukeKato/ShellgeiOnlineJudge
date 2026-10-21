"""新規3問題の期待値を参照解答とは独立に確認し、公開DTO・policy・白JPEGを検査する。"""

from pathlib import Path, PurePosixPath

import pytest
from PIL import Image

from soj_shared.problem_repository import build_problem_repository
from soj_shared.problem_schema import load_problem_definition


PROBLEMS = Path(__file__).resolve().parents[2] / "problems"
IDS = ("PRACTICE-basename-01", "PRACTICE-cut-01", "STANDARD-00000077")


@pytest.mark.parametrize("problem_id", IDS)
def test_new_command_problem_independent_expectation(problem_id: str) -> None:
    # ファイル名の手確認表・区切りfield・3行の行番号表から期待値を独立に計算する。
    definition = load_problem_definition(PROBLEMS / "v3" / f"{problem_id}.yaml")
    fixture = definition.execution.fixtures[0].content
    lines = fixture.splitlines()
    if problem_id == "PRACTICE-basename-01":
        expected_names = [
            "api",
            "batch 02",
            "notes.log.bak",
            "api.v2",
            "service.log",
            "standalone",
            "error.LOG",
            "api",
        ]
        assert len(lines) == len(expected_names)
        assert [
            PurePosixPath(line).name.removesuffix(".log") for line in lines
        ] == expected_names
        expected = "\n".join(expected_names) + "\n"
    elif problem_id == "PRACTICE-cut-01":
        assert lines == [
            "JP-0042-A",
            "US-0100-B",
            "EU-0007-A",
            "JP-0042-C",
            "NZ-9001-B",
        ]
        # cutの文字位置指定とは異なり、意味上の区切りから2fieldを取り出す。
        expected = "".join(
            region + registration + "\n"
            for region, registration, _ in (line.split("-") for line in lines)
        )
        assert expected == "JP0042\nUS0100\nEU0007\nJP0042\nNZ9001\n"
    else:
        assert lines == [
            "INFO boot",
            "WARN cache miss",
            "",
            "INFO ready",
            "WARN cache miss",
            "INFO accept  job",
            "INFO done",
            "INFO stop",
        ]
        groups = (lines[:3], lines[3:6], lines[6:])
        expected = "".join(
            f"[part_{number:02d}]\n" + "\n".join(group) + "\n"
            for number, group in enumerate(groups)
        )
        assert expected.count("[part_") == 3
    assert definition.judge.type == "text"
    assert definition.judge.expected_output == expected


@pytest.mark.parametrize("problem_id", IDS)
def test_new_command_problem_api_policy_and_preview(problem_id: str) -> None:
    # 表示用入力・期待値と正常終了policyを公開し、日英titleと白画像を現行契約に合わせる。
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(problem_id)
    definition = record.definition
    assert definition.execution.stdin == ""
    assert definition.execution.exit_code == "zero"
    assert definition.execution.stderr == "must_be_empty"
    assert len(definition.execution.fixtures) == 1
    fixture = definition.execution.fixtures[0]
    assert fixture.path == "input.txt"
    assert record.api_detail()["input"] == fixture.content
    assert record.api_detail()["expected_output"] == record.expected_output
    assert definition.statement.ja and definition.statement.en
    if definition.category == "PRACTICE":
        command = problem_id.split("-")[1]
        assert definition.title.ja == definition.title.en == f"{command} 1"
    assert len(definition.reference_solution) <= 1000
    with Image.open(PROBLEMS / "image" / f"{problem_id}.jpg") as image:
        image.load()
        assert image.format == "JPEG"
        assert image.convert("RGB").getextrema() == ((255, 255),) * 3
