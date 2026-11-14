"""chmod練習問題の手計算・独立期待値・公開データの整合を確認する。"""

from pathlib import Path
import re

import pytest
from PIL import Image

from soj_shared.problem_repository import build_problem_repository
from soj_shared.problem_schema import load_problem_definition

PROBLEMS = Path(__file__).resolve().parents[2] / "problems"
PROBLEM_ID = "PRACTICE-chmod-01"
ALTERNATIVE = (
    "chmod 644 target.txt && xargs -r -I{} sh -c "
    "'chmod \"$1\" target.txt && stat -c %03a target.txt' sh '{}' < input.txt"
)
CASES = [
    ("public", "u+x\ng+w\no-r\ng=rx\na-x\n", "744\n764\n760\n750\n640\n"),
    ("empty", "", ""),
    ("single", "u+x\n", "744\n"),
    ("idempotent", "g+w\ng+w\no-r\no-r\n", "664\n664\n660\n660\n"),
    ("order", "g=rx\ng+w\n", "654\n674\n"),
    ("clear_and_recover", "a=\nu+r\n", "000\n400\n"),
    ("no_final_lf", "u+x\no-r", "744\n740\n"),
    ("multiple_classes", "ug+x\nug-w\n", "754\n554\n"),
    ("other_only", "o=rx\n", "645\n"),
]


def expected_permissions(operations: str) -> str:
    """解法検査のu/g/o/a・+/-/=・rwxを3区分の集合で更新し、各状態の8進数を返す。

    chmod/statの出力や実fileのmodeには依存しない。範囲外のtest caseはValueErrorで止める。
    統合検査でもこの独立期待値と手計算caseを再利用する。
    """
    groups = {"u": set("rw"), "g": set("r"), "o": set("r")}
    rows = []
    for operation in operations.splitlines():
        match = re.fullmatch(r"([ugoa]+)([+=-])([rwx]*)", operation)
        if match is None:
            raise ValueError(f"unsupported permission test case: {operation}")
        who, action, rights = match.groups()
        targets = set("ugo") if "a" in who else set(who)
        for key in targets:
            if action == "+":
                groups[key] |= set(rights)
            elif action == "-":
                groups[key] -= set(rights)
            else:
                groups[key] = set(rights)
        rows.append(
            "".join(
                str(sum({"r": 4, "w": 2, "x": 1}[right] for right in groups[key]))
                for key in "ugo"
            )
        )
    return "".join(row + "\n" for row in rows)


@pytest.mark.parametrize("label,operations,expected", CASES)
def test_permission_sets_match_manual_cases(
    label: str, operations: str, expected: str
) -> None:
    """追加・削除・置換・対象区分・000の表現を、手計算と独立した集合モデルで照合する。"""
    assert expected_permissions(operations) == expected, label


def test_public_chmod_data_matches_independent_permission_trace() -> None:
    """公開5操作の各状態を独立に求め、隠れた初期modeへの依存やfixture違いを検出する。"""
    definition = load_problem_definition(PROBLEMS / "v3" / f"{PROBLEM_ID}.yaml")
    fixtures = {
        fixture.path: fixture.content for fixture in definition.execution.fixtures
    }
    assert fixtures == {"input.txt": CASES[0][1], "target.txt": "sample\n"}
    assert definition.judge.type == "text"
    assert definition.judge.expected_output == expected_permissions(
        fixtures["input.txt"]
    )
    assert definition.judge.expected_output.splitlines() == [
        "744",
        "764",
        "760",
        "750",
        "640",
    ]


def test_chmod_public_dto_policy_and_preview() -> None:
    """追加fixtureと初期状態の日英説明、title、公開DTO、実行policy、白JPEGを確認する。"""
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(PROBLEM_ID)
    definition = record.definition
    assert definition.title.ja == definition.title.en == "chmod 1"
    for statement in (definition.statement.ja, definition.statement.en):
        for token in ("input.txt", "target.txt", "sample", "644", "+", "-", "="):
            assert token in statement
    assert "改行（LF）" in definition.statement.ja
    assert "line feed (LF)" in definition.statement.en
    assert definition.execution.stdin == ""
    assert definition.execution.exit_code == "zero"
    assert definition.execution.stderr == "must_be_empty"
    detail = record.api_detail()
    assert detail["input"] == CASES[0][1]
    assert detail["expected_output"] == CASES[0][2]
    assert detail["answer"] == definition.reference_solution
    assert detail["image"] == f"/image/{PROBLEM_ID}.jpg"
    with Image.open(PROBLEMS / "image" / f"{PROBLEM_ID}.jpg") as image:
        image.load()
        assert image.format == "JPEG"
        assert image.convert("RGB").getextrema() == ((255, 255),) * 3
