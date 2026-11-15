"""lnの回答例・別解・誤答・境界条件とrequest間のfile分離を実sandboxで確認する。"""

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
from tests.test_ln_problem import (
    ALTERNATIVE,
    CASES,
    PROBLEM_ID,
    expected_link_trace,
)

pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(
        os.getenv("SOJ_RUN_DOCKER_TESTS") != "1",
        reason="解答の実行にはrootless Dockerへの明示指定が必要",
    ),
]
PROBLEMS = Path(__file__).resolve().parents[3] / "problems"


def test_ln_solutions_mistakes_boundaries_and_request_isolation() -> None:
    """2解法・3誤答・7境界と、実inode共有・request間の本文/別名分離を検査する。"""
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(PROBLEM_ID)
    judge = ShellgeiJudge(repository)
    reference = record.definition.reference_solution
    manager = ContainerManager(pool_size=1, owner_id=f"soj-ln-{uuid.uuid4().hex}")
    client = ShellgeiDockerClient(
        container_manager=manager, max_concurrent=1, problem_repository=repository
    )

    def evaluate(
        label: str, solution: str, original: str | None = None, accepted: bool = True
    ) -> None:
        """fixture差替えもsandbox内だけで行い、raw出力・policy・実judgeを独立期待値と照合する。"""
        prefix = (
            ""
            if original is None
            else f"printf %s {shlex.quote(original)} > input.txt; "
        )
        submitted = prefix + solution
        assert len(submitted) <= 1000
        execution = asyncio.run(client.run_with_timeout(submitted, PROBLEM_ID))
        context = (label, execution)
        assert execution.status is ExecutionStatus.COMPLETED, context
        assert execution.exit_code == 0 and execution.stderr == "", context
        assert not execution.timed_out and not execution.truncated, context
        expected = (
            record.expected_output
            if original is None
            else expected_link_trace(original)
        )
        verdict = (
            judge.judge(execution, PROBLEM_ID).verdict
            if original is None
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

    def check_fixture(command: str, expected: str) -> None:
        """監査用commandもsandboxで実行し、共有inodeまたは新規requestの初期状態を確認する。"""
        execution = asyncio.run(client.run_with_timeout(command, PROBLEM_ID))
        assert execution.status is ExecutionStatus.COMPLETED
        assert execution.exit_code == 0 and execution.stderr == ""
        assert execution.stdout == expected
        assert not execution.timed_out and not execution.truncated

    fresh = (
        "test ! -e shared.txt && test ! -L shared.txt "
        "&& cat input.txt && stat -c %h input.txt"
    )
    mistakes = [
        ("copy", reference.replace("ln input.txt", "cp input.txt", 1)),
        ("symlink", reference.replace("ln input.txt", "ln -s input.txt", 1)),
        ("overwrite", reference.replace(" >> ", " > ", 1)),
    ]
    try:
        manager.initialize_pool()
        check_fixture(
            "ln input.txt shared.txt && test input.txt -ef shared.txt "
            "&& test ! -L shared.txt && stat -c %h input.txt",
            "2\n",
        )
        check_fixture(fresh, CASES[0][1] + "1\n")
        for index, solution in enumerate((reference, ALTERNATIVE)):
            evaluate(f"public-{index}", solution)
        for label, solution in mistakes:
            assert solution != reference
            evaluate(label, solution, accepted=False)
        for label, original, expected in CASES[1:]:
            assert expected_link_trace(original) == expected
            for index, solution in enumerate((reference, ALTERNATIVE)):
                evaluate(f"{label}-{index}", solution, original)
        check_fixture(fresh, CASES[0][1] + "1\n")
    finally:
        try:
            manager.shutdown_pool()
        finally:
            client.close()
