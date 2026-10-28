"""承認済みの転置・byte抽出を実sandboxと現行judgeで検査する。"""

import asyncio
import os
from pathlib import Path
import shlex
import uuid

import pytest

from soj_backend.judge import JudgeVerdict, ShellgeiJudge, TextJudgeInput, judge_text
from soj_runner.container_manager import ContainerManager
from soj_runner.run_shellgei import ShellgeiDockerClient
from soj_shared.models.execution import ExecutionStatus
from soj_shared.models.problem import TextJudgeSpecification
from soj_shared.problem_repository import build_problem_repository

pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(
        os.getenv("SOJ_RUN_DOCKER_TESTS") != "1",
        reason="解答の実行にはrootless Dockerへの明示指定が必要",
    ),
]
PROBLEMS = Path(__file__).resolve().parents[3] / "problems"

ALTERNATIVES = {
    "PRACTICE-rs-01": "awk '{for(c=1;c<=NF;c++)a[c,NR]=$c;cols=NF} "
    "END{for(c=1;c<=cols;c++){for(r=1;r<=NR;r++)printf "
    '"%s%s",(r==1?"":" "),a[c,r];print ""}}\' input.txt',
    "STANDARD-00000070": "bytes=$(head -n1 input.txt); tail -n +2 input.txt | head -c "
    '"$bytes"',
}

BOUNDARIES = {
    "PRACTICE-rs-01": [
        ("empty", ""),
        ("single", "one\n"),
        ("one_row", "a 12 -3 12\n"),
        ("one_column", "north\nsouth\nnorth\n"),
        ("square", "a b\nc d\n"),
        ("wide", "a b c d\ne f g h\n"),
        ("duplicates", "x x y\nx y y\n"),
        ("no_final_lf", "a b\nc d"),
        ("multiple_spaces", "a   bb c\nd ee   f\n"),
    ],
    "STANDARD-00000070": [
        ("zero", "0\nignored\n"),
        ("ascii_one", "1\nabc\n"),
        ("within_line", "4\nabcdef\n"),
        ("blank_inside", "4\nA\n\nBtail\n"),
        ("spaces", "6\n a  b!tail\n"),
        ("japanese", "3\n猫tail\n"),
        ("two_byte", "2\nétail\n"),
        ("four_byte", "4\n🐚tail\n"),
        ("at_eof_without_lf", "5\nhello"),
        ("two_digit_length", "12\nhello world!tail\n"),
        ("duplicates", "6\nx\nx\nx\nIGNORE\n"),
        ("line_feed_count", "2\nA\nTAIL\n"),
    ],
}

MISTAKES = {
    "PRACTICE-rs-01": [
        ("unchanged", "cat input.txt"),
        ("reverse_rows", "tac input.txt | rs -T -C' ' | sed 's/ $//'"),
        ("flatten", "tr '\\n' ' ' < input.txt; printf '\\n'"),
        ("numeric_only", "tail -n +2 input.txt | rs -T -C' ' | sed 's/ $//'"),
        ("sort_rows", "sort input.txt | rs -T -C' ' | sed 's/ $//'"),
        ("padded", "rs -T < input.txt"),
    ],
    "STANDARD-00000070": [
        ("unchanged", "cat input.txt"),
        ("all_remaining", "tail -n +2 input.txt"),
        ("count_lines", '{ IFS= read -r bytes; head -n "$bytes"; } < input.txt'),
        (
            "count_characters",
            '{ IFS= read -r bytes; IFS= read -r -N "$bytes" text; printf '
            '%s "$text"; } < input.txt',
        ),
        ("one_less", '{ IFS= read -r bytes; head -c "$((bytes-1))"; } < input.txt'),
        ("one_more", '{ IFS= read -r bytes; head -c "$((bytes+1))"; } < input.txt'),
        ("include_header", "head -c 15 input.txt"),
    ],
}


def _independent_expected(problem_id: str, fixture: str) -> str:
    """転置は列添字、本文はUTF-8 byte配列から、shellコマンドと独立に期待値を求める。"""
    if problem_id == "PRACTICE-rs-01":
        rows = [line.split() for line in fixture.splitlines()]
        if not rows:
            return ""
        assert all(len(row) == len(rows[0]) for row in rows)
        return "".join(
            " ".join(row[column] for row in rows) + "\n"
            for column in range(len(rows[0]))
        )
    header, body = fixture.encode().split(b"\n", 1)
    count = int(header)
    assert 0 <= count <= len(body)
    return body[:count].decode()


@pytest.mark.parametrize("problem_id", tuple(ALTERNATIVES))
def test_rs_and_length_prefix_solutions_in_real_sandboxes(problem_id: str) -> None:
    """公開入力の2正解・誤答と境界fixtureを検査し、rsのtab区切り非対応も区別する。"""
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(problem_id)
    manager = ContainerManager(pool_size=1, owner_id=f"soj-rs-byte-{uuid.uuid4().hex}")
    client = ShellgeiDockerClient(
        container_manager=manager, max_concurrent=1, problem_repository=repository
    )
    judge = ShellgeiJudge(repository)
    solutions = (record.definition.reference_solution, ALTERNATIVES[problem_id])

    def evaluate(
        label: str,
        fixture: str | None,
        command: str,
        expected: str,
        accepted: bool = True,
    ) -> None:
        """公開入力またはsandbox内の試験入力を実行し、raw出力と実judgeの両方を照合する。"""
        submitted = (
            command
            if fixture is None
            else f"printf %s {shlex.quote(fixture)} > input.txt; {command}"
        )
        assert len(submitted) <= 1000
        execution = asyncio.run(client.run_with_timeout(submitted, problem_id))
        context = (problem_id, label, execution)
        assert execution.status is ExecutionStatus.COMPLETED, context
        assert execution.exit_code == 0 and execution.stderr == "", context
        assert not execution.timed_out and not execution.truncated, context
        if fixture is None:
            verdict = judge.judge(execution, problem_id).verdict
        else:
            verdict = judge_text(
                TextJudgeSpecification(type="text", expected_output=expected),
                record.definition.execution,
                TextJudgeInput(
                    stdout=execution.stdout,
                    stderr=execution.stderr,
                    exit_code=execution.exit_code,
                    timed_out=execution.timed_out,
                    truncated=execution.truncated,
                ),
            ).verdict
        assert verdict is (
            JudgeVerdict.ACCEPTED if accepted else JudgeVerdict.WRONG_ANSWER
        ), context
        if accepted:
            assert execution.stdout == expected, context

    try:
        manager.initialize_pool()
        for index, solution in enumerate(solutions):
            evaluate(f"public-{index}", None, solution, record.expected_output)
        for label, command in MISTAKES[problem_id]:
            evaluate(label, None, command, record.expected_output, False)
        for label, fixture in BOUNDARIES[problem_id]:
            expected = _independent_expected(problem_id, fixture)
            for index, solution in enumerate(solutions):
                evaluate(f"{label}-{index}", fixture, solution, expected)
        if problem_id == "PRACTICE-rs-01":
            fixture = "a\tbb   c\nd  ee\tf\n"
            expected = _independent_expected(problem_id, fixture)
            evaluate("tab-outside-rs-scope", fixture, solutions[0], expected, False)
            evaluate("awk-tab-separator", fixture, solutions[1], expected)
    finally:
        try:
            manager.shutdown_pool()
        finally:
            client.close()
