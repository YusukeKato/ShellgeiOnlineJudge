"""joinとfactorの公開期待値を参照commandと独立に確認する。"""

import math
from pathlib import Path

import pytest
from PIL import Image

from soj_shared.problem_repository import build_problem_repository
from soj_shared.problem_schema import load_problem_definition

PROBLEMS = Path(__file__).resolve().parents[2] / "problems"


def test_join_expected_rows_preserve_orders_and_unknown_names() -> None:
    """公開5明細の手作業対応と辞書参照・数値sortを独立照合する。"""
    definition = load_problem_definition(PROBLEMS / "v3/PRACTICE-join-01.yaml")
    fixtures = {f.path: f.content for f in definition.execution.fixtures}
    catalog = dict(row.split() for row in fixtures["catalog.txt"].splitlines())
    orders = [
        (code, int(quantity))
        for code, quantity in (
            row.split() for row in fixtures["input.txt"].splitlines()
        )
    ]
    rows = [
        (code, catalog.get(code, "UNKNOWN"), quantity)
        for code, quantity in sorted(orders)
    ]
    assert rows == [
        ("A05", "Apple", 3),
        ("B10", "Book", 8),
        ("C20", "Cable", 2),
        ("C20", "Cable", 12),
        ("D40", "UNKNOWN", 1),
    ]
    assert definition.judge.type == "text"
    assert definition.judge.expected_output == "".join(
        f"{code} {name} {quantity}\n" for code, name, quantity in rows
    )


def test_factor_expected_products_and_multiplicity() -> None:
    """手計算の積・素数性・順序・重複から公開6行を確認し、factor出力をoracleにしない。"""
    definition = load_problem_definition(PROBLEMS / "v3/PRACTICE-factor-01.yaml")
    numbers = [int(v) for v in definition.execution.fixtures[0].content.split()]
    factors = [[2, 2, 3, 7], [13], [], [2, 2, 2, 2, 2, 2], [2, 2, 3, 7], [2, 2, 5, 5]]
    assert numbers == [84, 13, 1, 64, 84, 100]
    for number, parts in zip(numbers, factors, strict=True):
        assert math.prod(parts) == number
        assert parts == sorted(parts)
        assert all(all(p % d for d in range(2, math.isqrt(p) + 1)) for p in parts)
    assert definition.judge.type == "text"
    assert definition.judge.expected_output == "".join(
        f"{number}:" + "".join(f" {p}" for p in parts) + "\n"
        for number, parts in zip(numbers, factors, strict=True)
    )


@pytest.mark.parametrize("command", ["join", "factor"])
def test_new_practice_public_dto_policy_and_preview(command: str) -> None:
    """日英title・入力欄外catalog全文・公開DTO・終了policy・白JPEGを検査する。"""
    problem_id = f"PRACTICE-{command}-01"
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(problem_id)
    definition = record.definition
    fixtures = {f.path: f.content for f in definition.execution.fixtures}
    assert definition.title.ja == definition.title.en == f"{command} 1"
    for statement in (definition.statement.ja, definition.statement.en):
        assert "input.txt" in statement
        if command == "join":
            assert "catalog.txt" in statement
            assert fixtures["catalog.txt"] in statement
    assert definition.execution.stdin == ""
    assert definition.execution.exit_code == "zero"
    assert definition.execution.stderr == "must_be_empty"
    detail = record.api_detail()
    assert detail["input"] == fixtures["input.txt"]
    assert detail["expected_output"] == record.expected_output
    assert detail["answer"] == definition.reference_solution
    assert detail["image"] == f"/image/{problem_id}.jpg"
    with Image.open(PROBLEMS / "image" / f"{problem_id}.jpg") as image:
        image.load()
        assert image.format == "JPEG"
        assert image.convert("RGB").getextrema() == ((255, 255),) * 3
