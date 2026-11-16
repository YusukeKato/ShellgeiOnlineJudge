"""unexpandの回答例・別解を実sandboxで検証する。"""

import asyncio
import os
import shlex
import uuid

import pytest

from soj_backend.judge import JudgeVerdict, ShellgeiJudge
from soj_runner.container_manager import ContainerManager
from soj_runner.run_shellgei import ShellgeiDockerClient
from soj_shared.models.execution import ExecutionResult, ExecutionStatus
from soj_shared.problem_repository import build_problem_repository
from tests.test_unexpand_problem import PROBLEMS, PROBLEM_ID, visible_indents

pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(
        os.getenv("SOJ_RUN_DOCKER_TESTS") != "1",
        reason="rootless Docker検査の明示指定が必要",
    ),
]


def test_unexpand_solutions() -> None:
    """公開入力と8境界で本文・端数の保持を調べ、幅や変換範囲を誤る4解を実judgeで区別する。"""
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    reference = repository.require(PROBLEM_ID).definition.reference_solution
    alternative = (
        "awk '{match($0,/^ */); n=4*int(RLENGTH/4); "
        'for(i=0;i<n;i+=4)printf "\\t"; '
        "print substr($0,n+1)}' input.txt | cat -T"
    )
    mistakes = (
        "unexpand input.txt | cat -T",
        "unexpand -t 4 input.txt | cat -T",
        r"sed 's/    /\t/g' input.txt | cat -T",
        r"sed 's/^    /\t/' input.txt | cat -T",
    )
    boundaries = (
        "",
        "alpha    beta\n",
        "   alpha\n",
        "     alpha  beta\n",
        "            alpha\n",
        "\n    a\n\n",
        "      \n",
        "    literal ^I\n",
    )
    manager = ContainerManager(pool_size=1, owner_id=f"soj-unexpand-{uuid.uuid4().hex}")
    client = ShellgeiDockerClient(
        container_manager=manager, max_concurrent=1, problem_repository=repository
    )
    judge = ShellgeiJudge(repository)

    def run(command: str) -> ExecutionResult:
        """隔離したrequestでcommandを実行し、正常終了時の出力と判定に使う実行結果を返す。"""
        execution = asyncio.run(client.run_with_timeout(command, PROBLEM_ID))
        assert execution.status is ExecutionStatus.COMPLETED, execution
        assert execution.exit_code == 0 and execution.stderr == "", execution
        assert not execution.truncated and not execution.timed_out, execution
        return execution

    try:
        manager.initialize_pool()
        for solution in (reference, alternative):
            execution = run(solution)
            assert execution.stdout == repository.require(PROBLEM_ID).expected_output
            assert judge.judge(execution, PROBLEM_ID).verdict is JudgeVerdict.ACCEPTED
            for fixture in boundaries:
                execution = run(
                    f"printf %s {shlex.quote(fixture)} > input.txt && {solution}"
                )
                assert execution.stdout == visible_indents(fixture), (solution, fixture)
        for mistake in mistakes:
            assert (
                judge.judge(run(mistake), PROBLEM_ID).verdict
                is JudgeVerdict.WRONG_ANSWER
            )
    finally:
        try:
            manager.shutdown_pool()
        finally:
            client.close()
