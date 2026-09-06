"""改訂した通常問題の参照解答・別解・誤解例を、本番と同じ隔離設定のsandboxで確認する。"""

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
# Trueは自然な別解、Falseは正常終了するが仕様を満たさない典型的な誤答。
CASES: dict[int, list[tuple[str, bool]]] = {
    3: [("printf '%s\\n' {1..10}", True), ("seq 0 9", False)],
    5: [
        (
            'stock=0; while read -r time change; do stock=$((stock + change)); printf "%s %s\\n" "$time" "$stock"; done < input.txt',
            True,
        ),
        ("awk '{print $1, $2}' input.txt", False),
    ],
    6: [
        (
            r"printf 'scale=20; 4*a(1)\n' | bc -l | sed -E 's/^([0-9]+\.[0-9]{10}).*/\1/'",
            True,
        ),
        (
            'LC_ALL=C; printf "%.10f\\n" "$(printf \'scale=20; 4*a(1)\\n\' | bc -l)"',
            False,
        ),
    ],
    7: [
        (
            r"""awk '{if (sub(/\\$/, "")) printf "%s", $0; else print}' input.txt""",
            True,
        ),
        (r"tr -d '\\\n' < input.txt", False),
        (r"tr -d '\\' < input.txt", False),
    ],
    8: [
        (
            "awk '{for (c=0; c<=$1; c++) {t=$1-c; if (2*c+4*t==$2) print c,t}}' input.txt",
            True,
        ),
        (
            "awk '{for(c=0;c<10;c++)for(t=0;t<10;t++)if(c+t==$1 && 2*c+4*t==$2)print c,t}' input.txt",
            False,
        ),
    ],
    9: [
        (
            r"""awk 'BEGIN{RS=""; ORS="\n\n"} {entries[$1]=$0} END{PROCINFO["sorted_in"]="@ind_str_desc"; for(day in entries) print entries[day]}' input.txt""",
            True,
        ),
        (
            r"""awk 'BEGIN{RS=""; ORS="\0"} {print $0 "\n"}' input.txt | LC_ALL=C sort -z | tr '\0' '\n' """.strip(),
            False,
        ),
        (
            r"""awk 'BEGIN{RS=""; ORS="\0"} {print $0 "\n"}' input.txt | LC_ALL=C sort -zr | tr '\0' '\n' | tr -s ' ' """.strip(),
            False,
        ),
        ("LC_ALL=C sort -r input.txt", False),
    ],
    10: [
        (
            r"""awk '/^---$/{body=1; next} !body{split($0,pair,"="); values[pair[1]]=pair[2]; next} {for(key in values) gsub("{{" key "}}",values[key]); print}' input.txt""",
            True,
        ),
        (
            r"sed '1,/^---$/d' input.txt | sed -f <(sed '/^---$/,$d; s|^\([a-z]*\)=\(.*\)$|s/{{\1}}/\2/|' input.txt)",
            False,
        ),
        (
            r"sed '1,/^---$/d' input.txt | sed -f <(sed '/^---$/,$d; s|^\([a-z]*\)=\(.*\)$|s/\1/\2/g|' input.txt)",
            False,
        ),
    ],
}


@pytest.mark.parametrize("number", CASES)
def test_revised_problem_solutions_and_mistakes(number: int) -> None:
    # 各問題の参照解答と別解が正解、誤解例が不正解となり、すべて正常終了することを確認する。
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    problem_id = f"STANDARD-{number:08d}"
    cases = [
        (repository.require(problem_id).definition.reference_solution, True),
        *CASES[number],
    ]
    manager = ContainerManager(pool_size=1)
    client = ShellgeiDockerClient(
        container_manager=manager, max_concurrent=1, problem_repository=repository
    )
    judge = ShellgeiJudge(repository)
    try:
        manager.initialize_pool()
        for command, accepted in cases:
            execution = asyncio.run(client.run_with_timeout(command, problem_id))
            assert execution.status is ExecutionStatus.COMPLETED, (command, execution)
            assert execution.exit_code == 0, (command, execution)
            assert execution.stderr == "", (command, execution)
            expected = JudgeVerdict.ACCEPTED if accepted else JudgeVerdict.WRONG_ANSWER
            assert judge.judge(execution, problem_id).verdict is expected, (
                command,
                execution,
            )
    finally:
        manager.shutdown_pool()
        client.close()
