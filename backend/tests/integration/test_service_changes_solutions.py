"""commの両方向差分と配列別解、集合・向き・順序の取り違えを実sandboxで検証する。"""

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
PROBLEM_ID = "STANDARD-00000064"


def test_service_changes_solutions_and_common_mistakes_in_real_sandboxes() -> None:
    # 参照解・配列別解を受理し、片方向・重複・部分一致・ラベル順・逆転の6誤答を拒否する。
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(PROBLEM_ID)
    reference = record.definition.reference_solution
    before = "<(sed -n 's/^before //p' input.txt | sort -u)"
    after = "<(sed -n 's/^after //p' input.txt | sort -u)"
    cases = [
        ("reference", reference, JudgeVerdict.ACCEPTED),
        (
            "arrays",
            'awk \'$1=="before"{b[$2]=1} $1=="after"{a[$2]=1} END {for(n in b) if(!(n in a)) print "REMOVE",n; for(n in a) if(!(n in b)) print "ADD",n}\' input.txt | sort -k2,2',
            JudgeVerdict.ACCEPTED,
        ),
        (
            "only-removed",
            f"comm -23 {before} {after} | sed 's/^/REMOVE /'",
            JudgeVerdict.WRONG_ANSWER,
        ),
        (
            "only-added",
            f"comm -13 {before} {after} | sed 's/^/ADD /'",
            JudgeVerdict.WRONG_ANSWER,
        ),
        ("multiset", reference.replace("sort -u", "sort"), JudgeVerdict.WRONG_ANSWER),
        ("label-order", reference + " | sort", JudgeVerdict.WRONG_ANSWER),
        (
            "reversed",
            reference.replace('"ADD"', '"REMOVED"')
            .replace('"REMOVE"', '"ADD"')
            .replace('"REMOVED"', '"REMOVE"'),
            JudgeVerdict.WRONG_ANSWER,
        ),
        (
            "partial-name",
            f"{{ grep -v -f {after} {before} | sed 's/^/REMOVE /'; "
            f"grep -v -f {before} {after} | sed 's/^/ADD /'; }} | sort -k2,2",
            JudgeVerdict.WRONG_ANSWER,
        ),
    ]
    manager = ContainerManager(pool_size=1, owner_id=f"soj-services-{uuid.uuid4().hex}")
    client = ShellgeiDockerClient(
        container_manager=manager, max_concurrent=1, problem_repository=repository
    )
    judge = ShellgeiJudge(repository)
    try:
        manager.initialize_pool()
        for case_name, command, verdict in cases:
            execution = asyncio.run(client.run_with_timeout(command, PROBLEM_ID))
            context = (case_name, command, execution)
            assert execution.status is ExecutionStatus.COMPLETED, context
            assert execution.exit_code == 0, context
            assert execution.stderr == "", context
            assert judge.judge(execution, PROBLEM_ID).verdict is verdict, context
            if verdict is JudgeVerdict.ACCEPTED:
                assert execution.stdout == record.expected_output, context
    finally:
        try:
            manager.shutdown_pool()
        finally:
            client.close()
