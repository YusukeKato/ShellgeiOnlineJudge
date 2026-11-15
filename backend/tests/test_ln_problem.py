"""ln練習問題の名前と実体のモデル、独立期待値、公開dataの整合を確認する。"""

from pathlib import Path

import pytest
from PIL import Image

from soj_shared.problem_repository import build_problem_repository
from soj_shared.problem_schema import load_problem_definition

PROBLEMS = Path(__file__).resolve().parents[2] / "problems"
PROBLEM_ID = "PRACTICE-ln-01"
ALTERNATIVE = (
    "cp -l input.txt shared.txt && printf 'blue\\n' >> shared.txt "
    "&& cat input.txt && stat -c %h shared.txt"
)
CASES = [
    ("public", "red\ngreen\n", "red\ngreen\nblue\n2\n"),
    ("empty", "", "blue\n2\n"),
    ("single", "red\n", "red\nblue\n2\n"),
    ("existing_blue", "blue\n", "blue\nblue\n2\n"),
    ("blank_lines", "red\n\ngreen\n", "red\n\ngreen\nblue\n2\n"),
    ("spaces", " red \n green\n", " red \n green\nblue\n2\n"),
    ("unicode", "赤\n緑\n", "赤\n緑\nblue\n2\n"),
    ("no_final_lf", "red", "redblue\n2\n"),
]


def expected_link_trace(original: str) -> str:
    """file実体と名前を分け、別名を通した追記と名前の数から期待値を返す。

    OSのfile操作やln/statの実行結果には依存しない。末尾LFがない入力にも
    区切りを補わず、元のbyte列に対応する文字列をそのまま保持する。
    """
    contents = {"file": original}
    names = {"input.txt": "file"}
    names["shared.txt"] = names["input.txt"]
    contents[names["shared.txt"]] += "blue\n"
    count = sum(target == names["input.txt"] for target in names.values())
    return contents[names["input.txt"]] + f"{count}\n"


@pytest.mark.parametrize("label,original,expected", CASES)
def test_link_model_matches_manual_cases(
    label: str, original: str, expected: str
) -> None:
    """空・空白・日本語・末尾LFなしを含め、手計算と名前/実体モデルを照合する。"""
    assert expected_link_trace(original) == expected, label


def test_public_ln_data_matches_independent_model() -> None:
    """公開fixtureと17byteの想定出力を独立に求め、コピーや余分な改行への取り違えを防ぐ。"""
    definition = load_problem_definition(PROBLEMS / "v3" / f"{PROBLEM_ID}.yaml")
    fixtures = {
        fixture.path: fixture.content for fixture in definition.execution.fixtures
    }
    assert fixtures == {"input.txt": CASES[0][1]}
    assert definition.judge.type == "text"
    assert definition.judge.expected_output == expected_link_trace(
        fixtures["input.txt"]
    )
    assert definition.judge.expected_output == CASES[0][2]
    assert len(definition.judge.expected_output.encode("utf-8")) == 17


def test_ln_public_dto_policy_and_preview() -> None:
    """日英のhard link説明・公開DTO・正常終了policy・共通の白JPEGを確認する。"""
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(PROBLEM_ID)
    definition = record.definition
    assert definition.title.ja == definition.title.en == "ln 1"
    for statement in (definition.statement.ja, definition.statement.en):
        for token in ("input.txt", "shared.txt", "blue", "LF"):
            assert token in statement
    assert "ハードリンク" in definition.statement.ja
    assert "リンク数" in definition.statement.ja
    assert "Hard links" in definition.statement.en
    assert "link count" in definition.statement.en
    assert definition.execution.stdin == ""
    assert definition.execution.exit_code == "zero"
    assert definition.execution.stderr == "must_be_empty"
    assert len(definition.reference_solution) <= 1000
    detail = record.api_detail()
    assert detail["input"] == CASES[0][1]
    assert detail["expected_output"] == CASES[0][2]
    assert detail["answer"] == definition.reference_solution
    assert detail["image"] == f"/image/{PROBLEM_ID}.jpg"
    with Image.open(PROBLEMS / "image" / f"{PROBLEM_ID}.jpg") as image:
        image.load()
        assert image.format == "JPEG"
        assert image.convert("RGB").getextrema() == ((255, 255),) * 3
