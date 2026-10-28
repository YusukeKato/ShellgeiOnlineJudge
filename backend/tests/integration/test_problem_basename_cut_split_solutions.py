"""basename・cut・splitの解法、誤答と境界条件を実rootless sandboxで検査する。"""

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
ALTERNATIVES = {
    "PRACTICE-basename-01": r"sed 's|.*/||; s/\.log$//' input.txt",
    "PRACTICE-cut-01": """awk '{print substr($0,1,2) substr($0,4,4)}' input.txt""",
    "STANDARD-00000067": (
        """awk '(NR-1)%3==0{printf "[part_%02d]\\n",int((NR-1)/3)}{print}' input.txt"""
    ),
}
MISTAKES = {
    "PRACTICE-basename-01": [
        "cat input.txt",
        "sed 's|.*/||' input.txt",
        r"sed 's/\.log$//' input.txt",
        r"sed 's|.*/||; s/\..*//' input.txt",
        r"sed 's|.*/||; s/\.log//' input.txt",
        r"sed 's|.*/||; s/\.log$//' input.txt | sort -u",
        r"""sed 's|.*/||; s/\.log$//' input.txt | tr -d ' '""",
    ],
    "PRACTICE-cut-01": [
        "cut -c1-7 input.txt",
        "cut -c1-2,5-7 input.txt",
        "cut -c1-2,4-8 input.txt",
        """awk -F- '{print $1 ($2+0)}' input.txt""",
        "cut -c1-2,4-7 input.txt | sort -u",
        "cut -c1-2,4-7 input.txt | tac",
    ],
    "STANDARD-00000067": [
        """awk '(NR-1)%2==0{printf "[part_%02d]\\n",int((NR-1)/2)}{print}' input.txt""",
        """awk '(NR-1)%3==0{printf "[part_%02d]\\n",int((NR-1)/3)+1}{print}' input.txt""",
        """awk '(NR-1)%3==0{printf "[part_%d]\\n",int((NR-1)/3)}{print}' input.txt""",
        """awk 'NR<=6{if((NR-1)%3==0)printf "[part_%02d]\\n",int((NR-1)/3);print}' input.txt""",
        """sed '/^$/d' input.txt | awk '(NR-1)%3==0{printf "[part_%02d]\\n",int((NR-1)/3)}{print}'""",
        """tr -s ' ' < input.txt | awk '(NR-1)%3==0{printf "[part_%02d]\\n",int((NR-1)/3)}{print}'""",
    ],
}
BOUNDARIES = {
    "PRACTICE-basename-01": [
        ("", ""),
        ("plain\nfolder/name\n", "plain\nname\n"),
        ("./a b/name  1.log.log\n./backup.log.bak", "name  1.log\nbackup.log.bak\n"),
        ("./-n.log\nname.LOG\n", "-n\nname.LOG\n"),
    ],
    "PRACTICE-cut-01": [
        ("", ""),
        ("AA-0000-X\n", "AA0000\n"),
        ("ZZ-9999-X\nAA-0001-Y\nZZ-9999-Z\n", "ZZ9999\nAA0001\nZZ9999\n"),
        ("AB-0010-Q", "AB0010\n"),
    ],
    "STANDARD-00000067": [
        ("", ""),
        ("one\n", "[part_00]\none\n"),
        ("a\nb\nc\n", "[part_00]\na\nb\nc\n"),
        ("a\nb\nc\nd\n", "[part_00]\na\nb\nc\n[part_01]\nd\n"),
        (
            "\n  same  line\nsame\nsame\n\n",
            "[part_00]\n\n  same  line\nsame\n[part_01]\nsame\n\n",
        ),
    ],
}


@pytest.mark.parametrize("problem_id", tuple(ALTERNATIVES))
def test_command_solutions_and_common_mistakes_in_real_sandboxes(
    problem_id: str,
) -> None:
    # 参照解・自然な別解を受理し、位置・接尾辞・空行・順序などの誤解を拒否する。
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(problem_id)
    reference = record.definition.reference_solution
    solutions = (reference, ALTERNATIVES[problem_id])
    manager = ContainerManager(pool_size=1, owner_id=f"soj-command-{uuid.uuid4().hex}")
    client = ShellgeiDockerClient(
        container_manager=manager, max_concurrent=1, problem_repository=repository
    )
    judge = ShellgeiJudge(repository)
    try:
        manager.initialize_pool()
        for command in (*solutions, *MISTAKES[problem_id]):
            execution = asyncio.run(client.run_with_timeout(command, problem_id))
            context = (problem_id, command, execution)
            assert execution.status is ExecutionStatus.COMPLETED, context
            assert execution.exit_code == 0, context
            assert execution.stderr == "", context
            expected_verdict = (
                JudgeVerdict.ACCEPTED
                if command in solutions
                else JudgeVerdict.WRONG_ANSWER
            )
            assert judge.judge(execution, problem_id).verdict is expected_verdict, (
                context
            )
            if expected_verdict is JudgeVerdict.ACCEPTED:
                assert execution.stdout == record.expected_output, context
        # 解法確認用fixtureをsandbox内だけで差し替える。非公開の採点入力は追加しない。
        for fixture, expected in BOUNDARIES[problem_id]:
            for solution in solutions:
                command = f"printf %s {shlex.quote(fixture)} > input.txt; {solution}"
                execution = asyncio.run(client.run_with_timeout(command, problem_id))
                boundary_context = (problem_id, fixture, solution, execution)
                assert execution.status is ExecutionStatus.COMPLETED, boundary_context
                assert execution.exit_code == 0, boundary_context
                assert execution.stderr == "", boundary_context
                # 最終改行の有無は現行judgeが区別しない。公開入力では上でbyte一致も確認する。
                assert execution.stdout.replace("\r", "").rstrip(
                    " \n"
                ) == expected.rstrip(" \n"), boundary_context
    finally:
        try:
            manager.shutdown_pool()
        finally:
            client.close()
