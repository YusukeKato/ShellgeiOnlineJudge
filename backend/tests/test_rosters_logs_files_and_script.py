"""4問の公開入力から、シェルの回答例とは独立に想定出力を求める。"""

from pathlib import Path

from soj_shared.problem_repository import build_problem_repository

PROBLEMS = Path(__file__).resolve().parents[2] / "problems"


def test_public_problem_outputs() -> None:
    """集合積、復号したログ、ファイルサイズ、見出しのバイト位置を公開fixtureと照合する。"""
    repo = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    roster = repo.require("PRACTICE-comm-01")
    second = dict(roster.fixtures)["second.txt"]
    for statement in (roster.definition.statement.ja, roster.definition.statement.en):
        assert second in statement
    names = set(roster.input_text.splitlines()).intersection(second.splitlines())
    assert roster.expected_output == "".join(name + "\n" for name in sorted(names))

    warnings = repo.require("STANDARD-00000073")
    log = bytes.fromhex(warnings.input_text).decode("ascii")
    messages = [line[5:] for line in log.splitlines() if line.startswith("WARN ")]
    assert warnings.expected_output == "".join(message + "\n" for message in messages)

    paths = repo.require("PRACTICE-test-01")
    sizes = {name: len(content.encode()) for name, content in paths.fixtures}
    assert "data/missing.txt" not in sizes and "data/empty.txt" not in sizes
    sizes["data/empty.txt"] = 0
    rows = []
    for path in paths.input_text.splitlines():
        status = "MISSING" if path not in sizes else "DATA" if sizes[path] else "EMPTY"
        rows.append(f"{path} {status}\n")
    assert paths.expected_output == "".join(rows)

    script = repo.require("STANDARD-00000074")
    raw = script.input_text.encode()
    offsets = [0, *(i + 1 for i, byte in enumerate(raw) if byte == 10)]
    headings = []
    for offset in offsets:
        if raw.startswith(b"@@ ", offset):
            name = raw[offset + 3 :].split(b"\n", 1)[0].decode()
            headings.append(f"{offset} {name}\n")
    assert script.expected_output == "".join(headings)
