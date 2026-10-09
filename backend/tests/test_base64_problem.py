"""Base64練習の固定データ・復号単位・空白と実行policyを独立に検査する。"""

import base64
import binascii
from pathlib import Path

import pytest
from PIL import Image

from soj_backend.judge import JudgeVerdict, TextJudgeInput, judge_text
from soj_shared.problem_repository import build_problem_repository
from soj_shared.problem_schema import load_problem_definition


PROBLEMS = Path(__file__).resolve().parents[2] / "problems"
PROBLEM_ID = "PRACTICE-base64-01"
INPUT = "U0hFTExHRUkKC\nueMq+OBqOeKrA\nprZWVwICBzcGF\njZXMhCg==\n"
OUTPUT = "SHELLGEI\n\n猫と犬\nkeep  spaces!\n"


def test_base64_schema_fixture_and_preview() -> None:
    # 改行を含む固定入力・正常終了policy・白JPEGを検査し、詳細APIでも空白が保たれることを確認する。
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(PROBLEM_ID)
    definition = record.definition
    assert definition.schema_version == 3
    assert definition.category == "PRACTICE"
    assert definition.judge.type == "text"
    assert definition.reference_solution == "base64 -d input.txt"
    assert definition.execution.stdin == ""
    assert definition.execution.exit_code == "zero"
    assert definition.execution.stderr == "must_be_empty"
    assert len(definition.execution.fixtures) == 1
    assert definition.execution.fixtures[0].path == "input.txt"
    assert definition.execution.fixtures[0].content == INPUT
    assert definition.judge.expected_output == OUTPUT
    assert record.api_detail()["input"] == INPUT
    assert record.api_detail()["expected_output"] == OUTPUT
    with Image.open(PROBLEMS / "image" / f"{PROBLEM_ID}.jpg") as image:
        image.load()
        assert image.format == "JPEG"
        assert image.convert("RGB").getextrema() == ((255, 255),) * 3


def test_base64_expected_output_decodes_the_whole_message() -> None:
    # shell解答を実行せず、改行を除いたデータの厳密な復号と再符号化でUTF-8・空行・2空白・末尾LFを照合する。
    definition = load_problem_definition(PROBLEMS / "v3" / f"{PROBLEM_ID}.yaml")
    assert definition.judge.type == "text"
    encoded = definition.execution.fixtures[0].content.replace("\n", "").encode("ascii")
    expected = OUTPUT.encode("utf-8")
    assert base64.b64decode(encoded, validate=True) == expected
    assert base64.b64encode(expected) == encoded
    assert definition.judge.expected_output.encode("utf-8") == expected


@pytest.mark.parametrize("line", INPUT.splitlines())
def test_base64_wrapped_lines_are_not_independent_messages(line: str) -> None:
    # 全4行を4文字境界以外で折り返し、行単位の厳密な復号が成立しない入力であることを確認する。
    assert len(line) % 4 != 0
    with pytest.raises(binascii.Error):
        base64.b64decode(line, validate=True)


@pytest.mark.parametrize(
    "execution,verdict",
    [
        (TextJudgeInput(stdout=OUTPUT), JudgeVerdict.ACCEPTED),
        # 現行judgeは末尾LFを無視するが、内部空行・スペースは区別する。
        (TextJudgeInput(stdout=OUTPUT.rstrip("\n")), JudgeVerdict.ACCEPTED),
        (
            TextJudgeInput(stdout=OUTPUT.replace("\n\n", "\n")),
            JudgeVerdict.WRONG_ANSWER,
        ),
        (TextJudgeInput(stdout=OUTPUT.replace("  ", " ")), JudgeVerdict.WRONG_ANSWER),
        (
            TextJudgeInput(stdout=OUTPUT.replace("猫と犬", "犬と猫")),
            JudgeVerdict.WRONG_ANSWER,
        ),
        (TextJudgeInput(stdout=INPUT), JudgeVerdict.WRONG_ANSWER),
        (TextJudgeInput(stdout=OUTPUT, exit_code=1), JudgeVerdict.EXECUTION_FAILURE),
        (
            TextJudgeInput(stdout=OUTPUT, stderr="base64: invalid input\n"),
            JudgeVerdict.EXECUTION_FAILURE,
        ),
    ],
)
def test_base64_judge_preserves_message_and_requires_clean_execution(
    execution: TextJudgeInput, verdict: JudgeVerdict
) -> None:
    # 固定出力と末尾LF省略を受理し、空行・2空白・文字順の破壊、未復号、非0終了・stderrを拒否する。
    definition = load_problem_definition(PROBLEMS / "v3" / f"{PROBLEM_ID}.yaml")
    assert definition.judge.type == "text"
    result = judge_text(definition.judge, definition.execution, execution)
    assert result.verdict is verdict
