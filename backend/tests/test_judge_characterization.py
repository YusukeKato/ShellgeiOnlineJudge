import base64
from pathlib import Path

import pytest
import yaml

from scripts.judge import ShellgeiJudge


PROBLEM_ID = "STANDARD-00000001"


def _judge_fixture(
    tmp_path: Path,
    *,
    expected_output: str = "expected",
    answer_image: bytes = b"answer-image" * 4,
) -> tuple[ShellgeiJudge, str]:
    # 一時領域に問題YAMLと正解画像を作り、実際のjudgeと比較用Base64画像を返す。
    yaml_directory = tmp_path / "problems" / "yaml_data"
    image_directory = tmp_path / "problems" / "image"
    yaml_directory.mkdir(parents=True)
    image_directory.mkdir(parents=True)
    (yaml_directory / f"{PROBLEM_ID}.yaml").write_text(
        yaml.safe_dump({"expected_output": expected_output}),
        encoding="utf-8",
    )
    (image_directory / f"{PROBLEM_ID}.jpg").write_bytes(answer_image)
    judge = ShellgeiJudge()
    judge.base_dir = tmp_path
    return judge, base64.b64encode(answer_image).decode("ascii")


@pytest.mark.parametrize(
    "text_matches,image_matches,expected_verdict",
    [
        (True, True, "1"),
        (True, False, "2"),
        (False, True, "3"),
        (False, False, "4"),
    ],
)
def test_legacy_judge_verdict_truth_table(
    tmp_path: Path,
    text_matches: bool,
    image_matches: bool,
    expected_verdict: str,
) -> None:
    # テキストと画像の一致・不一致の組み合わせが従来の判定番号になることを確認する。
    judge, matching_image = _judge_fixture(tmp_path)
    different_image = base64.b64encode(b"different-image" * 4).decode("ascii")

    assert (
        judge.judge(
            "expected" if text_matches else "different",
            matching_image if image_matches else different_image,
            PROBLEM_ID,
        )
        == expected_verdict
    )


@pytest.mark.parametrize(
    "output",
    [
        "expected",
        "expected\n",
        "expected\n\n",
        "expected ",
        "expected\r\n",
    ],
)
def test_legacy_judge_ignores_carriage_returns_and_trailing_spaces_or_newlines(
    tmp_path: Path,
    output: str,
) -> None:
    # CRと末尾の空白・改行を除外して比較する従来の文字列判定を確認する。
    judge, image = _judge_fixture(tmp_path, expected_output="expected\n")

    assert judge.judge(output, image, PROBLEM_ID) == "1"


def test_legacy_judge_keeps_tabs_significant(tmp_path: Path) -> None:
    # タブは通常の空白と同一視されず、文字列不一致になることを確認する。
    judge, image = _judge_fixture(tmp_path, expected_output="a b")

    assert judge.judge("a\tb", image, PROBLEM_ID) == "3"


def test_legacy_judge_maps_empty_output_and_answer_to_null(tmp_path: Path) -> None:
    # 利用者出力と期待出力が両方空の場合に正解となることを確認する。
    judge, image = _judge_fixture(tmp_path, expected_output="")

    assert judge.judge("", image, PROBLEM_ID) == "1"


@pytest.mark.xfail(
    strict=True,
    reason="SOJ-009: replacement tokens can collide with literal output",
)
def test_known_bug_replacement_token_must_not_false_accept(tmp_path: Path) -> None:
    # 実際の空白と文字列SPACEが衝突して誤って正解になる既知不具合を追跡する。
    judge, image = _judge_fixture(tmp_path, expected_output="SPACE")

    assert judge.judge(" ", image, PROBLEM_ID) != "1"


@pytest.mark.xfail(
    strict=True,
    reason="SOJ-009: literal NULL collides with an empty expected output",
)
def test_known_bug_literal_null_must_not_match_empty_answer(tmp_path: Path) -> None:
    # 空出力の内部表現と文字列NULLが衝突して誤って正解になる既知不具合を追跡する。
    judge, image = _judge_fixture(tmp_path, expected_output="")

    assert judge.judge("NULL", image, PROBLEM_ID) != "1"


@pytest.mark.xfail(
    strict=True,
    reason="SOJ-009: the first 28 Base64 characters are excluded from comparison",
)
def test_known_bug_image_prefix_difference_must_not_be_ignored(tmp_path: Path) -> None:
    # 画像先頭21 byteだけの違いを検出できない既知不具合を追跡する。
    suffix = b"same-image-suffix"
    judge, _ = _judge_fixture(
        tmp_path,
        answer_image=b"A" * 21 + suffix,
    )
    different_prefix = base64.b64encode(b"B" * 21 + suffix).decode("ascii")

    assert judge.judge("expected", different_prefix, PROBLEM_ID) != "1"
