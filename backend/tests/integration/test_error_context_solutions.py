"""エラー前後の抽出で、自然な別解と文脈・境界の誤解を実sandboxで区別する。"""

import asyncio
import os
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
        reason="explicit isolated-host opt-in is required",
    ),
]
PROBLEMS = Path(__file__).resolve().parents[3] / "problems"
PROBLEM_ID = "STANDARD-00000061"


def test_error_context_solutions_and_common_mistakes_in_real_sandboxes() -> None:
    # 参照解・行番号集合の別解を受理し、文脈・境界・重複の扱いを取り違えた誤答を拒否する。
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    cases = [
        (repository.require(PROBLEM_ID).definition.reference_solution, True),
        (
            "awk '{line[NR]=$0;if($0~/^ERROR /)"
            "keep[NR-1]=keep[NR]=keep[NR+1]=1} "
            "END{for(i=1;i<=NR;i++)if(keep[i])print line[i]}' input.txt",
            True,
        ),
        ("grep '^ERROR ' input.txt", False),
        ("grep -C 1 '^ERROR ' input.txt", False),
        ("grep -C 1 --no-group-separator 'ERROR' input.txt", False),
        ("grep -C 1 --no-group-separator '^ERROR' input.txt", False),
        (
            repository.require(PROBLEM_ID).definition.reference_solution
            + " | awk '!seen[$0]++'",
            False,
        ),
        (
            "awk '{line[NR]=$0} END{for(i=1;i<=NR;i++)if(line[i]~/^ERROR /)"
            "for(j=i-1;j<=i+1;j++)if(j>=1&&j<=NR)print line[j]}' input.txt",
            False,
        ),
    ]
    # 並行したテストのsandboxを回収しないよう、今回だけのownerを付ける。
    manager = ContainerManager(
        pool_size=1, owner_id=f"soj-error-context-{uuid.uuid4().hex}"
    )
    client = ShellgeiDockerClient(
        container_manager=manager, max_concurrent=1, problem_repository=repository
    )
    judge = ShellgeiJudge(repository)
    try:
        manager.initialize_pool()
        for command, accepted in cases:
            execution = asyncio.run(client.run_with_timeout(command, PROBLEM_ID))
            context = (command, execution)
            assert execution.status is ExecutionStatus.COMPLETED, context
            assert execution.exit_code == 0, context
            assert execution.stderr == "", context
            expected = JudgeVerdict.ACCEPTED if accepted else JudgeVerdict.WRONG_ANSWER
            assert judge.judge(execution, PROBLEM_ID).verdict is expected, context
    finally:
        manager.shutdown_pool()
        client.close()
