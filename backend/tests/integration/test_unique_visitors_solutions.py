"""通常68の参照解・配列による別解と、集計単位や抽出順の誤りを実sandboxで検査する。"""

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
PROBLEM_ID = "STANDARD-00000068"


def test_unique_visitors_solutions_and_common_mistakes_in_real_sandboxes() -> None:
    # 参照解・組をキーにした配列別解を受理し、回数・全行・全体での重複除去や同率逆順を拒否する。
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(PROBLEM_ID)
    reference = record.definition.reference_solution
    aggregate = " | sort | uniq -c | sort -k1,1nr -k2,2 | awk '{print $2,$1}'"
    cases = [
        ("reference", reference, JudgeVerdict.ACCEPTED),
        (
            "associative-array",
            "awk '$4==200 && !seen[$3,$2]++ {n[$3]++} "
            "END {for(p in n) print p,n[p]}' input.txt | sort -k2,2nr -k1,1",
            JudgeVerdict.ACCEPTED,
        ),
        (
            "count-requests",
            "awk '$4==200 {print $3}' input.txt" + aggregate,
            JudgeVerdict.WRONG_ANSWER,
        ),
        (
            "include-failures",
            reference.replace("$4==200 ", ""),
            JudgeVerdict.WRONG_ANSWER,
        ),
        (
            "deduplicate-visitors-globally",
            "awk '$4==200 && !seen[$2]++ {n[$3]++} "
            "END {for(p in n) print p,n[p]}' input.txt | sort -k2,2nr -k1,1",
            JudgeVerdict.WRONG_ANSWER,
        ),
        (
            "deduplicate-timestamped-rows",
            "awk '$4==200' input.txt | sort -u | awk '{print $3}'" + aggregate,
            JudgeVerdict.WRONG_ANSWER,
        ),
        (
            "adjacent-pairs-only",
            reference.replace("sort -u", "uniq"),
            JudgeVerdict.WRONG_ANSWER,
        ),
        (
            "reverse-ties",
            reference.replace("sort -k1,1nr -k2,2", "sort -k1,1nr -k2,2r"),
            JudgeVerdict.WRONG_ANSWER,
        ),
    ]
    # 専用ownerに属するsandboxだけを回収し、他の検証環境へ干渉しない。
    manager = ContainerManager(pool_size=1, owner_id=f"soj-visitors-{uuid.uuid4().hex}")
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
