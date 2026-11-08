"""各メモの最初の見出しの解法、誤答とfile境界をrootless sandboxで検査する。"""

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
PROBLEM_ID = "STANDARD-00000072"
ALTERNATIVE = 'while IFS= read -r f || [ -n "$f" ]; do awk \'/^# / {print FILENAME ":" $0; exit}\' "$f"; done < input.txt'
CASES = [
    ("empty", ""),
    ("single", "notes/gamma.txt\n"),
    ("space_path", "notes/alpha memo.txt\n"),
    ("duplicate", "notes/beta.txt\nnotes/beta.txt\n"),
    ("reordered", "notes/gamma.txt\nnotes/beta.txt\n"),
    ("no_final_lf", "notes/beta.txt"),
    ("same_heading_different_paths", "notes/beta.txt\nnotes/delta.txt\n"),
]


def test_first_heading_solutions_mistakes_and_boundaries_in_real_sandboxes() -> None:
    """公開2解法・7誤答と7境界を検査し、fileごとの打切り・行頭条件・順序・重複を区別する。"""
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(PROBLEM_ID)
    reference = record.definition.reference_solution
    contents = {
        fixture.path: fixture.content
        for fixture in record.definition.execution.fixtures
    }
    manager = ContainerManager(
        pool_size=1, owner_id=f"soj-first-heading-{uuid.uuid4().hex}"
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
        """入力の差し替えもsandbox内で行い、raw出力・実行policy・judgeを一緒に確認する。"""
        prefix = (
            "" if fixture is None else f"printf %s {shlex.quote(fixture)} > input.txt; "
        )
        command = prefix + solution
        assert len(command) <= 1000
        execution = asyncio.run(client.run_with_timeout(command, PROBLEM_ID))
        context = (label, execution)
        assert execution.status is ExecutionStatus.COMPLETED, context
        assert execution.exit_code == 0 and execution.stderr == "", context
        assert not execution.timed_out and not execution.truncated, context
        verdict = (
            judge.judge(execution, PROBLEM_ID).verdict
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
        for index, solution in enumerate((reference, ALTERNATIVE)):
            evaluate(f"public-{index}", solution, record.expected_output)
        mistakes = [
            ("all_matches", reference.replace("-m1 ", "")),
            ("global_first", reference.replace("-m1 ", "") + " | head -n1"),
            ("not_anchored", reference.replace("^# ", "# ")),
            ("wrong_marker", reference.replace("^# ", "^#")),
            ("no_path", reference.replace("-H", "-h")),
            ("sort_unique", reference + " | sort -u"),
            ("glob", "grep -H -m1 -- '^# ' notes/*"),
        ]
        for label, solution in mistakes:
            evaluate(label, solution, record.expected_output, accepted=False)
        for label, fixture in CASES:
            expected = "".join(
                f"{path}:"
                + next(
                    line
                    for line in contents[path].splitlines()
                    if line.startswith("# ")
                )
                + "\n"
                for path in fixture.splitlines()
            )
            for index, solution in enumerate((reference, ALTERNATIVE)):
                evaluate(f"{label}-{index}", solution, expected, fixture)
    finally:
        try:
            manager.shutdown_pool()
        finally:
            client.close()
