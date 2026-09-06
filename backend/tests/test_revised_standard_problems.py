"""改訂問題の期待出力を、参照shell commandと独立した計算・データ操作で確認する。"""

from datetime import date
from decimal import Decimal, ROUND_DOWN
from itertools import accumulate
import html
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


def test_matrix_rotation_expected_output() -> None:
    # 長方形の行列を座標で回転し、複数桁・負数の要素が文字単位に反転されないことを確認する。
    content, output = _problem(11)
    matrix = [line.split() for line in content.splitlines()]
    assert len(matrix) != len(matrix[0])
    assert all(len(row) == len(matrix[0]) for row in matrix)
    expected = [
        " ".join(matrix[row][column] for row in range(len(matrix) - 1, -1, -1))
        for column in range(len(matrix[0]))
    ]
    assert output.splitlines() == expected
    assert any(int(value) < 0 for row in matrix for value in row)
    assert any(int(value) >= 10 for row in matrix for value in row)


def test_bit_inversion_expected_output() -> None:
    # 各bitを1から引いて期待値を確認し、複数行の境界と文字数が変わらないことを確認する。
    content, output = _problem(12)
    assert output.splitlines() == [
        "".join(str(1 - int(bit)) for bit in line) for line in content.splitlines()
    ]
    assert len(content.splitlines()) > 1
    assert any(set(line) == {"0"} for line in content.splitlines())
    assert any(set(line) == {"1"} for line in content.splitlines())


def test_missing_letters_expected_output() -> None:
    # 文字集合の補集合を独立に求め、欠落が複数あり入力の重複を数えないことを確認する。
    content, output = _problem(13)
    letters = content.replace("\n", "")
    alphabet = {chr(n) for n in range(ord("a"), ord("z") + 1)}
    assert set(letters) <= alphabet
    assert len(letters) > len(set(letters))
    assert output.splitlines() == sorted(alphabet - set(letters))
    assert len(output.splitlines()) > 1


def test_grouped_teams_expected_output() -> None:
    # 元の入力をチーム別に集め、数値順・欠番・チーム内の登場順を独立確認する。
    content, output = _problem(14)
    teams: dict[int, list[str]] = {}
    for line in content.splitlines():
        name, team = line.split()
        teams.setdefault(int(team), []).append(name)
    assert min(teams) > 1
    assert max(teams) >= 10
    assert sorted(teams) != sorted(teams, key=str)
    assert output.splitlines() == [
        f"{team} {' '.join(teams[team])}" for team in sorted(teams)
    ]


def test_primality_expected_output() -> None:
    # factorを使わず平方根まで試し割りし、1・平方数を含む入力のYES/NOを確認する。
    content, output = _problem(15)
    values = [int(line) for line in content.splitlines()]
    assert all(1 <= n <= 10000 for n in values)
    assert 1 in values
    assert any(n > 1 and math.isqrt(n) ** 2 == n for n in values)
    assert output.splitlines() == [
        "YES" if n >= 2 and all(n % d for d in range(2, math.isqrt(n) + 1)) else "NO"
        for n in values
    ]


def test_html_display_expected_output() -> None:
    # 標準libraryの文字参照変換で照合し、入力の既存entityと引用符・空白の保持を確認する。
    content, output = _problem(16)
    assert output == html.escape(content, quote=False)
    assert "&lt;" in content and "&amp;lt;" in output
    assert 'title="A &amp; B"' in output
    assert "plain  text" in output


def test_slow_requests_expected_output() -> None:
    # 安定な数値ソートの上位3行と照合し、同率が採用・不採用の境界にあることを確認する。
    content, output = _problem(17)
    records = content.splitlines()
    ranked = sorted(records, key=lambda line: -int(line.split()[1]))
    assert output.splitlines() == ranked[:3]
    assert ranked[2].split()[1] == ranked[3].split()[1]
    assert ranked[2] != ranked[3]
    assert len({len(line.split()[1]) for line in records}) > 1


def test_integer_conditions_expected_output() -> None:
    # 全整数へ各条件を直接適用し、重複した条件・厳密な不等号・範囲端100を確認する。
    content, output = _problem(18)
    conditions = [
        (op, int(value)) for _, op, value in map(str.split, content.splitlines())
    ]
    assert all(op in {"<", ">"} and 0 <= value <= 200 for op, value in conditions)
    expected = [
        str(n)
        for n in range(1, 101)
        if all(n > value if op == ">" else n < value for op, value in conditions)
    ]
    assert output.splitlines() == expected
    assert len(expected) > 1 and expected[-1] == "100"
    assert len(conditions) > len(set(conditions))


def test_original_strings_expected_output() -> None:
    # 期待する元文字列を3回連結して入力へ戻し、最短周期だけを返す誤解と区別する。
    content, output = _problem(19)
    originals = output.splitlines()
    assert content.splitlines() == [original * 3 for original in originals]
    assert "GG" in originals
    assert all(line and re.fullmatch("[A-Z]+", line) for line in content.splitlines())


def test_prime_factor_counts_expected_output() -> None:
    # 各整数を試し割りして頻度を独立集計し、重複行と同一数内の因数の重複を確認する。
    content, output = _problem(20)
    counts: dict[int, int] = {}
    values = [int(line) for line in content.splitlines()]
    assert all(2 <= n <= 10000 for n in values)
    assert len(values) > len(set(values))
    for value in values:
        divisor = 2
        while divisor * divisor <= value:
            while value % divisor == 0:
                counts[divisor] = counts.get(divisor, 0) + 1
                value //= divisor
            divisor += 1
        if value > 1:
            counts[value] = counts.get(value, 0) + 1
    assert output.splitlines() == [
        f"{prime} {counts[prime]}" for prime in sorted(counts)
    ]
    assert any(prime >= 10 for prime in counts)
