"""printf %bの復元、自然な別解、誤答と境界条件をrootless sandboxで検証する。"""

import asyncio
import os
import shlex
import uuid
from pathlib import Path

import pytest

from soj_backend.judge import JudgeVerdict, ShellgeiJudge
from soj_runner.container_manager import ContainerManager
from soj_runner.run_shellgei import ShellgeiDockerClient
from soj_shared.models.execution import ExecutionStatus
from soj_shared.problem_repository import build_problem_repository

pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(
        os.getenv("SOJ_RUN_DOCKER_TESTS") != "1",
        reason="解答の実行にはrootless Dockerへの明示指定が必要",
    ),
]
PROBLEMS = Path(__file__).resolve().parents[3] / "problems"
PROBLEM_ID = "PRACTICE-printf-01"


def test_printf_solutions_mistakes_and_boundaries_in_real_sandboxes() -> None:
    """1回の復元と書式・データの分離を受理し、未復元・再解釈・タブ破壊を区別する。"""
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(PROBLEM_ID)
    reference = record.definition.reference_solution
    alternative = """echo -ne "$(cat input.txt)" """
    cases = [
        ("reference", reference, JudgeVerdict.ACCEPTED),
        ("echo_alternative", alternative, JudgeVerdict.ACCEPTED),
        ("literal", "cat input.txt", JudgeVerdict.WRONG_ANSWER),
        ("percent_s", """printf '%s' "$(cat input.txt)" """, JudgeVerdict.WRONG_ANSWER),
        (
            "data_as_format",
            """printf "$(cat input.txt)" """,
            JudgeVerdict.EXECUTION_FAILURE,
        ),
        ("tabs_as_spaces", reference + r" | tr '\t' ' '", JudgeVerdict.WRONG_ANSWER),
        (
            "double_decode",
            """printf '%b' "$(printf '%b' "$(cat input.txt)")" """,
            JudgeVerdict.WRONG_ANSWER,
        ),
    ]
    manager = ContainerManager(pool_size=1, owner_id=f"soj-printf-{uuid.uuid4().hex}")
    client = ShellgeiDockerClient(
        container_manager=manager, max_concurrent=1, problem_repository=repository
    )
    judge = ShellgeiJudge(repository)
    try:
        manager.initialize_pool()
        for label, command, verdict in cases:
            execution = asyncio.run(client.run_with_timeout(command, PROBLEM_ID))
            context = (label, command, execution)
            assert execution.status is ExecutionStatus.COMPLETED, context
            assert judge.judge(execution, PROBLEM_ID).verdict is verdict, context
            if verdict is not JudgeVerdict.EXECUTION_FAILURE:
                assert execution.exit_code == 0 and execution.stderr == "", context
            else:
                assert execution.exit_code != 0 and execution.stderr, context
            if verdict is JudgeVerdict.ACCEPTED:
                assert execution.stdout == record.expected_output, context
        boundaries = [
            ("", ""),
            (r"row\t100%\n" + "\n", "row\t100%\n"),
            (r"a\n\nb\n" + "\n", "a\n\nb\n"),
            (r"row\t\\n\n" + "\n", "row\t\\n\n"),
            ("no final newline", "no final newline"),
            ("-n", "-n"),
        ]
        for fixture, expected in boundaries:
            # echo別解は固定公開入力向け。-nだけの入力はoptionと誤認するため一般化しない。
            solutions = (reference,) if fixture == "-n" else (reference, alternative)
            for solution in solutions:
                command = f"printf %s {shlex.quote(fixture)} > input.txt; {solution}"
                execution = asyncio.run(client.run_with_timeout(command, PROBLEM_ID))
                context = (fixture, solution, execution)
                assert execution.status is ExecutionStatus.COMPLETED, context
                assert execution.exit_code == 0 and execution.stderr == "", context
                assert execution.stdout == expected, context
        execution = asyncio.run(
            client.run_with_timeout(
                "printf %s '-n' > input.txt; " + alternative, PROBLEM_ID
            )
        )
        assert execution.status is ExecutionStatus.COMPLETED
        assert execution.exit_code == 0 and execution.stderr == ""
        assert execution.stdout != "-n"
    finally:
        try:
            manager.shutdown_pool()
        finally:
            client.close()
