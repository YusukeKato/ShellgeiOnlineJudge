"""通常69のグループ先頭による抽出・2回読みの別解と、最大値や同率の誤解を検査する。"""

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
PROBLEM_ID = "STANDARD-00000069"


def test_sales_leaders_solutions_and_common_mistakes_in_real_sandboxes() -> None:
    # 参照解と2回読みの別解を受理し、同率欠落・数値比較・全体最大値・並べ替えの誤りを拒否する。
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(PROBLEM_ID)
    reference = record.definition.reference_solution
    cases = [
        ("reference", reference, JudgeVerdict.ACCEPTED),
        (
            "two-pass",
            "awk 'NR==FNR {if(!($1 in m) || $3>m[$1]) m[$1]=$3; next} "
            "$3==m[$1]' input.txt input.txt | sort -k1,1 -k2,2",
            JudgeVerdict.ACCEPTED,
        ),
        (
            "lexicographic-sales",
            reference.replace("-k3,3nr", "-k3,3r"),
            JudgeVerdict.WRONG_ANSWER,
        ),
        (
            "drop-ties",
            "sort -k1,1 -k3,3nr -k2,2 input.txt | awk '!seen[$1]++'",
            JudgeVerdict.WRONG_ANSWER,
        ),
        (
            "no-group-sort",
            "awk '$1!=c {c=$1; m=$3} $3==m' input.txt",
            JudgeVerdict.WRONG_ANSWER,
        ),
        (
            "global-maximum",
            "awk 'NR==FNR {if($3>m)m=$3;next} $3==m' input.txt input.txt "
            "| sort -k1,1 -k2,2",
            JudgeVerdict.WRONG_ANSWER,
        ),
        (
            "reverse-product-order",
            reference.replace("-k2,2", "-k2,2r"),
            JudgeVerdict.WRONG_ANSWER,
        ),
    ]
    # 専用ownerのsandboxだけを作成・回収し、既存検証環境へ干渉しない。
    manager = ContainerManager(pool_size=1, owner_id=f"soj-sales-{uuid.uuid4().hex}")
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
