"""joinとfactorの解法・誤答・小さな境界を明示rootless sandboxで検査する。"""

import asyncio
import math
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
ALTERNATIVES = {
    "join": "awk 'FILENAME==ARGV[1]{name[$1]=$2;next}{print $1,($1 in name?name[$1]:\"UNKNOWN\"),$2}' catalog.txt input.txt | sort -k1,1 -k3,3n",
    "factor": 'awk \'NF {n=$1+0;printf "%d:",n;for(p=2;p<=n/p;p++)while(n%p==0){printf " %d",p;n/=p}if(n>1)printf " %d",n;print ""}\' input.txt',
}

JOIN_CASES = [
    ("empty_orders", "", "A05 Apple\n"),
    ("empty_catalog", "D40 2\n", ""),
    ("single_match", "A05 1\n", "A05 Apple\n"),
    ("all_unknown", "Y90 12\nX80 2\n", "A05 Apple\n"),
    ("duplicate_record", "C20 2\nC20 2\n", "C20 Cable\n"),
    ("reordered", "B10 1\nA05 3\n", "A05 Apple\nB10 Book\n"),
    ("no_final_lf", "C20 12\nC20 2", "C20 Cable"),
    ("numeric_and_unused", "C20 100\nC20 9\nC20 11\n", "E50 Envelope\nC20 Cable\n"),
]
FACTOR_CASES = [
    ("empty", ""),
    ("one", "1\n"),
    ("prime", "97\n"),
    ("power", "1024\n"),
    ("square", "49\n"),
    ("duplicate", "12\n12\n"),
    ("whitespace", "  9 \n\t25\t\n\n"),
    ("no_final_lf", "6\n13"),
]


def expected_output(command: str, fixtures: dict[str, str]) -> str:
    """参照commandと独立に、辞書参照または素数のべきへの可除性で小入力の正解を求める。"""
    if command == "join":
        names = dict(line.split() for line in fixtures["catalog.txt"].splitlines())
        orders = sorted(
            (code, int(quantity))
            for code, quantity in (
                line.split() for line in fixtures["input.txt"].splitlines()
            )
        )
        return "".join(
            f"{code} {names.get(code, 'UNKNOWN')} {quantity}\n"
            for code, quantity in orders
        )
    lines = []
    for word in fixtures["input.txt"].split():
        n = int(word)
        assert 1 <= n <= 1024
        primes = [
            p
            for p in range(2, n + 1)
            if all(p % d for d in range(2, math.isqrt(p) + 1))
        ]
        parts = []
        for prime in primes:
            power = prime
            while n % power == 0:
                parts.append(prime)
                power *= prime
        lines.append(f"{n}:" + "".join(f" {p}" for p in parts) + "\n")
    return "".join(lines)


@pytest.mark.parametrize("command", ["join", "factor"])
def test_solutions_mistakes_and_boundaries(command: str) -> None:
    """各問で公開2解法・5誤答・8境界の2解法を確認し、順序・欠損・重複等を区別する。"""
    problem_id = f"PRACTICE-{command}-01"
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(problem_id)
    reference = record.definition.reference_solution
    public = {f.path: f.content for f in record.definition.execution.fixtures}
    assert expected_output(command, public) == record.expected_output
    manager = ContainerManager(
        pool_size=1, owner_id=f"soj-{command}-{uuid.uuid4().hex}"
    )
    client = ShellgeiDockerClient(
        container_manager=manager, max_concurrent=1, problem_repository=repository
    )
    judge = ShellgeiJudge(repository)

    def evaluate(
        label: str,
        solution: str,
        fixtures: dict[str, str] | None = None,
        accepted: bool = True,
    ) -> None:
        """境界fixtureもsandbox内でだけ準備し、生出力・終了状態・実judgeを照合する。"""
        prefix = (
            ""
            if fixtures is None
            else "".join(
                f"printf %s {shlex.quote(content)} > {shlex.quote(path)}; "
                for path, content in fixtures.items()
            )
        )
        submitted = prefix + solution
        assert len(submitted) <= 1000
        execution = asyncio.run(client.run_with_timeout(submitted, problem_id))
        context = (command, label, execution)
        assert execution.status is ExecutionStatus.COMPLETED, context
        assert execution.exit_code == 0 and execution.stderr == "", context
        assert not execution.timed_out and not execution.truncated, context
        expected = expected_output(command, public if fixtures is None else fixtures)
        verdict = (
            judge.judge(execution, problem_id).verdict
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

    if command == "join":
        mistakes = [
            ("inner_only", reference.replace("-a1 ", "")),
            ("right_also", reference.replace("-a1", "-a1 -a2")),
            ("lexical_quantity", reference.replace("-k2,2n", "-k2,2")),
            ("collapse_code", reference + " | awk '!seen[$1]++'"),
            ("row_position", "paste input.txt catalog.txt | awk '{print $1,$4,$2}'"),
        ]
        cases = [
            (name, {"input.txt": orders, "catalog.txt": catalog})
            for name, orders, catalog in JOIN_CASES
        ]
    else:
        mistakes = [
            (
                "unique_factors",
                'factor < input.txt | awk \'{delete seen;printf "%s",$1;for(i=2;i<=NF;i++)if(!seen[$i]++)printf " %s",$i;print ""}\'',
            ),
            ("one_factor", "factor < input.txt | sed 's/^1:$/1: 1/'"),
            ("input_sorted", "sort -n input.txt | factor"),
            ("records_deduplicated", "sort -nu input.txt | factor"),
            (
                "descending",
                'factor < input.txt | awk \'{printf "%s",$1;for(i=NF;i>=2;i--)printf " %s",$i;print ""}\'',
            ),
        ]
        cases = [(name, {"input.txt": content}) for name, content in FACTOR_CASES]
    try:
        manager.initialize_pool()
        for i, solution in enumerate((reference, ALTERNATIVES[command])):
            evaluate(f"public-{i}", solution)
        for label, solution in mistakes:
            evaluate(label, solution, accepted=False)
        for label, fixtures in cases:
            for i, solution in enumerate((reference, ALTERNATIVES[command])):
                evaluate(f"{label}-{i}", solution, fixtures)
    finally:
        try:
            manager.shutdown_pool()
        finally:
            client.close()
