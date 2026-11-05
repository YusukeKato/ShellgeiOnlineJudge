"""巡回配分とBash引数表記の参照解・別解・誤答・境界をrootless sandboxで検査する。"""

import asyncio
import os
from pathlib import Path
import shlex
import string
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
IDS = ("PRACTICE-split-01", "PRACTICE-printf-02")
ALTERNATIVES = {
    "PRACTICE-split-01": "awk '{part[(NR-1)%3]=part[(NR-1)%3] $0 ORS} END{for(i=0;i<3;i++)printf \"[part_%d]\\n%s\",i,part[i]}' input.txt",
    "PRACTICE-printf-02": 'mapfile -t values < input.txt; for value in "${values[@]}"; do printf \'%q\\n\' "$value"; done',
}
CASES = {
    "PRACTICE-split-01": [
        ("empty", ""),
        ("one", "one\n"),
        ("two", "one\ntwo\n"),
        ("exact_three", "one\ntwo\nthree\n"),
        ("exact_six", "a\nb\nc\nd\ne\nf\n"),
        ("all_blank", "\n\n\n\n"),
        ("spacing_unicode", "  猫と犬\nfirst\\path\n  # keep\n猫と犬\n"),
        ("duplicate_lines", "same\nsame\nsame\nsame\n"),
    ],
    "PRACTICE-printf-02": [
        ("empty", ""),
        ("blank_line", "\n"),
        ("one", "simple.txt\n"),
        ("spaces_only", "  \n"),
        ("edge_spaces", " leading and trailing \n"),
        ("literal_percent", "%s.txt\n100%.txt\n"),
        ("backslashes", "dir\\file\\last\n"),
        ("quotes", "\"quoted\"\n'quoted'\n"),
        ("metacharacters", "a;b|c&d(e)\n"),
        ("unicode", "猫と犬\n日本語 ファイル.txt\n"),
    ],
}
MISTAKES = {
    "PRACTICE-split-01": [
        (
            "contiguous_three_lines",
            'split -l 3 -d -a 1 input.txt part_; for f in part_[0-2]; do printf \'[%s]\\n\' "$f"; cat "$f"; done',
        ),
        (
            "contiguous_three_files",
            'split -n l/3 -d -a 1 input.txt part_; for f in part_[0-2]; do printf \'[%s]\\n\' "$f"; cat "$f"; done',
        ),
        (
            "omit_empty",
            'grep . input.txt > cleaned.txt; split -n r/3 -d -a 1 cleaned.txt part_; for f in part_[0-2]; do printf \'[%s]\\n\' "$f"; cat "$f"; done',
        ),
        (
            "deduplicate",
            'sort -u input.txt > cleaned.txt; split -n r/3 -d -a 1 cleaned.txt part_; for f in part_[0-2]; do printf \'[%s]\\n\' "$f"; cat "$f"; done',
        ),
    ],
    "PRACTICE-printf-02": [
        ("no_quoting", "cat input.txt"),
        ("entire_file_as_one_argument", "printf '%q\\n' \"$(cat input.txt)\""),
        (
            "split_and_glob",
            "for value in $(cat input.txt); do printf '%q\\n' \"$value\"; done",
        ),
        (
            "trim_edge_spaces",
            "while read -r value; do printf '%q\\n' \"$value\"; done < input.txt",
        ),
    ],
}


def _expected(problem_id: str, fixture: str) -> str:
    """shellを実行せず、行番号の剰余または印字可能文字の引用規則から期待値を求める。"""
    assert not fixture or fixture.endswith("\n")
    lines = fixture[:-1].split("\n") if fixture else []
    if problem_id == IDS[0]:
        return "".join(
            f"[part_{lane}]\n" + "".join(line + "\n" for line in lines[lane::3])
            for lane in range(3)
        )
    assert problem_id == IDS[1]
    safe = set(string.ascii_letters + string.digits + "_@%+=:,./-")
    quoted = []
    for line in lines:
        assert all(char.isprintable() for char in line)
        quoted.append(
            "''"
            if not line
            else "".join(
                char if char in safe or not char.isascii() else "\\" + char
                for char in line
            )
        )
    return "".join(line + "\n" for line in quoted)


@pytest.mark.parametrize("problem_id", IDS)
def test_split_and_printf_solutions_mistakes_and_boundaries_in_real_sandboxes(
    problem_id: str,
) -> None:
    """公開の2解法・4誤答と境界を検証し、splitが生成したfileの次requestへの残存も拒否する。"""
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(problem_id)
    reference = record.definition.reference_solution
    alternative = ALTERNATIVES[problem_id]
    manager = ContainerManager(
        pool_size=1, owner_id=f"soj-split-printf-{uuid.uuid4().hex}"
    )
    client = ShellgeiDockerClient(
        container_manager=manager, max_concurrent=1, problem_repository=repository
    )
    judge = ShellgeiJudge(repository)

    def evaluate(
        label: str,
        solution: str,
        expected: str,
        fixture: str | None = None,
        accepted: bool = True,
    ) -> None:
        """境界入力の作成もsandbox内に限定し、raw出力と正常終了policy・judgeを照合する。"""
        prefix = (
            "" if fixture is None else f"printf %s {shlex.quote(fixture)} > input.txt; "
        )
        command = prefix + solution
        assert len(command) <= 1000
        execution = asyncio.run(client.run_with_timeout(command, problem_id))
        context = (label, execution)
        assert execution.status is ExecutionStatus.COMPLETED, context
        assert execution.exit_code == 0 and execution.stderr == "", context
        assert not execution.timed_out and not execution.truncated, context
        verdict = (
            judge.judge(execution, problem_id).verdict
            if fixture is None
            else judge_text(
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
        )
        assert verdict is (
            JudgeVerdict.ACCEPTED if accepted else JudgeVerdict.WRONG_ANSWER
        ), context
        if accepted:
            assert execution.stdout == expected, context

    try:
        manager.initialize_pool()
        for index, solution in enumerate((reference, alternative)):
            evaluate(f"public-{index}", solution, record.expected_output)
        for label, solution in MISTAKES[problem_id]:
            evaluate(label, solution, record.expected_output, accepted=False)
        for label, fixture in CASES[problem_id]:
            for index, solution in enumerate((reference, alternative)):
                evaluate(
                    f"{label}-{index}",
                    solution,
                    _expected(problem_id, fixture),
                    fixture,
                )
        if problem_id == IDS[0]:
            evaluate(
                "request_file_isolation",
                "test ! -e part_0 && test ! -e part_1 && test ! -e part_2 && printf 'isolated\\n'",
                "isolated\n",
                "",
            )
    finally:
        try:
            manager.shutdown_pool()
        finally:
            client.close()
