"""prの縦方向段組み、別解・誤答・適用限界をrootless sandboxで検査する。"""

import asyncio
import os
import shlex
import uuid
from pathlib import Path

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
PROBLEM_ID = "PRACTICE-pr-01"


def _independent_expected(fixture: str) -> str:
    """前半・後半の行番号を対応付け、参照コマンドとは独立に期待表を作る。"""
    lines = fixture.splitlines()
    split = (len(lines) + 1) // 2
    return "".join(
        value + (" | " + lines[i + split] if i + split < len(lines) else "") + "\n"
        for i, value in enumerate(lines[:split])
    )


def test_pr_solutions_mistakes_and_boundaries_in_real_sandboxes() -> None:
    """公開入力の縦方向配置を受理し、横方向・整列・欠落と印刷機能の適用限界を区別する。"""
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(PROBLEM_ID)
    reference = record.definition.reference_solution
    alternative = 'awk \'{a[NR]=$0} END{n=int((NR+1)/2);for(i=1;i<=n;i++){printf "%s",a[i];if(i+n<=NR)printf " | %s",a[i+n];print ""}}\' input.txt'
    manager = ContainerManager(pool_size=1, owner_id=f"soj-pr-{uuid.uuid4().hex}")
    client = ShellgeiDockerClient(
        container_manager=manager, max_concurrent=1, problem_repository=repository
    )
    judge = ShellgeiJudge(repository)

    def evaluate(
        label: str,
        fixture: str | None,
        command: str,
        expected: str,
        verdict: JudgeVerdict = JudgeVerdict.ACCEPTED,
    ) -> None:
        """登録済み公開入力またはsandbox内の試験fixtureを実行し、出力と実judgeを照合する。"""
        submitted = command
        if fixture is not None:
            submitted = f"printf %s {shlex.quote(fixture)} > input.txt; {command}"
        assert len(submitted) <= 1000
        execution = asyncio.run(client.run_with_timeout(submitted, PROBLEM_ID))
        context = (label, execution)
        assert execution.status is ExecutionStatus.COMPLETED, context
        assert not execution.timed_out and not execution.truncated, context
        assert execution.exit_code == 0 and execution.stderr == "", context
        if fixture is None:
            actual = judge.judge(execution, PROBLEM_ID).verdict
        else:
            actual = judge_text(
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
        assert actual is verdict, context
        if verdict is JudgeVerdict.ACCEPTED:
            assert execution.stdout == expected, context

    try:
        manager.initialize_pool()
        evaluate("reference", None, reference, record.expected_output)
        evaluate("awk_alternative", None, alternative, record.expected_output)
        mistakes = [
            ("unchanged", "cat input.txt"),
            ("across", reference.replace("pr -2", "pr -2 -a")),
            ("adjacent_pairs", "paste -d'|' - - < input.txt"),
            ("presort", "sort input.txt | " + reference.replace(" input.txt", "")),
            (
                "remove_duplicates",
                "awk '!seen[$0]++' input.txt | " + reference.replace(" input.txt", ""),
            ),
            ("default_separator", "pr -2 -t -J input.txt"),
            ("column_padding", reference.replace(" -J", "")),
            ("headers", reference.replace(" -t", "")),
        ]
        for label, command in mistakes:
            evaluate(
                label, None, command, record.expected_output, JudgeVerdict.WRONG_ANSWER
            )
        boundaries = [
            ("empty", ""),
            ("single", "one\n"),
            ("pair", "left\nright\n"),
            ("odd", "a\nb\nc\n"),
            ("even", "a\nb\nc\nd\n"),
            ("blank_line", "a\n\nc\nd\ne\n"),
            ("no_final_newline", "a\nb\nc"),
            ("long_line", "a" * 80 + "\nb\nc\n"),
            ("page_boundary", "".join(f"{i:03}\n" for i in range(1, 133))),
        ]
        for label, fixture in boundaries:
            expected = _independent_expected(fixture)
            for name, command in [("reference", reference), ("awk", alternative)]:
                evaluate(label + "_" + name, fixture, command, expected)
        # prの印刷用整形は連続空白を再タブ化し末尾空白を落とすため、汎用の文字列保持とは区別する。
        spacing = "  lead\nmiddle  spaces\nlast  \nright\n"
        evaluate(
            "pr_spacing_limit",
            spacing,
            reference,
            _independent_expected(spacing),
            JudgeVerdict.WRONG_ANSWER,
        )
        evaluate(
            "awk_preserves_spacing",
            spacing,
            alternative,
            _independent_expected(spacing),
        )
        fixture = "".join(f"{i:03}\n" for i in range(1, 141))
        evaluate(
            "pr_page_scope_limit",
            fixture,
            reference,
            _independent_expected(fixture),
            JudgeVerdict.WRONG_ANSWER,
        )
        evaluate(
            "awk_without_page_limit",
            fixture,
            alternative,
            _independent_expected(fixture),
        )
    finally:
        try:
            manager.shutdown_pool()
        finally:
            client.close()
