"""通常62・63の参照解・自然な別解と、順序や表記を誤る解答を実sandboxで区別する。"""

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
        reason="実sandbox実行にはSOJ_RUN_DOCKER_TESTS=1の明示指定が必要",
    ),
]
PROBLEMS = Path(__file__).resolve().parents[3] / "problems"
CASES = [
    (
        62,
        "sort -t. -k1.2,1n -k2,2n -k3,3n input.txt",
        (
            "sort input.txt",
            "sort -n input.txt",
            "sort -Vr input.txt",
            "sort -V input.txt | sed 's/^v//'",
        ),
    ),
    (
        63,
        "awk '{nodes[$1]=nodes[$2]=1;from[NR]=$1;to[NR]=$2;indegree[$2]++} "
        'END{for(step=1;step<=length(nodes);step++){ready="";'
        "for(node in nodes)if(!done[node]&&!indegree[node]){ready=node;break}"
        'if(ready=="")exit 1;print ready;done[ready]=1;'
        "for(i=1;i<=NR;i++)if(from[i]==ready)indegree[to[i]]--}}' input.txt",
        (
            "tr ' ' '\\n' < input.txt | sort -u",
            "awk '{for(i=1;i<=NF;i++)if(!seen[$i]++)print $i}' input.txt",
            "awk '{print $1}' input.txt | sort -u",
            "awk '{print $2,$1}' input.txt | tsort",
        ),
    ),
]


@pytest.mark.parametrize(
    ("number", "alternative", "mistakes"), CASES, ids=["version-order", "task-order"]
)
def test_ordering_solutions_and_common_mistakes_in_real_sandboxes(
    number: int, alternative: str, mistakes: tuple[str, ...]
) -> None:
    # 各問の参照解・別解を受理し、順序や元の表記を取り違えた4誤答を拒否する。
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    problem_id = f"STANDARD-{number:08}"
    reference = repository.require(problem_id).definition.reference_solution
    cases = [(reference, True), (alternative, True)]
    cases.extend((mistake, False) for mistake in mistakes)
    # 並行テストのsandboxを回収しないよう、この問題の実行だけにownerを割り当てる。
    manager = ContainerManager(
        pool_size=1, owner_id=f"soj-ordering-{number}-{uuid.uuid4().hex}"
    )
    client = ShellgeiDockerClient(
        container_manager=manager, max_concurrent=1, problem_repository=repository
    )
    judge = ShellgeiJudge(repository)
    try:
        manager.initialize_pool()
        for command, accepted in cases:
            execution = asyncio.run(client.run_with_timeout(command, problem_id))
            context = (problem_id, command, execution)
            assert execution.status is ExecutionStatus.COMPLETED, context
            assert execution.exit_code == 0, context
            assert execution.stderr == "", context
            expected = JudgeVerdict.ACCEPTED if accepted else JudgeVerdict.WRONG_ANSWER
            assert judge.judge(execution, problem_id).verdict is expected, context
    finally:
        try:
            manager.shutdown_pool()
        finally:
            client.close()
