"""エラー前後の抽出問題の期待値を、行ごとの近傍確認で独立検証する。"""

from pathlib import Path

from PIL import Image

from soj_shared.problem_schema import load_problem_definition


PROBLEMS = Path(__file__).resolve().parents[2] / "problems"
PROBLEM_ID = "STANDARD-00000061"


def test_error_context_expected_output_and_preview() -> None:
    # 各行の近傍を調べ、端・重なり・非連続区間の期待値と表示用白JPEGを確認する。
    definition = load_problem_definition(PROBLEMS / "v3" / f"{PROBLEM_ID}.yaml")
    assert definition.category == "STANDARD"
    assert definition.judge.type == "text"
    assert definition.execution.stdin == ""
    assert definition.execution.exit_code == "zero"
    assert definition.execution.stderr == "must_be_empty"
    assert len(definition.execution.fixtures) == 1
    assert definition.execution.fixtures[0].path == "input.txt"
    lines = definition.execution.fixtures[0].content.splitlines()
    # grepの文脈統合やawk別解の行番号集合を使わず、出力候補の側から条件を判定する。
    expected = [
        line
        for index, line in enumerate(lines)
        if any(
            neighbor.startswith("ERROR ")
            for neighbor in lines[max(0, index - 1) : index + 2]
        )
    ]
    assert definition.judge.expected_output == "\n".join(expected) + "\n"
    with Image.open(PROBLEMS / "image" / f"{PROBLEM_ID}.jpg") as image:
        image.load()
        assert image.format == "JPEG"
        assert image.convert("RGB").getextrema() == ((255, 255),) * 3
