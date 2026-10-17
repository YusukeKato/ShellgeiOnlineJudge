"""作業の抽出位置と連番・重複・空白の保持を独立期待値と詳細APIで検査する。"""

from pathlib import Path

from PIL import Image

from soj_shared.problem_repository import build_problem_repository
from soj_shared.problem_schema import load_problem_definition


PROBLEMS = Path(__file__).resolve().parents[2] / "problems"
PROBLEM_ID = "STANDARD-00000074"
INPUT = (
    "DONE archive logs\nTODO update README\nNOTE TODO items are below\n"
    "TODO run  unit tests\nTODO2 check backup\nTODO update README\n"
    "DONE send report\nTODO check backups\n"
)
EXPECTED = "01 update README\n02 run  unit tests\n03 update README\n04 check backups\n"


def test_pending_tasks_expected_output_from_selected_records() -> None:
    # sed・nlを使わず、手確認した元の行番号と作業名から連番付き期待値を独立に照合する。
    definition = load_problem_definition(PROBLEMS / "v3" / f"{PROBLEM_ID}.yaml")
    selected = [
        (number, line.removeprefix("TODO "))
        for number, line in enumerate(
            definition.execution.fixtures[0].content.splitlines(), 1
        )
        if line.startswith("TODO ")
    ]
    assert selected == [
        (2, "update README"),
        (4, "run  unit tests"),
        (6, "update README"),
        (8, "check backups"),
    ]
    expected = "".join(
        f"{number:02d} {task}\n" for number, (_, task) in enumerate(selected, 1)
    )
    assert definition.judge.type == "text"
    assert definition.judge.expected_output == expected == EXPECTED
    assert len(EXPECTED.encode()) == 70


def test_pending_tasks_api_policy_and_preview() -> None:
    # 詳細APIが作業名の連続空白・重複・末尾LFを保ち、正常終了policyと白JPEGを使用する。
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(PROBLEM_ID)
    definition = record.definition
    assert definition.category == "STANDARD"
    assert definition.execution.stdin == ""
    assert definition.execution.exit_code == "zero"
    assert definition.execution.stderr == "must_be_empty"
    assert len(definition.execution.fixtures) == 1
    assert definition.execution.fixtures[0].path == "input.txt"
    assert record.api_detail()["input"] == INPUT
    assert record.api_detail()["expected_output"] == EXPECTED
    assert len(definition.reference_solution) <= 1000
    with Image.open(PROBLEMS / "image" / f"{PROBLEM_ID}.jpg") as image:
        image.load()
        assert image.format == "JPEG"
        assert image.convert("RGB").getextrema() == ((255, 255),) * 3
