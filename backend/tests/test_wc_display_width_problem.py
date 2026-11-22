"""駅の案内板の公開入力と想定幅をシェルの回答例から独立に確認する。"""

from pathlib import Path

from soj_shared.problem_repository import build_problem_repository


def test_station_display_width() -> None:
    """8桁境界のタブや同一行内の複数タブを展開し、各行の幅と最大幅を照合する。"""
    problems = Path(__file__).resolve().parents[2] / "problems"
    repo = build_problem_repository(
        problems / "v3", problems / "image", problems / "v3/manifest.json"
    )
    record = repo.require("PRACTICE-wc-04")
    widths = [len(line.expandtabs(8)) for line in record.input_text.splitlines()]
    assert widths == [12, 18, 16, 17]
    assert record.expected_output == f"{max(widths)}\n"
