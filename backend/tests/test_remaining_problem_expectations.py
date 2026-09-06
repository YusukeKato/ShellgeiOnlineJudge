"""残りの通常・練習問題の期待出力を、参照shellとは別の処理で検算する。"""

from collections import Counter, deque
from decimal import Decimal, ROUND_HALF_UP
from itertools import groupby, permutations
from math import gcd, lcm
from pathlib import Path
import re

import pytest

from soj_shared.problem_schema import load_problem_definition

PROBLEMS = Path(__file__).resolve().parents[2] / "problems/v3"


def _expected(number: int, data: str) -> str:
    # 小さな入力をPythonで独立計算し、shell解答のコピーでは検出できない期待値の誤りを調べる。
    rows = data.splitlines()
    result: list[str | int] = []
    if number == 21:
        result = ["YES" if row == row[::-1] else "NO" for row in rows]
    elif number == 22:
        result = [len(str(2**1024))]
    elif number == 23:
        result = [
            sum(dict(A=1, B=1, C=1, D=2, E=2, F=3)[c] for c in row) for row in rows
        ]
    elif number == 24:
        stock = {
            name: int(n) for kind, name, n in map(str.split, rows) if kind == "stock"
        }
        orders = {
            name: int(n) for kind, name, n in map(str.split, rows) if kind == "order"
        }
        result = [
            f"{name} {orders[name] - stock.get(name, 0)}"
            for name in sorted(orders)
            if orders[name] > stock.get(name, 0)
        ]
    elif number == 25:
        result = ["".join(p) for p in permutations("ABC")]
    elif number == 26:
        start = next(
            (r, c)
            for r, row in enumerate(rows)
            for c, ch in enumerate(row)
            if ch == "S"
        )
        queue = deque([(start, 0)])
        seen = {start}
        while queue:
            (r, c), distance = queue.popleft()
            if rows[r][c] == "G":
                result = [distance]
                break
            for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                if (
                    0 <= nr < len(rows)
                    and 0 <= nc < len(rows[0])
                    and rows[nr][nc] != "#"
                    and (nr, nc) not in seen
                ):
                    seen.add((nr, nc))
                    queue.append(((nr, nc), distance + 1))
    elif number == 27:
        reachable = {("A", 480)}
        trips = [
            (
                a,
                b,
                int(d.split(":")[0]) * 60 + int(d.split(":")[1]),
                int(t.split(":")[0]) * 60 + int(t.split(":")[1]),
            )
            for a, b, d, t in map(str.split, rows)
        ]
        # 順序依存のない到達可能状態の固定点で、参照解答の時刻順走査を検算する。
        while True:
            expanded = reachable | {
                (b, t)
                for a, b, d, t in trips
                if any(s == a and time <= d for s, time in reachable)
            }
            if expanded == reachable:
                break
            reachable = expanded
        minute = min(t for s, t in reachable if s == "D")
        result = [f"{minute // 60}:{minute % 60:02d}"]
    elif number == 28:
        n = int(rows[0])
        size = 2 * n - 1
        result = [
            "".join(str(n - min(r, c, size - 1 - r, size - 1 - c)) for c in range(size))
            for r in range(size)
        ]
    elif number == 29:
        result = [" ".join(rows[i : i + 4]) for i in range(0, len(rows), 4)]
    elif number == 30:
        result = [
            "".join(
                chr((ord(c) - 65 - 8) % 26 + 65) if "A" <= c <= "Z" else c for c in row
            )
            for row in rows
        ]
    elif number in (31, 32):
        result = [(gcd if number == 31 else lcm)(*map(int, rows))]
    elif number == 33:
        result = [f"{row[0]} {len(row)}" for row in rows]
    elif number == 34:
        result = [next(x for x in range(2, 101) if x**5 == int(row)) for row in rows]
    elif number == 35:
        result = [row for row in rows for _ in range(2)]
    elif number == 36:
        result = [row for row in rows for _ in range(int(row))]
    elif number == 37:
        result = re.findall(r"[0-9]+", data)
    elif number == 38:
        result = [
            "Yes" if int(a) % int(b) == 0 else "No" for a, b in map(str.split, rows)
        ]
    elif number == 39:
        result = ["".join(c for c in rows[0] if rows[0].count(c) == 1)]
    elif number == 40:
        result = [f"{c} {data.count(c)}" for c in "abc"]
    elif number == 41:
        grid = [row.split() for row in rows]
        # 行だけでなく列と両対角線も一致することを全探索で確認する。
        candidates = []
        for x in range(-100, 101):
            g = [[x if c == "x" else int(c) for c in row] for row in grid]
            sums = (
                [sum(row) for row in g]
                + [sum(row[c] for row in g) for c in range(3)]
                + [sum(g[i][i] for i in range(3)), sum(g[i][2 - i] for i in range(3))]
            )
            if len(set(sums)) == 1:
                candidates.append(g)
        assert len(candidates) == 1
        result = [" ".join(map(str, row)) for row in candidates[0]]
    elif number == 42:
        result = [f"{name:<8} | {int(n):>4}" for name, n in map(str.split, rows)]
    elif number == 43:
        result = [f"{row}.png {row}.jpg" for row in rows]
    elif number == 45:
        result = ["".join(c * 3 for c in row) for row in rows for _ in range(3)]
    elif number == 46:
        result = [
            "".join("1" if r == c else "0" for c in range(int(n)))
            for n in rows
            for r in range(int(n))
        ]
    elif number == 47:
        result = [
            token
            for token in data.split()
            if len(token.split(".")) == 4
            and all(
                p.isascii() and p.isdigit() and 0 <= int(p) <= 255
                for p in token.split(".")
            )
        ]
    elif number == 48:
        result = ["".join(c + str(len(list(group))) for c, group in groupby(rows[0]))]
    elif number == 49:
        result = [
            max(
                (
                    row[a:b]
                    for a in range(len(row))
                    for b in range(a + 1, len(row) + 1)
                    if row[a:b] == row[a:b][::-1]
                ),
                key=len,
            )
            for row in rows
        ]
    elif number == 51:
        averages = [
            (
                name,
                (Decimal(h) / Decimal(a)).quantize(
                    Decimal(".001"), rounding=ROUND_HALF_UP
                ),
            )
            for name, a, h in map(str.split, rows)
        ]
        result = [
            f"{name} {value:.3f}"
            for name, value in sorted(averages, key=lambda p: (-p[1], p[0]))
        ]
    else:
        raise AssertionError(number)
    return "".join(str(value) + "\n" for value in result)


