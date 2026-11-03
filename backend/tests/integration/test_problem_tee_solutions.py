"""teeの表示と保存、別解、誤答と境界条件をrootless sandboxで検査する。"""

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
PROBLEM_ID = "PRACTICE-tee-01"


def _expected(fixture: str) -> str:
    """先頭1文字による選別とLFの個数から、shellとは独立に本文と件数を求める。"""
    retained = [line for line in fixture.splitlines(keepends=True) if line[:1] != "#"]
    body = "".join(retained)
    return body + f"LINES {body.count(chr(10))}\n"


def test_tee_solutions_mistakes_and_boundaries_in_real_sandboxes() -> None:
    """表示と保存を両立し、空行・字下げ#・重複・抽出後の件数とrequest分離を区別する。"""
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(PROBLEM_ID)
    reference = record.definition.reference_solution
    alternative = (
        "sed '/^#/d' input.txt > preview.txt; cat preview.txt; "
        "printf 'LINES %s\\n' \"$(wc -l < preview.txt)\""
    )
    manager = ContainerManager(pool_size=1, owner_id=f"soj-tee-{uuid.uuid4().hex}")
    client = ShellgeiDockerClient(
        container_manager=manager, max_concurrent=1, problem_repository=repository
    )
    judge = ShellgeiJudge(repository)

    def evaluate(
        label: str,
        solution: str,
        expected: str,
        fixture: str | None = None,
        accepted: bool = True,
    ) -> None:
        """境界の入力作成もsandbox内に限定し、raw出力・policy・現行judgeを照合する。"""
        prefix = (
            "" if fixture is None else f"printf %s {shlex.quote(fixture)} > input.txt; "
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
            if fixture is None
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
        for label, solution in (
            ("reference", reference),
            ("redirect_alternative", alternative),
        ):
            evaluate(label, solution, record.expected_output)
        evaluate(
            "saved_copy_matches_displayed_body",
            reference + "; cmp -s preview.txt <(sed '/^#/d' input.txt)",
            record.expected_output,
        )
        mistakes = [
            ("unanchored_hash", reference.replace("'^#'", "'#'")),
            ("drop_blank", reference.replace("| tee", "| grep . | tee")),
            ("deduplicate_sort", reference.replace("| tee", "| sort -u | tee")),
            (
                "count_original",
                reference.replace("wc -l < preview.txt", "wc -l < input.txt"),
            ),
            (
                "redirect_only",
                "sed '/^#/d' input.txt > preview.txt; "
                "printf 'LINES %s\\n' \"$(wc -l < preview.txt)\"",
            ),
        ]
        for label, solution in mistakes:
            evaluate(label, solution, record.expected_output, accepted=False)
        boundaries = [
            ("empty", ""),
            ("all_comments", "# one\n# two\n"),
            ("no_comments", "one\ntwo\n"),
            ("only_blank", "\n"),
            ("indented_hash", "  # keep\n\t# also keep\n# remove\n"),
            ("duplicates", "same\n# comment\nsame\n"),
            ("unicode", "# 注記\n猫と犬\n\n猫と犬\n"),
            ("final_blank", "x\n# note\n\n"),
        ]
        for label, fixture in boundaries:
            for index, solution in enumerate((reference, alternative)):
                evaluate(f"{label}-{index}", solution, _expected(fixture), fixture)
        evaluate(
            "no_cross_request_copy",
            "test ! -e preview.txt && printf 'isolated\\n'",
            "isolated\n",
            fixture="",
        )
    finally:
        try:
            manager.shutdown_pool()
        finally:
            client.close()
