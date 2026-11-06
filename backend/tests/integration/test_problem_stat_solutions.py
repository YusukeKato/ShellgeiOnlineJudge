"""statとwcの解法、文字数等の誤答とpath一覧の境界をrootless sandboxで検査する。"""

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
PROBLEM_ID = "PRACTICE-stat-01"
ALTERNATIVE = 'while IFS= read -r p || [ -n "$p" ]; do printf \'%s %s\\n\' "$p" "$(wc -c < "$p")"; done < input.txt'
CASES = [
    ("empty", ""),
    ("single", "data/short.txt\n"),
    ("space_path", "data/two lines.txt\n"),
    ("unicode", "data/japanese.txt\n"),
    ("no_final_lf", "data/message.txt"),
    ("duplicate", "data/short.txt\ndata/short.txt\n"),
    ("reordered", "data/message.txt\ndata/japanese.txt\ndata/short.txt\n"),
]


def test_stat_solutions_mistakes_and_boundaries_in_real_sandboxes() -> None:
    """公開2解法・4誤答と7境界を検査し、UTF-8 byte数・LF・順序・重複・名前内spaceを区別する。"""
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(PROBLEM_ID)
    reference = record.definition.reference_solution
    contents = {
        fixture.path: fixture.content
        for fixture in record.definition.execution.fixtures
    }
    manager = ContainerManager(pool_size=1, owner_id=f"soj-stat-{uuid.uuid4().hex}")
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
            ("characters", ALTERNATIVE.replace("wc -c", "wc -m")),
            ("lines", ALTERNATIVE.replace("wc -c", "wc -l")),
            ("sort", reference + " | sort"),
            ("glob", "stat --format='%n %s' -- data/*"),
        ]
        for label, solution in mistakes:
            evaluate(label, solution, record.expected_output, accepted=False)
        for label, fixture in CASES:
            expected = "".join(
                f"{path} {len(contents[path].encode('utf-8'))}\n"
                for path in fixture.splitlines()
            )
            for index, solution in enumerate((reference, ALTERNATIVE)):
                evaluate(f"{label}-{index}", solution, expected, fixture)
    finally:
        try:
            manager.shutdown_pool()
        finally:
            client.close()