@pytest.mark.parametrize("number", [n for n in range(21, 52) if n not in (44, 50)])
def test_remaining_standard_expected_outputs(number: int) -> None:
    # 外部ファイル検索と数式処理以外は、入力から全期待値を独立に導出して照合する。
    definition = load_problem_definition(PROBLEMS / f"STANDARD-{number:08d}.yaml")
    assert definition.judge.type == "text"
    data = "".join(f.content for f in definition.execution.fixtures)
    assert _expected(number, data).rstrip(
        " \n"
    ) == definition.judge.expected_output.rstrip(" \n")


@pytest.mark.parametrize(
    "name",
    [
        "grep-01",
        "grep-02",
        "grep-03",
        "grep-04",
        "sed-01",
        "sed-02",
        "sed-03",
        "sed-04",
        "sed-05",
        "sed-06",
        "sort-01",
        "sort-02",
        "sort-03",
        "cat-02",
        "cat-03",
        "wc-02",
        "wc-03",
        "uniq-01",
        "uniq-02",
    ],
)
def test_practice_counterexamples(name: str) -> None:
    # 部分一致・末尾一致・数値順・空行・文字数など、今回補った違いを独立に検算する。
    definition = load_problem_definition(PROBLEMS / f"PRACTICE-{name}.yaml")
    assert definition.judge.type == "text"
    data = definition.execution.fixtures[0].content
    rows = data.splitlines()
    result: list[str | int]
    if name.startswith("grep"):
        predicates = {
            "grep-01": lambda s: ".jpg" in s,
            "grep-02": lambda s: s.endswith((".jpg", ".png")),
            "grep-03": lambda s: not s.endswith(".txt"),
            "grep-04": lambda s: s.endswith(".jpg"),
        }
        result = [row for row in rows if predicates[name](row)]
    elif name == "sed-01":
        result = [row.replace("XXX", "SHELLGEI") for row in rows]
    elif name == "sed-02":
        result = [
            row.replace("XXX", "SHELLGEI").replace("YYY", "ONLINE") for row in rows
        ]
    elif name == "sed-03":
        result = ["".join(c for c in row if c not in "0123456789") for row in rows]
    elif name == "sed-04":
        result = [row for row in rows if not row.isdigit()]
    elif name == "sed-05":
        result = [row for row in rows if any(c in "0123456789" for c in row)]
    elif name == "sed-06":
        result = [row + ".jpg" for row in rows]
    elif name.startswith("sort"):
        values = list(map(int, rows))
        result = list(
            sorted(
                set(values) if name == "sort-03" else values, reverse=name == "sort-02"
            )
        )
    elif name == "cat-02":
        result = [f"{i:6}\t{row}" for i, row in enumerate(rows, 1)]
    elif name == "cat-03":
        result = [row + "$" for row in rows]
    elif name == "wc-02":
        result = [len(data.split())]
    elif name == "wc-03":
        result = [len(data)]
    elif name == "uniq-01":
        result = list(sorted(set(rows)))
    else:
        result = [f"{count:7} {row}" for row, count in sorted(Counter(rows).items())]
    assert (
        "".join(str(value) + "\n" for value in result)
        == definition.judge.expected_output
    )
