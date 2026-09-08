"""正規表現1〜10番の別解と典型的な誤答を、実sandboxとjudgeで検査する。"""

import asyncio
import os
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
CASES = [
    (1, "sed -n '/^A/p' input.txt", "grep 'A' input.txt"),
    (
        2,
        "grep -Ex '[RGB][0-9]{3}!{1,2}' input.txt",
        "grep -E '[RGB][0-9]{3}!{1,2}' input.txt",
    ),
    (3, "grep -E '^(RYG|RG)+$' input.txt", "grep -E '^[RYG]+$' input.txt"),
    (
        4,
        r"sed -n '/^\([a-z]\)\([a-z]\)\2\1$/p' input.txt",
        "grep -E '^[a-z]{4}$' input.txt",
    ),
    (5, "sed -nE '/(^| )open( |$)/p' input.txt", "grep -w 'open' input.txt"),
    (
        6,
        "awk -F'[<>]' '{for(i=2;i<=NF;i+=2)if($i!=\"\")print $i}' input.txt",
        "grep -oE '<.*>' input.txt | tr -d '<>'",
    ),
    (7, r"sed '/\([RGB]\)\1/d' input.txt", "grep -v 'RR' input.txt"),
    (8, "sed 's/[0-9][0-9]*/#/g' input.txt", "sed 's/[0-9]/#/g' input.txt"),
    (
        9,
        r"sed 's/\([a-z][a-z]*\)->\([a-z][a-z]*\)/\2->\1/g' input.txt",
        r"sed -E 's/([a-z]+)->([a-z]+)/\2->\1/' input.txt",
    ),
    (
        10,
        'awk \'{for(i=1;i<=NF;i++)if(i==1||$i!=$(i-1)){printf "%s%s",sep,$i;sep=" "}print "";sep=""}\' input.txt',
        r"sed -E 's/([a-z]+)( \1)+/\1/g' input.txt",
    ),
]


def test_regex_solutions_and_mistakes() -> None:
    # 参照解答・別解は正解、部分一致・過剰な抽出・反復や境界の取り違えによる誤答は不正解になる。
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    manager = ContainerManager(pool_size=1)
    client = ShellgeiDockerClient(
        container_manager=manager, max_concurrent=1, problem_repository=repository
    )
    judge = ShellgeiJudge(repository)
    try:
        manager.initialize_pool()
        for number, alternative, mistake in CASES:
            problem_id = f"REGEX-{number:08}"
            reference = repository.require(problem_id).definition.reference_solution
            commands = [
                (reference, True),
                (alternative, True),
                (mistake, False),
            ]
            for command, accepted in commands:
                execution = asyncio.run(client.run_with_timeout(command, problem_id))
                context = (problem_id, command, execution)
                assert execution.status is ExecutionStatus.COMPLETED, context
                assert execution.exit_code == 0, context
                assert execution.stderr == "", context
                expected = (
                    JudgeVerdict.ACCEPTED if accepted else JudgeVerdict.WRONG_ANSWER
                )
                assert judge.judge(execution, problem_id).verdict is expected, context
    finally:
        manager.shutdown_pool()
        client.close()
