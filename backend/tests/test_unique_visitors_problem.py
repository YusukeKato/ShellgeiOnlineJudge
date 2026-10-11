"""訪問者数の期待値をページ別の集合から独立に確認し、表示・判定の契約を検査する。"""

from pathlib import Path

import pytest
from PIL import Image

from soj_backend.judge import JudgeVerdict, TextJudgeInput, judge_text
from soj_shared.problem_repository import build_problem_repository
from soj_shared.problem_schema import load_problem_definition


PROBLEMS = Path(__file__).resolve().parents[2] / "problems"
PROBLEM_ID = "STANDARD-00000068"
OUTPUT = "/tools 4\n/guide 3\n/news 3\n/status 1\n"


def test_unique_visitors_fixture_policy_and_preview() -> None:
    # input.txtが詳細APIで欠落せず、正常終了policyと白JPEGが現行画面に適合することを確認する。
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(PROBLEM_ID)
    definition = record.definition
    assert definition.category == "STANDARD"
    assert definition.judge.type == "text"
    assert definition.execution.stdin == ""
    assert definition.execution.exit_code == "zero"
    assert definition.execution.stderr == "must_be_empty"
    assert len(definition.execution.fixtures) == 1
    fixture = definition.execution.fixtures[0]
    assert fixture.path == "input.txt"
    assert len(fixture.content.splitlines()) == 18
    assert record.api_detail()["input"] == fixture.content
    assert record.api_detail()["expected_output"] == OUTPUT
    assert len(definition.reference_solution) <= 1000
    with Image.open(PROBLEMS / "image" / f"{PROBLEM_ID}.jpg") as image:
        image.load()
        assert image.format == "JPEG"
        assert image.convert("RGB").getextrema() == ((255, 255),) * 3


def test_unique_visitors_expected_output_from_independent_membership() -> None:
    # shellの参照解を使わず、各人に成功記録があるかを全行から調べて手確認した集合と照合する。
    definition = load_problem_definition(PROBLEMS / "v3" / f"{PROBLEM_ID}.yaml")
    records = [
        line.split() for line in definition.execution.fixtures[0].content.splitlines()
    ]
    pages = {record[2] for record in records}
    visitors = {record[1] for record in records}
    membership = {
        page: {
            visitor
            for visitor in visitors
            if any(row[1:] == [visitor, page, "200"] for row in records)
        }
        for page in pages
    }
    assert membership == {
        "/tools": {"u01", "u02", "u03", "u04"},
        "/guide": {"u01", "u02", "u03"},
        "/news": {"u01", "u04", "u05"},
        "/status": {"u06"},
        "/hidden": set(),
    }
    ranking = sorted(
        ((page, len(people)) for page, people in membership.items() if people),
        key=lambda item: (-item[1], item[0]),
    )
    expected = "".join(f"{page} {count}\n" for page, count in ranking)
    assert definition.judge.type == "text"
    assert definition.judge.expected_output == expected == OUTPUT
    # 時刻付きの全行は一意でも、成功アクセス14件の中に再訪があり、組は11件だけになる。
    assert len({tuple(row) for row in records}) == 18
    assert sum(row[3] == "200" for row in records) == 14
    assert sum(map(len, membership.values())) == 11


@pytest.mark.parametrize(
    "execution,verdict",
    [
        (TextJudgeInput(stdout=OUTPUT), JudgeVerdict.ACCEPTED),
        (TextJudgeInput(stdout=OUTPUT.rstrip("\n")), JudgeVerdict.ACCEPTED),
        (
            TextJudgeInput(stdout="/tools 5\n/guide 4\n/news 3\n/status 2\n"),
            JudgeVerdict.WRONG_ANSWER,
        ),
        (
            TextJudgeInput(
                stdout="/guide 4\n/tools 4\n/news 3\n/hidden 1\n/status 1\n"
            ),
            JudgeVerdict.WRONG_ANSWER,
        ),
        (
            TextJudgeInput(stdout="/tools 4\n/news 3\n/guide 3\n/status 1\n"),
            JudgeVerdict.WRONG_ANSWER,
        ),
        (TextJudgeInput(stdout=OUTPUT + "/hidden 0\n"), JudgeVerdict.WRONG_ANSWER),
        (TextJudgeInput(stdout=OUTPUT, exit_code=1), JudgeVerdict.EXECUTION_FAILURE),
        (
            TextJudgeInput(stdout=OUTPUT, stderr="warning\n"),
            JudgeVerdict.EXECUTION_FAILURE,
        ),
    ],
)
def test_unique_visitors_judge_counts_order_and_clean_execution(
    execution: TextJudgeInput, verdict: JudgeVerdict
) -> None:
    # 再訪の加算・失敗の混入・同率の逆順・0人ページの出力と、非0終了・stderrを拒否する。
    definition = load_problem_definition(PROBLEMS / "v3" / f"{PROBLEM_ID}.yaml")
    assert definition.judge.type == "text"
    assert (
        judge_text(definition.judge, definition.execution, execution).verdict is verdict
    )
