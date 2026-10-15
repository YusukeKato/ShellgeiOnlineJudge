"""pasteの直列結合とawk別解、空行・区切り・順序の取り違えを実sandboxで検証する。"""

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
PROBLEM_ID = "PRACTICE-paste-01"


def test_paste_solutions_and_common_mistakes_in_real_sandboxes() -> None:
    # 参照解・awk別解を受理し、空行の削除・圧縮、末尾区切り、整列などの6誤答を拒否する。
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(PROBLEM_ID)
    reference = record.definition.reference_solution
    cases = [
        ("reference", reference, JudgeVerdict.ACCEPTED),
        (
            "awk",
            'awk \'NR>1{printf ","} {printf "%s",$0} END{print ""}\' input.txt',
            JudgeVerdict.ACCEPTED,
        ),
        ("missing-serial", "paste -d ',' input.txt", JudgeVerdict.WRONG_ANSWER),
        (
            "dropped-empty",
            "grep . input.txt | paste -s -d ','",
            JudgeVerdict.WRONG_ANSWER,
        ),
        (
            "collapsed-empty",
            "cat -s input.txt | paste -s -d ','",
            JudgeVerdict.WRONG_ANSWER,
        ),
        ("trailing-comma", "tr '\\n' ',' < input.txt", JudgeVerdict.WRONG_ANSWER),
        ("tab-delimiter", "paste -s input.txt", JudgeVerdict.WRONG_ANSWER),
        (
            "sorted-dedup",
            "sort -u input.txt | paste -s -d ','",
            JudgeVerdict.WRONG_ANSWER,
        ),
    ]
    manager = ContainerManager(pool_size=1, owner_id=f"soj-paste-{uuid.uuid4().hex}")
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
