"""realpathの字句的正規化、別解・誤答・境界をrootless sandboxで検査する。"""

import asyncio
import os
import posixpath
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
        reason="解答の実行にはrootless Dockerへの明示指定が必要",
    ),
]
PROBLEMS = Path(__file__).resolve().parents[3] / "problems"
PROBLEM_ID = "PRACTICE-realpath-01"


def test_realpath_solutions_mistakes_and_boundaries_in_real_sandboxes() -> None:
    """パス全体の正規化と、順序・重複・スペース・実体を調べない挙動を確認する。"""
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(PROBLEM_ID)
    reference = record.definition.reference_solution
    alternative = 'awk -F/ \'{n=0;for(i=1;i<=NF;i++){if($i==""||$i==".")continue;if($i==".."){if(n)n--}else a[++n]=$i}printf "/";for(i=1;i<=n;i++)printf "%s%s",a[i],i<n?"/":"\\n";if(!n)print ""}\' input.txt'
    cases = [
        ("reference", reference, JudgeVerdict.ACCEPTED),
        ("awk_alternative", alternative, JudgeVerdict.ACCEPTED),
        ("unchanged", "cat input.txt", JudgeVerdict.WRONG_ANSWER),
        (
            "collapse_slashes_only",
            "sed -E 's:/+:/:g' input.txt",
            JudgeVerdict.WRONG_ANSWER,
        ),
        ("delete_all_dots", r"sed 's/\.//g' input.txt", JudgeVerdict.WRONG_ANSWER),
        (
            "basename_only",
            'while IFS= read -r p; do basename -- "$p"; done < input.txt',
            JudgeVerdict.WRONG_ANSWER,
        ),
        ("split_spaces", "realpath -ms -- $(cat input.txt)", JudgeVerdict.WRONG_ANSWER),
        ("sort_unique", reference + " | sort -u", JudgeVerdict.WRONG_ANSWER),
        (
            "require_existing",
            reference.replace("-ms", "-es"),
            JudgeVerdict.EXECUTION_FAILURE,
        ),
    ]
    manager = ContainerManager(pool_size=1, owner_id=f"soj-realpath-{uuid.uuid4().hex}")
    client = ShellgeiDockerClient(
        container_manager=manager, max_concurrent=1, problem_repository=repository
    )
    judge = ShellgeiJudge(repository)
    try:
        manager.initialize_pool()
        for label, command, verdict in cases:
            execution = asyncio.run(client.run_with_timeout(command, PROBLEM_ID))
            context = (label, command, execution)
            assert execution.status is ExecutionStatus.COMPLETED, context
            assert not execution.timed_out and not execution.truncated, context
            assert judge.judge(execution, PROBLEM_ID).verdict is verdict, context
            if verdict is JudgeVerdict.ACCEPTED:
                assert execution.exit_code == 0 and execution.stderr == "", context
                assert execution.stdout == record.expected_output, context
        boundaries = [
            "",
            "/\n/../../\n",
            "/data/release notes/../team notes/result.txt",
            "/a//b/./\n",
            "/a..b/.../file.v1\n",
            "/a/./b\n/a/b\n",
            "/data/-n/./name\n",
        ]
        for fixture in boundaries:
            expected = "".join(
                posixpath.normpath(p) + "\n" for p in fixture.splitlines()
            )
            for solution in (reference, alternative):
                command = f"printf %s {shlex.quote(fixture)} > input.txt; {solution}"
                execution = asyncio.run(client.run_with_timeout(command, PROBLEM_ID))
                context = (fixture, solution, execution)
                assert execution.status is ExecutionStatus.COMPLETED, context
                assert execution.exit_code == 0 and execution.stderr == "", context
                assert execution.stdout == expected, context
        for solution, expected in [
            (reference, "/work/answer.txt\n"),
            (reference.replace("-ms", "-m"), "/answer.txt\n"),
        ]:
            # 各提出で作る専用symlinkにより、字句処理と実体解決の違いを区別する。
            command = (
                "ln -s /tmp /work/alias; "
                "printf '%s\\n' /work/alias/../answer.txt > input.txt; " + solution
            )
            execution = asyncio.run(client.run_with_timeout(command, PROBLEM_ID))
            assert execution.status is ExecutionStatus.COMPLETED, execution
            assert execution.exit_code == 0 and execution.stderr == "", execution
            assert execution.stdout == expected, execution
    finally:
        try:
            manager.shutdown_pool()
        finally:
            client.close()
