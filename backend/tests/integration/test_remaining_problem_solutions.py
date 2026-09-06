"""残りの改訂問題で自然な別解と典型的な誤解を実sandboxの判定へ通す。"""

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
# 正常終了する別解（True）と、今回の入力で区別する誤答（False）。
CASES: dict[str, list[tuple[str, bool]]] = {
    "STANDARD-00000021": [
        (
            """awk '{r="";for(i=length;i;i--)r=r substr($0,i,1);print r==$0?"YES":"NO"}' input.txt""",
            True,
        )
    ],
    "STANDARD-00000024": [
        (
            """awk '$1=="stock"{s[$2]=$3} $1=="order"{o[$2]=$3} END{for(k in o)if(o[k]>s[k])print k,o[k]-s[k]}' input.txt | sort""",
            True,
        ),
        (
            """awk '$1=="stock"{s[$2]=$3} $1=="order"{o[$2]=$3} END{for(k in o)if(k in s && o[k]>s[k])print k,o[k]-s[k]}' input.txt | sort""",
            False,
        ),
    ],
    "STANDARD-00000027": [("""awk '{print $4}' input.txt | sort | head -n1""", False)],
    "STANDARD-00000029": [
        ("""xargs -n4 < input.txt""", True),
        ("""paste -d ' ' - - - < input.txt""", False),
    ],
    "STANDARD-00000030": [
        (
            """sed 'y/ABCDEFGHIJKLMNOPQRSTUVWXYZ/STUVWXYZABCDEFGHIJKLMNOPQR/' input.txt""",
            True,
        )
    ],
    "STANDARD-00000031": [
        (
            """awk '{a[NR]=$1} END{for(d=100;d>0;d--){ok=1;for(i=1;i<=NR;i++)if(a[i]%d)ok=0;if(ok){print d;exit}}}' input.txt""",
            True,
        ),
        ("""sort -n input.txt | head -n1""", False),
    ],
    "STANDARD-00000032": [
        (
            r"""factor < input.txt | awk '{delete row;for(i=2;i<=NF;i++)row[$i]++;for(p in row)if(row[p]>maximum[p])maximum[p]=row[p]} END{m=1;for(p in maximum)for(i=0;i<maximum[p];i++)m*=p;printf "%.0f\n",m}' """.strip(),
            True,
        ),
        ("""sort -n input.txt | tail -n1""", False),
    ],
    "STANDARD-00000034": [
        (
            """while read -r n; do for x in {2..100}; do if ((x**5==n)); then echo "$x";break;fi;done;done < input.txt""",
            True,
        ),
        ("""factor < input.txt | awk '{print $2}'""", False),
    ],
    "STANDARD-00000035": [
        ("""awk '{print;print}' input.txt""", True),
        ("""awk '{print $1;print $1}' input.txt""", False),
    ],
    "STANDARD-00000036": [
        ("""while read -r n; do seq "$n" | sed "s/.*/$n/";done < input.txt""", True),
        ("""awk '{for(i=0;i<s$1;i++)print $1}' input.txt""", False),
    ],
    "STANDARD-00000039": [
        (
            r"""fold -w1 input.txt | cat -n | sort -k2,2 | uniq -u -f1 | sort -k1,1n | awk '{printf "%s",$2} END{print ""}'""",
            True,
        ),
        (r"""fold -w1 input.txt | sort | uniq -u | tr -d '\n'""", False),
    ],
    "STANDARD-00000040": [
        (
            """awk '{for(i=1;i<=length;i++)n[substr($0,i,1)]++} END{print "a",n["a"]+0;print "b",n["b"]+0;print "c",n["c"]+0}' input.txt""",
            True,
        )
    ],
    "STANDARD-00000042": [
        (
            r"""while read -r name count;do printf '%-8s | %4d\n' "$name" "$count";done < input.txt""",
            True,
        ),
        ("""awk '{print $1,"|",$2}' input.txt""", False),
    ],
    "STANDARD-00000045": [
        (
            """awk '{line="";for(i=1;i<=length;i++){c=substr($0,i,1);line=line c c c}for(i=0;i<3;i++)print line}' input.txt""",
            True,
        ),
        ("""sed 's/./&&&/g' input.txt""", False),
    ],
    "STANDARD-00000047": [
        (
            r"""awk '{for(i=1;i<=NF;i++)if($i~/^[0-9]+(\.[0-9]+){3}$/)print $i}' input.txt""",
            True,
        ),
        (r"""grep -oE '[0-9]+(\.[0-9]+){3}' input.txt""", False),
    ],
    "STANDARD-00000048": [
        (
            """awk '{c=substr($0,1,1);n=1;for(i=2;i<=length;i++){d=substr($0,i,1);if(c==d)n++;else{printf "%s%d",c,n;c=d;n=1}}printf "%s%d\\n",c,n}' input.txt""",
            True,
        ),
        (
            r"""fold -w1 input.txt | sort | uniq -c | awk '{printf "%s%d",$2,$1} END{print ""}'""",
            False,
        ),
    ],
    "STANDARD-00000049": [
        (
            """awk '{best="";for(a=1;a<=length;a++)for(n=1;n<=length-a+1;n++){s=substr($0,a,n);r="";for(i=n;i;i--)r=r substr(s,i,1);if(s==r&&n>length(best))best=s}print best}' input.txt""",
            True,
        )
    ],
    "STANDARD-00000051": [
        (
            r"""awk '{printf "%s %.3f\n",$1,$3/$2}' input.txt | sort -k2,2nr -k1,1""",
            False,
        )
    ],
    "PRACTICE-cat-02": [("""cat -b input.txt""", False)],
    "PRACTICE-grep-01": [
        (r"""grep '\.jpg' input.txt""", True),
        ("""grep '.jpg' input.txt""", False),
    ],
    "PRACTICE-grep-02": [
        (r"""grep -e '\.jpg$' -e '\.png$' input.txt""", True),
        (r"""grep -E '\.(jpg|png)' input.txt""", False),
    ],
    "PRACTICE-grep-03": [("""grep -v '.txt' input.txt""", False)],
    "PRACTICE-grep-04": [("""grep '.jpg$' input.txt""", False)],
    "PRACTICE-sed-01": [("""sed 's/XXX/SHELLGEI/' input.txt""", False)],
    "PRACTICE-sed-02": [("""sed 's/XXX/SHELLGEI/;s/YYY/ONLINE/' input.txt""", False)],
    "PRACTICE-sed-04": [("""sed '/[0-9]/d' input.txt""", False)],
    "PRACTICE-sed-05": [("""sed -n '/^[0-9][0-9]*$/p' input.txt""", False)],
    "PRACTICE-sed-06": [(r"""sed 's/\([a-z]*[0-9]\)/\1.jpg/' input.txt""", False)],
    "PRACTICE-sort-01": [("""sort input.txt""", False)],
    "PRACTICE-sort-02": [("""sort -r input.txt""", False)],
    "PRACTICE-sort-03": [("""sort -u input.txt""", False)],
    "PRACTICE-wc-03": [("""wc -c < input.txt""", False)],
}


