import asyncio
import os
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
        reason="explicit isolated-host opt-in is required",
    ),
]

PROBLEMS = Path(__file__).resolve().parents[3] / "problems"
PROBLEM_ID = "STANDARD-00000052"
RESERVED = "sed -n 's/^reserved //p' input.txt"
ARRIVED = "sed -n 's/^arrived //p' input.txt"


def test_reservation_solutions_and_common_mistakes_in_real_sandboxes() -> None:
    # 参照解答・別解を受理し、逆の差・重複残存・部分一致による除外を実sandboxで区別する。
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    cases = [
        (repository.require(PROBLEM_ID).definition.reference_solution, True),
        (
            'awk \'$1=="arrived"{a[$2]=1} $1=="reserved"{r[$2]=1} '
            "END{for(n in r)if(!(n in a))print n}' input.txt | LC_ALL=C sort",
            True,
        ),
        (f"grep -Fxv -f <({ARRIVED}) <({RESERVED} | LC_ALL=C sort -u)", True),
        (
            f"export LC_ALL=C; comm -13 <({RESERVED} | sort -u) <({ARRIVED} | sort -u)",
            False,
        ),
        (
            f"export LC_ALL=C; comm -23 <({RESERVED} | sort) <({ARRIVED} | sort -u)",
            False,
        ),
        (f"grep -Fv -f <({ARRIVED}) <({RESERVED} | LC_ALL=C sort -u)", False),
    ]
    manager = ContainerManager(pool_size=1)
    client = ShellgeiDockerClient(
        container_manager=manager,
        max_concurrent=1,
        problem_repository=repository,
    )
    judge = ShellgeiJudge(repository)
    try:
        manager.initialize_pool()
        for command, accepted in cases:
            execution = asyncio.run(client.run_with_timeout(command, PROBLEM_ID))
            assert execution.status is ExecutionStatus.COMPLETED, command
            assert execution.exit_code == 0, command
            assert execution.stderr == "", command
            expected = JudgeVerdict.ACCEPTED if accepted else JudgeVerdict.WRONG_ANSWER
            assert judge.judge(execution, PROBLEM_ID).verdict is expected, command
    finally:
        manager.shutdown_pool()
        client.close()
