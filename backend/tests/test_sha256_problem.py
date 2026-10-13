"""ファイル全体のSHA-256を独立に計算し、改行・空白・表示・実行policyを検査する。"""

import hashlib
from pathlib import Path

import pytest
from PIL import Image

from soj_backend.judge import JudgeVerdict, TextJudgeInput, judge_text
from soj_shared.problem_repository import build_problem_repository
from soj_shared.problem_schema import load_problem_definition


PROBLEMS = Path(__file__).resolve().parents[2] / "problems"
PROBLEM_ID = "PRACTICE-sha256sum-01"
DIGEST = "f5ebb56e393995ff3fb5095d0c3bd1977567838eb234531341e8a10080a08b73"
INPUT = "shellgei\nonline judge\n"


def test_sha256_fixture_api_policy_and_preview() -> None:
    # 詳細APIが末尾LFを含む22 bytesを保持し、正常終了policyと白JPEGが画面に適合する。
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
    assert len(fixture.content.encode("utf-8")) == 22
    assert record.api_detail()["input"] == INPUT
    assert record.api_detail()["expected_output"] == DIGEST + "\n"
    assert len(definition.reference_solution) <= 1000
    with Image.open(PROBLEMS / "image" / f"{PROBLEM_ID}.jpg") as image:
        image.load()
        assert image.format == "JPEG"
        assert image.convert("RGB").getextrema() == ((255, 255),) * 3


def test_sha256_expected_output_from_independent_library() -> None:
    # sha256sumを呼ばずPythonのhashlibで期待値を求め、設計時の.NETとの照合値も固定する。
    definition = load_problem_definition(PROBLEMS / "v3" / f"{PROBLEM_ID}.yaml")
    assert definition.judge.type == "text"
    digest = hashlib.sha256(
        definition.execution.fixtures[0].content.encode()
    ).hexdigest()
    assert digest == DIGEST
    assert definition.judge.expected_output == digest + "\n"


@pytest.mark.parametrize(
    "changed_input",
    [
        INPUT.rstrip("\n"),
        INPUT.replace("\n", "\r\n"),
        INPUT.replace(" ", ""),
        INPUT.upper(),
    ],
)
def test_sha256_input_changes_produce_different_expected_values(
    changed_input: str,
) -> None:
    # 末尾LFの欠落、CRLF化、内部スペースの削除、大小文字変更を固定入力が区別できる。
    assert hashlib.sha256(changed_input.encode()).hexdigest() != DIGEST


@pytest.mark.parametrize(
    "execution,verdict",
    [
        (TextJudgeInput(stdout=DIGEST + "\n"), JudgeVerdict.ACCEPTED),
        (TextJudgeInput(stdout=DIGEST), JudgeVerdict.ACCEPTED),
        (TextJudgeInput(stdout=DIGEST + "  input.txt\n"), JudgeVerdict.WRONG_ANSWER),
        (TextJudgeInput(stdout=DIGEST.upper()), JudgeVerdict.WRONG_ANSWER),
        (TextJudgeInput(stdout=DIGEST, exit_code=1), JudgeVerdict.EXECUTION_FAILURE),
        (
            TextJudgeInput(stdout=DIGEST, stderr="warning\n"),
            JudgeVerdict.EXECUTION_FAILURE,
        ),
    ],
)
def test_sha256_judge_output_format_and_execution(
    execution: TextJudgeInput, verdict: JudgeVerdict
) -> None:
    # 出力の末尾LFは現行judgeに従い許容し、名前・大文字・非0終了・stderrを拒否する。
    definition = load_problem_definition(PROBLEMS / "v3" / f"{PROBLEM_ID}.yaml")
    assert definition.judge.type == "text"
    assert (
        judge_text(definition.judge, definition.execution, execution).verdict is verdict
    )
