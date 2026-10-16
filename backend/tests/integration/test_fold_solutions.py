"""foldの固定幅分割とawk別解、元の改行・残り・順序の取り違えを実sandboxで検証する。"""

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
        reason="実sandbox実行にはSOJ_RUN_DOCKER_TESTS=1の明示指定が必要",
    ),
]
PROBLEMS = Path(__file__).resolve().parents[3] / "problems"
PROBLEM_ID = "PRACTICE-fold-01"


def test_fold_solutions_and_common_mistakes_in_real_sandboxes() -> None:
    # 参照解・別解と境界条件を確認し、幅の誤り・連結・切り捨て・整列の6誤答を拒否する。
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(PROBLEM_ID)
    reference = record.definition.reference_solution
    alternative = (
        "awk 'NF==0{print;next} "
        "{for(i=1;i<=length($0);i+=8)print substr($0,i,8)}' input.txt"
    )
    cases = [
        ("reference", reference, JudgeVerdict.ACCEPTED),
        ("awk", alternative, JudgeVerdict.ACCEPTED),
        ("unchanged", "cat input.txt", JudgeVerdict.WRONG_ANSWER),
        ("width4", "fold -w4 input.txt", JudgeVerdict.WRONG_ANSWER),
        ("width9", "fold -w9 input.txt", JudgeVerdict.WRONG_ANSWER),
        ("joined", "tr -d '\\n' < input.txt | fold -w8", JudgeVerdict.WRONG_ANSWER),
        ("truncated", "cut -c1-8 input.txt", JudgeVerdict.WRONG_ANSWER),
        ("sorted", "fold -w8 input.txt | sort", JudgeVerdict.WRONG_ANSWER),
    ]
    manager = ContainerManager(pool_size=1, owner_id=f"soj-fold-{uuid.uuid4().hex}")
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
        # 公開入力とは別に短い行・幅ちょうど・1文字超過・空行を確認する。
        # 入力の差し替えも隔離sandbox内で行い、各実行後にcontainerを破棄する。
        boundaries = [
            ("ABC\n", "ABC\n"),
            ("ABCDEFGH\n", "ABCDEFGH\n"),
            ("ABCDEFGHI\n", "ABCDEFGH\nI\n"),
            ("AB\n\nCDEFGHIJK\n", "AB\n\nCDEFGHIJ\nK\n"),
        ]
        for fixture, expected in boundaries:
            for solution in (reference, alternative):
                command = f"printf %s {shlex.quote(fixture)} > input.txt; {solution}"
                execution = asyncio.run(client.run_with_timeout(command, PROBLEM_ID))
                assert execution.status is ExecutionStatus.COMPLETED, execution
                assert execution.exit_code == 0, execution
                assert execution.stderr == "", execution
                assert execution.stdout == expected, execution
    finally:
        try:
            manager.shutdown_pool()
        finally:
            client.close()
