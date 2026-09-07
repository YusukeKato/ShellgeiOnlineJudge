"""通常53〜60の別解と典型的な誤答を、実sandboxとjudgeで検査する。"""

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
CASES = [
    (
        53,
        "awk '{last[$1]=$0} END{for(k in last)print last[k]}' input.txt | sort",
        "awk '!seen[$1]++' input.txt | sort",
    ),
    (
        54,
        "awk 'NR>1{print $1,$2-prev} {prev=$2}' input.txt",
        "awk 'NR>1{print $1,prev-$2} {prev=$2}' input.txt",
    ),
    (
        55,
        'awk \'$0=="END"{inside=0} inside{print} $0=="BEGIN"{inside=1}\' input.txt',
        "sed -n '/BEGIN/,/END/{/BEGIN/d;/END/d;p;}' input.txt",
    ),
    (
        56,
        "awk 'BEGIN{FS=OFS=\"\\t\"} {print $1,$3}' input.txt",
        "awk 'BEGIN{OFS=\"\\t\"} {print $1,$3}' input.txt",
    ),
    (
        57,
        "awk -F. '{n[tolower($NF)]++} END{for(e in n)print e,n[e]}' input.txt | sort",
        "sed 's/.*\\.//' input.txt | sort | uniq -c | awk '{print $2,$1}'",
    ),
    (
        58,
        'awk \'$1=="team"{people[$2,$3]=1} $1=="file"{files[$2,$3]=1} '
        "END{for(p in people){split(p,a,SUBSEP);for(f in files){split(f,b,SUBSEP);"
        "if(a[1]==b[1])print a[1],a[2],b[2]}}}' input.txt | sort",
        "join <(sed -n 's/^team //p' input.txt | sort -u -k1,1) "
        "<(sed -n 's/^file //p' input.txt | sort) | sort",
    ),
    (
        59,
        "awk '{col=0;for(i=1;i<=length;i++){c=substr($0,i,1);"
        'if(c=="\\t"){n=4-col%4;printf "%s",substr(">>>>",1,n);col+=n}'
        'else{printf "%s",c;col++}}print ""}\' input.txt',
        "sed 's/\t/>>>>/g' input.txt",
    ),
    (
        60,
        "awk '{s[NR]=$2;e[NR]=$3} END{for(t=540;t<=660;t+=10){"
        'k=sprintf("%02d:%02d",t/60,t%60);n=0;'
        "for(i=1;i<=NR;i++)if(s[i]<=k&&k<e[i])n++;print k,n}}' input.txt",
        "awk '{s[NR]=$2;e[NR]=$3} END{for(t=540;t<=660;t+=10){"
        'k=sprintf("%02d:%02d",t/60,t%60);n=0;'
        "for(i=1;i<=NR;i++)if(s[i]<=k&&k<=e[i])n++;print k,n}}' input.txt",
    ),
]


def test_new_standard_solutions_and_mistakes() -> None:
    # 各問の参照解答・別解は正解、初出優先・空白分割・閉区間等の誤解は不正解になる。
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    manager = ContainerManager(pool_size=1)
    client = ShellgeiDockerClient(
        container_manager=manager, max_concurrent=1, problem_repository=repository
    )
    judge = ShellgeiJudge(repository)
    try:
        manager.initialize_pool()
        for number, alternative, mistake in CASES:
            problem_id = f"STANDARD-{number:08}"
            reference = repository.require(problem_id).definition.reference_solution
            commands = [
                (reference, True),
                (alternative, True),
                (mistake, False),
            ]
            if number == 59:
                # 元からあるスペースまで>に変換する誤答を区別する。
                commands.append(("expand -t 4 input.txt | tr ' ' '>'", False))
            if number == 60:
                # 記録に現れる時刻だけの出力と、11:00を落とす出力も区別する。
                commands.extend(
                    [
                        (
                            "awk '{print $2,1;print $3,-1}' input.txt | sort -k1,1 | "
                            "awk 'NR>1&&$1!=t{print t,n} {t=$1;n+=$2} END{print t,n}'",
                            False,
                        ),
                        (reference + " | head -n 12", False),
                    ]
                )
            for command, accepted in commands:
                execution = asyncio.run(client.run_with_timeout(command, problem_id))
                context = (problem_id, command, execution)
                assert execution.status is ExecutionStatus.COMPLETED, context
                assert execution.exit_code == 0, context
                assert execution.stderr == "", context
                expected = (
                    JudgeVerdict.ACCEPTED if accepted else JudgeVerdict.WRONG_ANSWER
                )
                assert judge.judge(execution, problem_id).verdict is expected, context
    finally:
        manager.shutdown_pool()
        client.close()
