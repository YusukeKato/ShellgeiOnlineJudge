"""正規表現問題の期待値を、正規表現を使わない条件判定で確認する。"""

import json
from pathlib import Path

import pytest
from PIL import Image

from soj_shared.problem_repository import build_problem_repository
from soj_shared.problem_schema import load_problem_definition


PROBLEMS = Path(__file__).resolve().parents[2] / "problems"


@pytest.mark.parametrize("number", [1, 2, 3, 4])
def test_regex_expectations(number: int) -> None:
    # 公開入力を文字位置・パターン消費・反転で判定し、出力順と表示用画像も確認する。
    problem_id = f"REGEX-{number:08}"
    definition = load_problem_definition(PROBLEMS / "v3" / f"{problem_id}.yaml")
    assert definition.category == "REGEX"
    assert definition.judge.type == "text"
    assert definition.execution.exit_code == "zero"
    assert definition.execution.stderr == "must_be_empty"
    if number == 1:
        # 公開する解答例が実行用の参照解答と一致することを日英とも保証する。
        for statement in (definition.statement.ja, definition.statement.en):
            assert definition.reference_solution.strip() in statement
    result = []
    for line in definition.execution.fixtures[0].content.splitlines():
        if number == 1:
            valid = line.startswith("A")
        elif number == 2:
            valid = (
                len(line) in (5, 6)
                and line[0] in "RGB"
                and all(c in "0123456789" for c in line[1:4])
                and line[4:] in ("!", "!!")
            )
        elif number == 3:
            remaining = line
            while remaining.startswith(("RYG", "RG")):
                remaining = (
                    remaining[3:] if remaining.startswith("RYG") else remaining[2:]
                )
            valid = bool(line) and not remaining
        else:
            valid = (
                len(line) == 4
                and all("a" <= c <= "z" for c in line)
                and line == line[::-1]
            )
        if valid:
            result.append(line)
    assert definition.judge.expected_output == "\n".join(result) + "\n"
    with Image.open(PROBLEMS / "image" / f"{problem_id}.jpg") as image:
        image.load()
        assert image.format == "JPEG"
        assert image.convert("RGB").getextrema() == ((255, 255),) * 3


def test_regex_catalog_and_details() -> None:
    # 本番と同じmanifest検証を通し、例題を先頭にした4問が一覧と詳細に公開されることを確認する。
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    summaries = json.loads(repository.catalog.response_body)
    regex = [item for item in summaries if item["category"] == "REGEX"]
    assert [item["id"] for item in regex] == [f"REGEX-{n:08}" for n in (1, 2, 3, 4)]
    for item in regex:
        detail = repository.require(item["id"]).api_detail()
        assert detail["title_ja"] == item["title_ja"]
        assert detail["title_en"] == item["title_en"]
        assert detail["input"]
        assert detail["expected_output"]
