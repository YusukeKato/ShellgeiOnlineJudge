"""UTF-8のbyte表示問題で、固定入力・実行policyと独立した期待値を検査する。"""

from pathlib import Path

from PIL import Image

from soj_shared.problem_schema import load_problem_definition


PROBLEMS = Path(__file__).resolve().parents[2] / "problems"
PROBLEM_ID = "PRACTICE-od-01"


def test_byte_display_schema_fixture_and_preview() -> None:
    # 連続する2空白・合成済みU+00E9・U+732B・末尾LFを含む入力と白JPEGを確認する。
    definition = load_problem_definition(PROBLEMS / "v3" / f"{PROBLEM_ID}.yaml")
    assert definition.schema_version == 3
    assert definition.category == "PRACTICE"
    assert definition.judge.type == "text"
    assert definition.execution.stdin == ""
    assert definition.execution.exit_code == "zero"
    assert definition.execution.stderr == "must_be_empty"
    assert len(definition.execution.fixtures) == 1
    assert definition.execution.fixtures[0].path == "input.txt"
    assert definition.execution.fixtures[0].content == "A  \u00e9\n\u732b\n"
    with Image.open(PROBLEMS / "image" / f"{PROBLEM_ID}.jpg") as image:
        image.load()
        assert image.format == "JPEG"
        assert image.convert("RGB").getextrema() == ((255, 255),) * 3


def test_byte_display_expected_output_follows_utf8_bit_groups() -> None:
    # odや数値出力の整形を使わず、各コードポイントをUTF-8のbit群へ分けて期待値を求める。
    definition = load_problem_definition(PROBLEMS / "v3" / f"{PROBLEM_ID}.yaml")
    assert definition.judge.type == "text"
    content = definition.execution.fixtures[0].content
    octets: list[int] = []
    for character in content:
        scalar = ord(character)
        if scalar <= 0x7F:
            octets.append(scalar)
        elif scalar <= 0x7FF:
            octets.extend([0xC0 | (scalar >> 6), 0x80 | (scalar & 0x3F)])
        else:
            # 固定入力の残りはBMP内の文字で、surrogateはUnicode scalarではない。
            assert scalar <= 0xFFFF and not 0xD800 <= scalar <= 0xDFFF
            octets.extend(
                [
                    0xE0 | (scalar >> 12),
                    0x80 | ((scalar >> 6) & 0x3F),
                    0x80 | (scalar & 0x3F),
                ]
            )
    assert len(octets) == 10
    assert bytes(octets) == content.encode("utf-8")
    assert definition.judge.expected_output == "".join(
        f"{octet:02x}\n" for octet in octets
    )
