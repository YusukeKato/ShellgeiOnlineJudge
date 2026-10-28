"""未完了作業の抽出・連番付けとawk別解、誤答・境界条件を実sandboxで検証する。"""

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
PROBLEM_ID = "STANDARD-00000065"


def test_pending_tasks_solutions_and_common_mistakes_in_real_sandboxes() -> None:
    # 参照解・別解と境界条件を確認し、接頭辞・元の行番号・整列・空白・番号書式の6誤答を拒否する。
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(PROBLEM_ID)
    reference = record.definition.reference_solution
    alternative = (
        r"""awk '/^TODO / {printf "%02d %s\n", ++n, substr($0,6)}' input.txt"""
    )
    numbered = " | nl -ba -w2 -nrz -s' '"
    cases = [
        ("reference", reference, JudgeVerdict.ACCEPTED),
        ("awk", alternative, JudgeVerdict.ACCEPTED),
        (
            "unanchored",
            "sed -n 's/.*TODO //p' input.txt" + numbered,
            JudgeVerdict.WRONG_ANSWER,
        ),
        (
            "prefix_only",
            "sed -n 's/^TODO *//p' input.txt" + numbered,
            JudgeVerdict.WRONG_ANSWER,
        ),
        (
            "original_numbers",
            r"""awk '/^TODO / {printf "%02d %s\n", NR, substr($0,6)}' input.txt""",
            JudgeVerdict.WRONG_ANSWER,
        ),
        (
            "sorted_unique",
            "sed -n 's/^TODO //p' input.txt | sort -u" + numbered,
            JudgeVerdict.WRONG_ANSWER,
        ),
        (
            "space_collapse",
            r"""awk '/^TODO / {$1="";sub(/^ /,"");printf "%02d %s\n",++n,$0}' input.txt""",
            JudgeVerdict.WRONG_ANSWER,
        ),
        (
            "default_numbering",
            "sed -n 's/^TODO //p' input.txt | nl",
            JudgeVerdict.WRONG_ANSWER,
        ),
    ]
    manager = ContainerManager(
        pool_size=1, owner_id=f"soj-pending-tasks-{uuid.uuid4().hex}"
    )
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
        # 公開入力とは別に該当なし・1件・10件・空の作業名を確認する。
        # 差し替えもsandbox内で行い、公開仕様を非公開テスト条件として増やさない。
        boundaries = [
            ("DONE nothing\n", ""),
            ("TODO one\n", "01 one\n"),
            ("TODO repeat\n" * 10, "".join(f"{n:02d} repeat\n" for n in range(1, 11))),
            ("TODO \nTODO two\n", "01 \n02 two\n"),
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
