"""revの文字反転とawk別解、行順・空行・スペースの取り違えを実sandboxで検証する。"""

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
PROBLEM_ID = "PRACTICE-rev-01"


def test_rev_solutions_and_common_mistakes_in_real_sandboxes() -> None:
    # 参照解・別解と境界条件を確認し、行順反転・空行削除・スペース圧縮などの6誤答を拒否する。
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(PROBLEM_ID)
    reference = record.definition.reference_solution
    alternative = 'awk \'{for(i=length($0);i>0;i--)printf "%s",substr($0,i,1);print ""}\' input.txt'
    cases = [
        ("reference", reference, JudgeVerdict.ACCEPTED),
        ("awk", alternative, JudgeVerdict.ACCEPTED),
        ("unchanged", "cat input.txt", JudgeVerdict.WRONG_ANSWER),
        ("line_order", "tac input.txt", JudgeVerdict.WRONG_ANSWER),
        ("both_orders", "rev input.txt | tac", JudgeVerdict.WRONG_ANSWER),
        ("blank_removed", "rev input.txt | sed '/^$/d'", JudgeVerdict.WRONG_ANSWER),
        ("space_squeezed", "rev input.txt | tr -s ' '", JudgeVerdict.WRONG_ANSWER),
        (
            "words_only",
            "awk '{for(i=NF;i>0;i--)printf \"%s%s\",$i,(i==1?ORS:OFS)}' input.txt",
            JudgeVerdict.WRONG_ANSWER,
        ),
    ]
    manager = ContainerManager(pool_size=1, owner_id=f"soj-rev-{uuid.uuid4().hex}")
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
        # 公開入力とは別に空ファイル・1文字・行境界・空行と端のスペースを確認する。
        # fixtureの差し替えも隔離sandbox内で行い、ホストでは解答を実行しない。
        boundaries = [
            ("", ""),
            ("Q\n", "Q\n"),
            ("ab\nCD\n", "ba\nDC\n"),
            (" aB  \n\n", "  Ba \n\n"),
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
