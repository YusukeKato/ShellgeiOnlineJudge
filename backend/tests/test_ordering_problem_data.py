"""通常62・63の数値順と依存順を、参照シェル解とは独立して検証する。"""

from itertools import permutations
from pathlib import Path
import re

import pytest
from PIL import Image

from soj_shared.problem_schema import load_problem_definition


PROBLEMS = Path(__file__).resolve().parents[2] / "problems"


@pytest.mark.parametrize("number", [62, 63])
def test_ordering_problem_schema_policy_and_preview(number: int) -> None:
    # text問題の共通実行条件と、完全decodeした表示用白JPEGを確認する。
    problem_id = f"STANDARD-{number:08}"
    definition = load_problem_definition(PROBLEMS / "v3" / f"{problem_id}.yaml")
    assert definition.schema_version == 3
    assert definition.category == "STANDARD"
    assert definition.judge.type == "text"
    assert definition.execution.stdin == ""
    assert definition.execution.exit_code == "zero"
    assert definition.execution.stderr == "must_be_empty"
    assert len(definition.execution.fixtures) == 1
    assert definition.execution.fixtures[0].path == "input.txt"
    with Image.open(PROBLEMS / "image" / f"{problem_id}.jpg") as image:
        image.load()
        assert image.format == "JPEG"
        assert image.convert("RGB").getextrema() == ((255, 255),) * 3


def test_version_order_expected_output_preserves_original_lines() -> None:
    # version sortを使わず3整数のtupleで比較し、vを含む元行を保持した昇順を確認する。
    definition = load_problem_definition(PROBLEMS / "v3/STANDARD-00000062.yaml")
    assert definition.judge.type == "text"
    lines = definition.execution.fixtures[0].content.splitlines()
    assert len(lines) == 7
    assert all(re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", line) for line in lines)
    version_keys = {line: tuple(map(int, line[1:].split("."))) for line in lines}
    expected = sorted(lines, key=version_keys.__getitem__)
    assert definition.judge.expected_output == "\n".join(expected) + "\n"


def test_task_order_is_the_only_permutation_satisfying_every_edge() -> None:
    # tsortやKahn法を使わず全720順列を調べ、9関係を満たす唯一の順序を確認する。
    definition = load_problem_definition(PROBLEMS / "v3/STANDARD-00000063.yaml")
    assert definition.judge.type == "text"
    edges = [
        tuple(line.split())
        for line in definition.execution.fixtures[0].content.splitlines()
    ]
    assert len(edges) == 9
    assert all(len(edge) == 2 for edge in edges)
    tasks = sorted({task for edge in edges for task in edge})
    assert len(tasks) == 6
    valid_orders = [
        order
        for order in permutations(tasks)
        if all(order.index(before) < order.index(after) for before, after in edges)
    ]
    assert len(valid_orders) == 1
    assert definition.judge.expected_output == "\n".join(valid_orders[0]) + "\n"
