"""chmodの解法・誤答と、同一request内の状態更新・request間の分離を検査する。"""

import asyncio
import os
from pathlib import Path
import shlex
import uuid

import pytest

from soj_backend.judge import JudgeVerdict, ShellgeiJudge, TextJudgeInput, judge_text
from soj_runner.container_manager import ContainerManager
from soj_runner.run_shellgei import ShellgeiDockerClient
from soj_shared.models.execution import ExecutionStatus
from soj_shared.models.problem import TextJudgeSpecification
from soj_shared.problem_repository import build_problem_repository
from tests.test_chmod_problem import (
    ALTERNATIVE,
    CASES,
    PROBLEM_ID,
    expected_permissions,
)

pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(
        os.getenv("SOJ_RUN_DOCKER_TESTS") != "1",
        reason="解答の実行にはrootless Dockerへの明示指定が必要",
    ),
]
PROBLEMS = Path(__file__).resolve().parents[3] / "problems"


def test_chmod_solutions_mistakes_boundaries_and_request_isolation() -> None:
    """2解法・4誤答・8境界を確認し、file本文と権限が次のrequestへ残らないことも検査する。"""
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(PROBLEM_ID)
    judge = ShellgeiJudge(repository)
    reference = record.definition.reference_solution
    manager = ContainerManager(pool_size=1, owner_id=f"soj-chmod-{uuid.uuid4().hex}")
    client = ShellgeiDockerClient(
        container_manager=manager, max_concurrent=1, problem_repository=repository
    )

    def evaluate(
        label: str, solution: str, operations: str | None = None, accepted: bool = True
    ) -> None:
        """fixture差し替えもsandbox内だけで行い、raw出力・policy・実judgeを照合する。"""
        prefix = (
            ""
            if operations is None
            else f"printf %s {shlex.quote(operations)} > input.txt; "
        )
        submitted = prefix + solution
        assert len(submitted) <= 1000
        execution = asyncio.run(client.run_with_timeout(submitted, PROBLEM_ID))
        context = (label, execution)
        assert execution.status is ExecutionStatus.COMPLETED, context
        assert execution.exit_code == 0 and execution.stderr == "", context
        assert not execution.timed_out and not execution.truncated, context
        expected = (
            record.expected_output
            if operations is None
            else expected_permissions(operations)
        )
        verdict = (
            judge.judge(execution, PROBLEM_ID).verdict
            if operations is None
            else judge_text(
                TextJudgeSpecification(type="text", expected_output=expected),
                record.definition.execution,
                TextJudgeInput(
                    stdout=execution.stdout,
                    stderr=execution.stderr,
                    exit_code=execution.exit_code,
                    timed_out=execution.timed_out,
                    truncated=execution.truncated,
                ),
            ).verdict
        )
        assert verdict is (
            JudgeVerdict.ACCEPTED if accepted else JudgeVerdict.WRONG_ANSWER
        ), context
        if accepted:
            assert execution.stdout == expected, context

    def assert_fresh_fixture() -> None:
        """前のchmodや本文書換えが残らず、archiveの初期0600・sample本文へ戻ることを確認する。"""
        execution = asyncio.run(
            client.run_with_timeout("stat -c %a target.txt; cat target.txt", PROBLEM_ID)
        )
        assert execution.status is ExecutionStatus.COMPLETED
        assert execution.exit_code == 0 and execution.stderr == ""
        assert execution.stdout == "600\nsample\n"
        assert not execution.timed_out and not execution.truncated

    mistakes = [
        (
            "reset_each_time",
            'while IFS= read -r mode; do chmod 644 target.txt; chmod "$mode" target.txt; stat -c %03a target.txt; done < input.txt',
        ),
        (
            "assignment_as_add",
            'chmod 644 target.txt; while IFS= read -r mode; do chmod "${mode/=/+}" target.txt; stat -c %03a target.txt; done < input.txt',
        ),
        (
            "final_only",
            'chmod 644 target.txt; while IFS= read -r mode; do chmod "$mode" target.txt; done < input.txt; stat -c %03a target.txt',
        ),
        (
            "before_change",
            'chmod 644 target.txt; while IFS= read -r mode; do stat -c %03a target.txt; chmod "$mode" target.txt; done < input.txt',
        ),
    ]
    try:
        manager.initialize_pool()
        assert_fresh_fixture()
        for index, solution in enumerate((reference, ALTERNATIVE)):
            evaluate(f"public-{index}", solution)
        for label, solution in mistakes:
            evaluate(label, solution, accepted=False)
        for label, operations, expected in CASES[1:]:
            assert expected_permissions(operations) == expected
            for index, solution in enumerate((reference, ALTERNATIVE)):
                evaluate(f"{label}-{index}", solution, operations)
        # 今回だけのwritable fixtureを変更しても、次回は実行archiveから復元される。
        changed = asyncio.run(
            client.run_with_timeout(
                "printf changed > target.txt; chmod 000 target.txt", PROBLEM_ID
            )
        )
        assert changed.status is ExecutionStatus.COMPLETED
        assert changed.exit_code == 0 and changed.stderr == ""
        assert_fresh_fixture()
    finally:
        try:
            manager.shutdown_pool()
        finally:
            client.close()
