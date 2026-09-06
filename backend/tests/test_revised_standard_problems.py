"""改訂問題の期待出力を、参照shell commandと独立した計算・データ操作で確認する。"""

from datetime import date
from decimal import Decimal, ROUND_DOWN
from itertools import accumulate
import math
from pathlib import Path
import re

from soj_shared.models.problem import ProblemDefinitionV3
from soj_shared.problem_schema import load_problem_definition


PROBLEMS = Path(__file__).resolve().parents[2] / "problems/v3"


def _problem(number: int) -> tuple[str, str]:
    # 指定したtext問題の公開入力と期待出力を返し、fixtureがUIで見える1つだけであることも確認する。
    definition: ProblemDefinitionV3 = load_problem_definition(
        PROBLEMS / f"STANDARD-{number:08d}.yaml"
    )
    assert definition.judge.type == "text"
    assert len(definition.execution.fixtures) <= 1
    assert all(f.path == "input.txt" for f in definition.execution.fixtures)
    content = (
        definition.execution.fixtures[0].content
        if definition.execution.fixtures
        else ""
    )
    return content, definition.judge.expected_output


def test_sequence_expected_output() -> None:
    # 生成対象が1から10まで、重複・欠番なく昇順に並ぶことを確認する。
    content, output = _problem(3)
    assert content == ""
    assert output.splitlines() == [str(n) for n in range(1, 11)]


def test_inventory_expected_output() -> None:
    # 増減の累積和から期待在庫を独立計算し、出庫と在庫0の境界を含むことを確認する。
    content, output = _problem(5)
    entries = [line.split(" ") for line in content.splitlines()]
    times = [time for time, _ in entries]
    changes = [int(change) for _, change in entries]
    stocks = list(accumulate(changes))
    assert times == sorted(times)
    assert min(stocks) == 0
    assert any(change < 0 for change in changes)
    assert output.splitlines() == [
        f"{time} {stock}" for time, stock in zip(times, stocks)
    ]


def test_pi_expected_output() -> None:
    # 標準libraryの円周率を十進で切り捨て、四捨五入との差が期待値に現れることを確認する。
    content, output = _problem(6)
    assert content == ""
    pi = Decimal(str(math.pi))
    assert output.strip() == str(
        pi.quantize(Decimal("0.0000000001"), rounding=ROUND_DOWN)
    )
    assert output.strip() != f"{math.pi:.10f}"


def test_wrapped_numbers_expected_output() -> None:
    # 既知の整数計算で全桁を確認し、継続改行だけを除去した復元結果と一致させる。
    content, output = _problem(7)
    values = [2**128, 2**10, math.factorial(20), 2**64]
    assert output.splitlines() == [str(value) for value in values]
    assert content.replace("\\\n", "") == output
    assert "1024\n" in content  # 折り返しのない記録も、そのまま独立して残す。
    assert content.count("\\\n") >= 3


def test_cranes_and_turtles_expected_output() -> None:
    # 期待解から頭数と足数を逆算し、0匹と旧解答の探索上限を超える入力を確認する。
    content, output = _problem(8)
    inputs = [tuple(map(int, line.split())) for line in content.splitlines()]
    counts = [tuple(map(int, line.split())) for line in output.splitlines()]
    assert len(inputs) == len(counts)
    assert any(c == 0 for c, _ in counts)
    assert any(t == 0 for _, t in counts)
    assert any(c >= 10 and t >= 10 for c, t in counts)
    for (animals, legs), (cranes, turtles) in zip(inputs, counts):
        assert 1 <= animals <= 100
        assert cranes >= 0 and turtles >= 0
        assert cranes + turtles == animals
        assert 2 * cranes + 4 * turtles == legs


def test_diary_expected_output_preserves_records() -> None:
    # 暦として解釈した先頭日付で並べ替え、本文内の空白・日付・改行が保存されることを確認する。
    content, output = _problem(9)
    entries = content.rstrip("\n").split("\n\n")
    dated = [
        (date.fromisoformat(entry.splitlines()[0].replace("/", "-")), entry)
        for entry in entries
    ]
    assert len({day for day, _ in dated}) == len(entries)
    assert (
        output == "\n\n".join(entry for _, entry in sorted(dated, reverse=True)) + "\n"
    )
    assert "read  more books" in output
    assert "メモ：2023/05/05 の写真を整理" in output


def test_template_expected_output_uses_exact_placeholders() -> None:
    # キー検索で穴だけを置換し、同一行での反復・表と異なる登場順・通常の英単語を確認する。
    content, output = _problem(10)
    table, body = content.split("\n---\n")
    pairs = [line.split("=", 1) for line in table.splitlines()]
    values = dict(pairs)
    assert len(values) == len(pairs)
    keys = re.findall(r"{{([a-z]+)}}", body)
    assert set(keys) <= values.keys()
    assert keys[0] != pairs[0][0]
    assert any(line.count("{{view}}") == 2 for line in body.splitlines())
    placeholder = re.compile(r"{{([a-z]+)}}")
    assert output == placeholder.sub(lambda match: values[match[1]], body)
    assert "river  train" in output
