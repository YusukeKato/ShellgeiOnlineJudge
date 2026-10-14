"""一覧への所属を独立に調べ、両方向の変更・重複・出力順と表示用dataを検査する。"""

from pathlib import Path

import pytest
from PIL import Image

from soj_backend.judge import JudgeVerdict, TextJudgeInput, judge_text
from soj_shared.problem_repository import build_problem_repository
from soj_shared.problem_schema import load_problem_definition


PROBLEMS = Path(__file__).resolve().parents[2] / "problems"
PROBLEM_ID = "STANDARD-00000071"
EXPECTED = "REMOVE api\nADD api2\nREMOVE cron\nADD mail\nADD proxy\nREMOVE queue\n"


def test_service_changes_expected_from_independent_membership_checks() -> None:
    # commや参照解答を使わず各名前の所属を全行から調べ、手確認した変更点とも照合する。
    definition = load_problem_definition(PROBLEMS / "v3" / f"{PROBLEM_ID}.yaml")
    rows = [
        line.split() for line in definition.execution.fixtures[0].content.splitlines()
    ]
    names = sorted({name for _, name in rows})
    changes = []
    for name in names:
        before = any(state == "before" and value == name for state, value in rows)
        after = any(state == "after" and value == name for state, value in rows)
        if before != after:
            changes.append(("REMOVE" if before else "ADD", name))
    assert changes == [
        ("REMOVE", "api"),
        ("ADD", "api2"),
        ("REMOVE", "cron"),
        ("ADD", "mail"),
        ("ADD", "proxy"),
        ("REMOVE", "queue"),
    ]
    assert definition.judge.type == "text"
    assert (
        definition.judge.expected_output
        == "".join(f"{action} {name}\n" for action, name in changes)
        == EXPECTED
    )
    # 共通の名前に左右非対称の重複を持たせ、多重集合の差や部分一致と区別する。
    assert rows.count(["before", "cache"]) == 2
    assert rows.count(["after", "cache"]) == 1
    assert rows.count(["before", "docs"]) == 1
    assert rows.count(["after", "docs"]) == 2
    assert rows.count(["before", "api"]) == rows.count(["after", "api2"]) == 2


def test_service_changes_api_policy_and_preview() -> None:
    # 公開入力の164 bytesと出力の64 bytes、正常終了policy、表示用JPEGを保持する。
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
    fixture = definition.execution.fixtures[0]
    assert fixture.path == "input.txt"
    assert len(fixture.content.encode()) == 164
    assert record.api_detail()["input"] == fixture.content
    assert record.api_detail()["expected_output"] == EXPECTED
    assert len(EXPECTED.encode()) == 64
    assert len(definition.reference_solution) <= 1000
    with Image.open(PROBLEMS / "image" / f"{PROBLEM_ID}.jpg") as image:
        image.load()
        assert image.format == "JPEG"
        assert image.convert("RGB").getextrema() == ((255, 255),) * 3


@pytest.mark.parametrize(
    "output",
    [
        "ADD api2\nADD mail\nADD proxy\n",
        "REMOVE api\nREMOVE cron\nREMOVE queue\n",
        "ADD api2\nADD mail\nADD proxy\nREMOVE api\nREMOVE cron\nREMOVE queue\n",
        EXPECTED.replace("REMOVE api\n", ""),
        EXPECTED.replace("ADD api2\n", "ADD api2\nADD api2\n"),
        EXPECTED + "ADD docs\nREMOVE cache\n",
        EXPECTED.replace("REMOVE api", "ADD api"),
    ],
)
def test_service_changes_rejects_membership_and_order_errors(output: str) -> None:
    # 片方向だけ、ラベル順、部分一致、重複、共通名の混入、向きの逆転を拒否する。
    definition = load_problem_definition(PROBLEMS / "v3" / f"{PROBLEM_ID}.yaml")
    assert definition.judge.type == "text"
    assert (
        judge_text(
            definition.judge, definition.execution, TextJudgeInput(stdout=output)
        ).verdict
        is JudgeVerdict.WRONG_ANSWER
    )
