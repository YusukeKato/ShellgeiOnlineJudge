"""単位付きサイズの比較、別解、誤答と境界条件をrootless sandboxで検査する。"""

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
PROBLEM_ID = "PRACTICE-sort-04"


def _expected(fixture: str) -> str:
    """整数でbyte数へ換算し、各値より小さい要素数による順位から期待値を求める。"""
    lines = fixture.splitlines()
    units = {"K": 1024, "M": 1024**2, "G": 1024**3}
    values = []
    for line in lines:
        size = line.split()[1]
        values.append(
            int(size[:-1]) * units[size[-1]] if size[-1] in units else int(size)
        )
    ranks = [sum(other < value for other in values) for value in values]
    assert len(set(ranks)) == len(lines)
    by_rank = dict(zip(ranks, lines, strict=True))
    return "".join(by_rank[index] + "\n" for index in range(len(lines)))


def test_sort_h_solutions_mistakes_and_boundaries_in_real_sandboxes() -> None:
    """単位・桁数を解釈したキー比較を受理し、辞書順・数値だけ・名前順・逆順を区別する。"""
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(PROBLEM_ID)
    reference = record.definition.reference_solution
    alternative = (
        "awk '{s=$2;u=substr(s,length(s),1);"
        'm=(u=="K"?1024:u=="M"?1048576:u=="G"?1073741824:1);'
        'printf "%.0f %s\\n",(s+0)*m,$0}\' input.txt '
        "| sort -n -k1,1 | cut -d' ' -f2-"
    )
    manager = ContainerManager(pool_size=1, owner_id=f"soj-sort-h-{uuid.uuid4().hex}")
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
        """境界入力の作成もsandbox内に限定し、raw出力と正常終了policy・judgeを照合する。"""
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
            ("converted_bytes", alternative),
        ):
            evaluate(label, solution, record.expected_output)
        for label, solution in [
            ("lexical", "sort -k2,2 input.txt"),
            ("numeric_only", "sort -k2,2n input.txt"),
            ("no_field_key", "sort -h input.txt"),
            ("descending", "sort -k2,2hr input.txt"),
        ]:
            evaluate(label, solution, record.expected_output, accepted=False)
        boundaries = [
            ("empty", ""),
            ("singleton", "only.txt 2M\n"),
            ("unit_boundaries", "a 1K\nb 1023\nc 1M\nd 1023K\ne 1G\nf 1023M\n"),
            ("same_unit", "a 100M\nb 2M\nc 12M\n"),
            ("zero", "a 1K\nb 0\nc 1\n"),
            ("no_final_lf", "z 2M\na 900K"),
        ]
        for label, fixture in boundaries:
            for index, solution in enumerate((reference, alternative)):
                evaluate(f"{label}-{index}", solution, _expected(fixture), fixture)
    finally:
        try:
            manager.shutdown_pool()
        finally:
            client.close()
