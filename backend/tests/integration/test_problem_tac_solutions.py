"""tacの区切り指定、別解、誤答と境界条件をrootless sandboxで検証する。"""

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
PROBLEM_ID = "PRACTICE-tac-01"


def test_tac_solutions_mistakes_and_boundaries_in_real_sandboxes() -> None:
    """記録順だけの逆転を受理し、行反転・文字反転・区切りの誤指定を区別する。"""
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(PROBLEM_ID)
    reference = record.definition.reference_solution
    alternative = (
        """awk '{r=r $0 ORS} $0=="END"{a[++n]=r;r=""} """
        """END{for(i=n;i>0;i--)printf "%s",a[i]}' input.txt"""
    )
    cases = [
        ("reference", reference, JudgeVerdict.ACCEPTED),
        ("awk_alternative", alternative, JudgeVerdict.ACCEPTED),
        ("unchanged", "cat input.txt", JudgeVerdict.WRONG_ANSWER),
        ("reverse_lines", "tac input.txt", JudgeVerdict.WRONG_ANSWER),
        ("reverse_characters", "rev input.txt", JudgeVerdict.WRONG_ANSWER),
        (
            "separator_before",
            r"tac -b -s $'\nEND\n' input.txt",
            JudgeVerdict.WRONG_ANSWER,
        ),
        (
            "literal_backslash_n",
            r"tac -s '\nEND\n' input.txt",
            JudgeVerdict.WRONG_ANSWER,
        ),
    ]
    manager = ContainerManager(pool_size=1, owner_id=f"soj-tac-{uuid.uuid4().hex}")
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
            assert execution.exit_code == 0 and execution.stderr == "", context
            assert judge.judge(execution, PROBLEM_ID).verdict is verdict, context
            if verdict is JudgeVerdict.ACCEPTED:
                assert execution.stdout == record.expected_output, context
        alpha = "job alpha\nstatus ready\nEND\n"
        beta = "job beta\nEND\n"
        gamma = "job gamma\nstatus running\nnote retry later\nEND\n"
        boundaries = [
            ("", ""),
            (alpha, alpha),
            (beta + gamma, gamma + beta),
            (
                "job a\n\n  two  spaces\nEND\n" + beta,
                beta + "job a\n\n  two  spaces\nEND\n",
            ),
            (
                "job a\nmessage END\nFRIEND\nEND\n" + beta,
                beta + "job a\nmessage END\nFRIEND\nEND\n",
            ),
            (alpha + beta + alpha + gamma, gamma + alpha + beta + alpha),
        ]
        for fixture, expected in boundaries:
            for solution in (reference, alternative):
                command = f"printf %s {shlex.quote(fixture)} > input.txt; {solution}"
                execution = asyncio.run(client.run_with_timeout(command, PROBLEM_ID))
                context = (fixture, solution, execution)
                assert execution.status is ExecutionStatus.COMPLETED, context
                assert execution.exit_code == 0 and execution.stderr == "", context
                assert execution.stdout == expected, context
    finally:
        try:
            manager.shutdown_pool()
        finally:
            client.close()
