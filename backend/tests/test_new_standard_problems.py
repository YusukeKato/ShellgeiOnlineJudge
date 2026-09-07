"""通常53〜60の期待値を、参照シェル解とは独立した処理で検証する。"""

from collections import Counter
from pathlib import Path

import pytest
from PIL import Image

from soj_shared.problem_schema import load_problem_definition


PROBLEMS = Path(__file__).resolve().parents[2] / "problems"


@pytest.mark.parametrize("number", range(53, 61))
def test_new_standard_problem_expectations(number: int) -> None:
    # 公開入力から期待値を独立計算し、空欄・区間境界・出力順まで完全一致で検査する。
    problem_id = f"STANDARD-{number:08}"
    definition = load_problem_definition(PROBLEMS / "v3" / f"{problem_id}.yaml")
    assert definition.judge.type == "text"
    assert definition.execution.exit_code == "zero"
    assert definition.execution.stderr == "must_be_empty"
    assert len(definition.execution.fixtures) == 1
    assert definition.execution.fixtures[0].path == "input.txt"
    content = definition.execution.fixtures[0].content
    lines = content.splitlines()
    result: list[str] = []
    if number == 53:
        devices = sorted({line.split()[0] for line in lines})
        result = [
            [line for line in lines if line.split()[0] == device][-1]
            for device in devices
        ]
    elif number == 54:
        measurements = [line.split() for line in lines]
        result = [
            f"{current[0]} {int(current[1]) - int(previous[1])}"
            for previous, current in zip(measurements, measurements[1:])
        ]
    elif number == 55:
        # 境界の行番号から区間を切り出し、参照解答の範囲状態とは別に確認する。
        starts = [i for i, line in enumerate(lines) if line == "BEGIN"]
        ends = [i for i, line in enumerate(lines) if line == "END"]
        assert len(starts) == len(ends)
        for start, end in zip(starts, ends):
            assert start < end
            result.extend(lines[start + 1 : end])
    elif number == 56:
        fields = [line.split("\t") for line in lines]
        assert all(len(row) == 4 for row in fields)
        result = [f"{row[0]}\t{row[2]}" for row in fields]
    elif number == 57:
        counts = Counter(line.rsplit(".", 1)[1].lower() for line in lines)
        result = [f"{extension} {counts[extension]}" for extension in sorted(counts)]
    elif number == 58:
        records = [line.split() for line in lines]
        result = sorted(
            f"{team} {person} {document}"
            for kind, team, person in records
            for other_kind, other_team, document in records
            if kind == "team" and other_kind == "file" and team == other_team
        )
    elif number == 59:
        # 元のスペースを1文字幅の印で保護し、expandtabsが追加した空白だけを可視化する。
        assert "\0" not in content
        result = [
            line.replace(" ", "\0").expandtabs(4).replace(" ", ">").replace("\0", " ")
            for line in lines
        ]
    else:
        intervals = [line.split()[1:] for line in lines]
        assert all(start < end for start, end in intervals)
        times = [
            f"{minute // 60:02}:{minute % 60:02}" for minute in range(540, 661, 10)
        ]
        # イベントの累積を使わず、各時刻に区間を直接数える。
        result = [
            f"{time} {sum(start <= time < end for start, end in intervals)}"
            for time in times
        ]
    assert definition.judge.expected_output == "\n".join(result) + "\n"
    with Image.open(PROBLEMS / "image" / f"{problem_id}.jpg") as image:
        image.load()
        assert image.format == "JPEG"
        assert image.convert("RGB").getextrema() == ((255, 255),) * 3