@pytest.mark.parametrize("problem_id", CASES)
def test_remaining_solutions_and_mistakes(problem_id: str) -> None:
    # 改訂の核に対応する別解・誤答が実際の隔離実行とtyped judgeで区別されることを確認する。
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
        for command, accepted in [
            (repository.require(problem_id).definition.reference_solution, True),
            *CASES[problem_id],
        ]:
            execution = asyncio.run(client.run_with_timeout(command, problem_id))
            assert execution.status is ExecutionStatus.COMPLETED, (command, execution)
            assert execution.exit_code == 0 and execution.stderr == "", (
                command,
                execution,
            )
            assert judge.judge(execution, problem_id).verdict is (
                JudgeVerdict.ACCEPTED if accepted else JudgeVerdict.WRONG_ANSWER
            ), (command, execution)
    finally:
        manager.shutdown_pool()
        client.close()


@pytest.mark.parametrize("number", range(1, 6))
def test_image_lossless_intermediate_and_wrong_geometry(number: int) -> None:
    # MIFF中間画像の別解は正解とし、背景色・寸法・図形の1ピクセル差を不正解にする。
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    pid = f"IMAGE-{number:08d}"
    ref = repository.require(pid).definition.reference_solution
    base = "convert -size 200x200 xc:'#FF0000'"
    variants = [
        (ref.replace(base, base + " miff:- | convert -"), True),
        (ref.replace("#FF0000", "#00FF00"), False),
        (ref.replace("200x200", "201x200"), False),
    ]
    if number > 1:
        old, new = {
            2: ("199,124", "199,125"),
            3: ("100,150", "100,149"),
            4: ("99,99", "100,100"),
            5: ("20*x+14", "20*x+15"),
        }[number]
        variants.append((ref.replace(old, new), False))
    manager = ContainerManager(pool_size=1)
    client = ShellgeiDockerClient(
        container_manager=manager, max_concurrent=1, problem_repository=repository
    )
    try:
        manager.initialize_pool()
        for command, accepted in variants:
            execution = asyncio.run(client.run_with_timeout(command, pid))
            assert (
                execution.status is ExecutionStatus.COMPLETED
                and execution.exit_code == 0
                and not execution.stderr
            ), (command, execution)
            assert ShellgeiJudge(repository).judge(execution, pid).verdict is (
                JudgeVerdict.ACCEPTED if accepted else JudgeVerdict.WRONG_IMAGE
            ), (pid, command)
    finally:
        manager.shutdown_pool()
        client.close()


@pytest.mark.parametrize(
    ("number", "data", "expected"),
    [
        (26, "S..\n.#.\n..G\n", "4\n"),
        (28, "1\n", "1\n"),
        (31, "97\n", "97\n"),
        (31, "12\n18\n30\n42\n66\n", "6\n"),
        (32, "97\n", "97\n"),
        (32, "2\n3\n5\n7\n11\n", "2310\n"),
        (34, "32\n10000000000\n", "2\n100\n"),
        (41, "x 1 6\n3 5 7\n4 9 2\n", "8 1 6\n3 5 7\n4 9 2\n"),
        (48, "zzzzzzzzzzzaz\n", "z11a1z1\n"),
        (50, "7 / 2 =\n-7 / 2 =\n", "7 / 2 = 3\n-7 / 2 = -3\n"),
    ],
)
def test_generalized_reference_boundaries(
    number: int, data: str, expected: str
) -> None:
    # 参照解答が公開fixtureの個数や固定位置に依存せず、検証用の境界値でも正しく動くことを確認する。
    import shlex

    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    pid = f"STANDARD-{number:08d}"
    command = (
        "printf '%s' "
        + shlex.quote(data)
        + " > input.txt; "
        + repository.require(pid).definition.reference_solution
    )
    manager = ContainerManager(pool_size=1)
    client = ShellgeiDockerClient(
        container_manager=manager, max_concurrent=1, problem_repository=repository
    )
    try:
        manager.initialize_pool()
        execution = asyncio.run(client.run_with_timeout(command, pid))
        assert execution.status is ExecutionStatus.COMPLETED, execution
        assert execution.exit_code == 0 and not execution.stderr, execution
        assert execution.stdout == expected
    finally:
        manager.shutdown_pool()
        client.close()
