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
            'printf "%.10f\\n" "$(printf \'scale=20; 4*a(1)\\n\' | bc -l)"',
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
            r"""awk 'BEGIN{RS=""; ORS="\0"} {print $0 "\n"}' input.txt | sort -z | tr '\0' '\n' """.strip(),
            False,
        ),
        (
            r"""awk 'BEGIN{RS=""; ORS="\0"} {print $0 "\n"}' input.txt | sort -zr | tr '\0' '\n' | tr -s ' ' """.strip(),
            False,
        ),
        ("sort -r input.txt", False),
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
    11: [
        (
            r"""awk '{for(c=1;c<=NF;c++) a[NR,c]=$c; cols=NF} END{for(c=1;c<=cols;c++){for(r=NR;r>=1;r--) printf "%s%s",a[r,c],r==1?"\n":" "}}' input.txt""",
            True,
        ),
        ("rs -T < input.txt | awk '{$1=$1;print}'", False),
        ("rs -T < input.txt | awk '{print $3,$2,$1}'", False),
    ],
    12: [
        ("sed 'y/01/10/' input.txt", True),
        ("sed 's/0/1/g; s/1/0/g' input.txt", False),
        ("rev input.txt", False),
    ],
    13: [
        (
            r"""comm -23 <(printf '%s\n' {a..z}) <(fold -w1 input.txt | sort -u)""",
            True,
        ),
        (
            r"""printf '%s' {a..z} | tr -d "$(tr -d '\n' < input.txt)" | fold -w1 | head -n1""",
            False,
        ),
    ],
    14: [
        (
            r"""awk '{names[$2]=names[$2] " " $1} END{for(team in names) print team names[team]}' input.txt | sort -k1,1n""",
            True,
        ),
        (
            r"""sort -s -k2,2 input.txt | awk '$2!=team{if(NR>1)printf "\n";team=$2;printf "%s",team}{printf " %s",$1}END{print ""}' """.strip(),
            False,
        ),
        (
            r"""sort -k2,2n input.txt | awk '$2!=team{if(NR>1)printf "\n";team=$2;printf "%s",team}{printf " %s",$1}END{print ""}' """.strip(),
            False,
        ),
    ],
    15: [
        (
            r"""awk '{prime=($1>=2); for(d=2;d*d<=$1;d++) if($1%d==0){prime=0;break} print prime?"YES":"NO"}' input.txt""",
            True,
        ),
        (
            r"""awk '{prime=1; for(d=2;d*d<=$1;d++) if($1%d==0){prime=0;break} print prime?"YES":"NO"}' input.txt""",
            False,
        ),
    ],
    16: [
        (
            r"""awk '{for(i=1;i<=length($0);i++){c=substr($0,i,1);printf "%s",c=="&"?"&amp;":c=="<"?"&lt;":c==">"?"&gt;":c} print ""}' input.txt""",
            True,
        ),
        (r"sed 's/</\&lt;/g; s/>/\&gt;/g; s/\&/\&amp;/g' input.txt", False),
        ("cat input.txt", False),
    ],
    17: [
        ("sort -s -k2,2nr input.txt | sed -n '1,3p'", True),
        ("sort -s -k2,2r input.txt | head -n3", False),
        ("sort -k2,2nr input.txt | head -n3", False),
        ("sort -s -k2,2nr input.txt", False),
    ],
    18: [
        (
            r"""awk '{op[NR]=$2;v[NR]=$3} END{for(n=1;n<=100;n++){ok=1;for(i=1;i<=NR;i++)if((op[i]==">" && n<=v[i])||(op[i]=="<" && n>=v[i]))ok=0;if(ok)print n}}' input.txt""",
            True,
        ),
        (
            r"""awk 'BEGIN{lo=1;hi=100} $2==">"&&$3>=lo{lo=$3} $2=="<"&&$3<=hi{hi=$3} END{print lo,hi}' input.txt | xargs seq""",
            False,
        ),
        (
            r"""awk 'BEGIN{lo=1;hi=100} $2==">"&&$3>lo{lo=$3} $2=="<"&&$3<hi{hi=$3} END{for(n=lo+1;n<hi;n++)print n}' input.txt""",
            False,
        ),
    ],
    19: [
        (r"sed -E 's/^(.+)\1\1$/\1/' input.txt", True),
        (
            r"""awk '{for(n=1;n<=length($0);n++){s=substr($0,1,n);t="";for(i=0;i<length($0);i+=n)t=t s;if(t==$0){print s;break}}}' input.txt""",
            False,
        ),
    ],
    20: [
        (
            r"""factor < input.txt | awk '{for(i=2;i<=NF;i++)count[$i]++} END{for(prime in count)print prime,count[prime]}' | sort -k1,1n""",
            True,
        ),
        (
            r"""sort -u input.txt | factor | cut -d ' ' -f2- | tr ' ' '\n' | sort -n | uniq -c | awk '{print $2,$1}' """.strip(),
            False,
        ),
        (
            r"""factor < input.txt | cut -d ' ' -f2- | tr ' ' '\n' | sort | uniq -c | awk '{print $2,$1}' """.strip(),
            False,
        ),
        (
            r"""factor < input.txt | tr ' ' '\n' | sort -n | uniq -c | awk '{print $2,$1}' """.strip(),
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
