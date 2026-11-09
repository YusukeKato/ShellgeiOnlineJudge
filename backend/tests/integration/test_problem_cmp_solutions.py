"""cmpの回答例・別解・誤答とbyte境界をrootless sandboxで検査する。"""

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

pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(
        os.getenv("SOJ_RUN_DOCKER_TESTS") != "1",
        reason="解答の実行にはrootless Dockerへの明示指定が必要",
    ),
]
PROBLEMS = Path(__file__).resolve().parents[3] / "problems"
PROBLEM_ID = "PRACTICE-cmp-01"
ALTERNATIVE = "paste <(od -An -v -tu1 -w1 input.txt) <(od -An -v -tu1 -w1 updated.txt) | awk '$1!=$2{print NR}'"
CASES = [
    ("identical", "a\n", "a\n"),
    ("empty", "", ""),
    ("one_byte", "a", "b"),
    ("first_last", "abc\n", "xbc!"),
    ("no_final_lf", "abc", "axc"),
    ("unicode_prefix", "猫a\n", "猫b\n"),
    ("line_feed", "a\nb\n", "a b\n"),
    ("utf8_internal", "猫\n", "犬\n"),
]


def test_cmp_solutions_mistakes_and_boundaries_in_real_sandboxes() -> None:
    """公開2解法・4誤答と8境界で、全相違・1始まり・順序・UTF-8/LF位置を区別する。"""
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(PROBLEM_ID)
    reference = record.definition.reference_solution
    manager = ContainerManager(pool_size=1, owner_id=f"soj-cmp-{uuid.uuid4().hex}")
    client = ShellgeiDockerClient(
        container_manager=manager, max_concurrent=1, problem_repository=repository
    )
    judge = ShellgeiJudge(repository)

    def evaluate(
        label: str,
        solution: str,
        expected: str,
        fixtures: tuple[str, str] | None = None,
        accepted: bool = True,
    ) -> None:
        """公開fixtureまたはsandbox内で準備した境界入力を、raw出力・policy・judgeで照合する。"""
        prefix = ""
        if fixtures is not None:
            prefix = (
                f"printf %s {shlex.quote(fixtures[0])} > input.txt; "
                f"printf %s {shlex.quote(fixtures[1])} > updated.txt; "
            )
        command = prefix + solution
        assert len(command) <= 1000
        execution = asyncio.run(client.run_with_timeout(command, PROBLEM_ID))
        context = (label, execution)
        assert execution.status is ExecutionStatus.COMPLETED, context
        assert execution.exit_code == 0 and execution.stderr == "", context
        assert not execution.timed_out and not execution.truncated, context
        verdict = (
            judge.judge(execution, PROBLEM_ID).verdict
            if fixtures is None
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

    try:
        manager.initialize_pool()
        for index, solution in enumerate((reference, ALTERNATIVE)):
            evaluate(f"public-{index}", solution, record.expected_output)
        mistakes = [
            ("first_only", reference + " | head -n1"),
            ("zero_based", "cmp -l input.txt updated.txt | awk '{print $1-1}'"),
            ("ordinal", "cmp -l input.txt updated.txt | awk '{print NR}'"),
            ("reverse", reference + " | sort -nr"),
        ]
        for label, solution in mistakes:
            evaluate(label, solution, record.expected_output, accepted=False)
        for label, original, updated in CASES:
            before, after = original.encode("utf-8"), updated.encode("utf-8")
            assert len(before) == len(after)
            expected = "".join(
                f"{position}\n"
                for position, (left, right) in enumerate(zip(before, after), 1)
                if left != right
            )
            for index, solution in enumerate((reference, ALTERNATIVE)):
                evaluate(f"{label}-{index}", solution, expected, (original, updated))
    finally:
        try:
            manager.shutdown_pool()
        finally:
            client.close()
