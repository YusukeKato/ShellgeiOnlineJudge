"""テキスト問題の回答例・別解と典型的な誤答を実sandboxで判定する。"""

import asyncio
import os
from uuid import uuid4

import pytest

from soj_backend.judge import JudgeVerdict, ShellgeiJudge
from soj_runner.container_manager import ContainerManager
from soj_runner.run_shellgei import ShellgeiDockerClient
from soj_shared.models.execution import ExecutionStatus
from soj_shared.problem_repository import build_problem_repository
from tests.test_rosters_logs_files_and_script import PROBLEMS

pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(
        os.getenv("SOJ_RUN_DOCKER_TESTS") != "1",
        reason="rootless Docker検査の明示指定が必要",
    ),
]


@pytest.mark.parametrize(
    ("problem_id", "alternative", "mistake", "setup", "expected"),
    [
        (
            "PRACTICE-umask-01",
            "read -r mask < input.txt && printf 'memo.txt %03o\\narchive %03o\\n' "
            '"$((0666 & ~8#$mask))" "$((0777 & ~8#$mask))"',
            "read -r mask < input.txt && printf 'memo.txt %03o\\narchive %03o\\n' "
            '"$((0666 - 8#$mask))" "$((0777 - 8#$mask))"',
            "echo 777 > input.txt",
            "memo.txt 000\narchive 000\n",
        ),
        (
            "PRACTICE-wc-04",
            "expand -t 8 input.txt | awk '{if (length > w) w=length} END {print w+0}'",
            "awk 'length > w {w=length} END {print w+0}' input.txt",
            ": > input.txt",
            "0\n",
        ),
        (
            "PRACTICE-cat-05",
            "awk 'length($0) || !empty {print} {empty = (length($0) == 0)}' input.txt",
            "uniq input.txt",
            r"printf '\n\nA\n \n\n\nB\n\n\n' > input.txt",
            "\nA\n \n\nB\n\n",
        ),
        (
            "STANDARD-00000075",
            "awk -F- '{for (p=$1; p<=$2; p++) print p}' input.txt",
            "tr '-' ' ' < input.txt | xargs -n 2 seq | sort -nu",
            r"printf '5-5\n4-6\n' > input.txt",
            "5\n4\n5\n6\n",
        ),
        (
            "PRACTICE-comm-01",
            "awk 'FILENAME==ARGV[1]{seen[$0]=1;next} $0 in seen' second.txt input.txt | sort -u",
            "comm -12 <(sort input.txt) <(sort second.txt)",
            ": > second.txt",
            "",
        ),
        (
            "STANDARD-00000073",
            """awk '{for(i=1;i<=NF;i++)printf "%c",strtonum("0x"$i)}' input.txt | sed -n 's/^WARN //p'""",
            r"tr -d ' \n' < input.txt | basenc --base16 -d | sed -n 's/.*WARN //p'",
            r"printf '57 41\n52 4E 20 20 78 0A\n' > input.txt",
            " x\n",
        ),
        (
            "PRACTICE-test-01",
            ': > data/empty.txt; while IFS= read -r f || [ -n "$f" ]; do '
            'if n=$(stat -c %s -- "$f" 2>/dev/null); then case "$n" in 0) s=EMPTY;; *) s=DATA;; esac; '
            'else s=MISSING; fi; printf \'%s %s\\n\' "$f" "$s"; done < input.txt',
            "sed 's/$/ DATA/' input.txt",
            "printf 'data/blank note.txt' > input.txt",
            "data/blank note.txt DATA\n",
        ),
        (
            "STANDARD-00000074",
            "LC_ALL=C awk '/^@@ / {print n+0, substr($0,4)} {n+=length($0)+1}' input.txt",
            "grep -n '^@@ ' input.txt | sed 's/:@@ / /'",
            r"printf '猫\n\n@@ A\n@@ A\n' > input.txt",
            "5 A\n10 A\n",
        ),
    ],
)
def test_public_and_boundary(
    problem_id: str, alternative: str, mistake: str, setup: str, expected: str
) -> None:
    """公開例を両解法で採点し、重複・警告位置・欠落・行番号・権限の誤解と追加境界を確認する。"""
    repo = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repo.require(problem_id)
    manager = ContainerManager(pool_size=1, owner_id=f"soj-problem-{uuid4().hex}")
    client = ShellgeiDockerClient(
        container_manager=manager, max_concurrent=1, problem_repository=repo
    )
    judge = ShellgeiJudge(repo)
    try:
        manager.initialize_pool()
        for command in (record.definition.reference_solution, alternative, mistake):
            result = asyncio.run(client.run_with_timeout(command, problem_id))
            assert result.status is ExecutionStatus.COMPLETED
            assert result.exit_code == 0 and result.stderr == ""
            assert not result.timed_out and not result.truncated
            if command == mistake:
                assert (
                    judge.judge(result, problem_id).verdict is JudgeVerdict.WRONG_ANSWER
                )
                continue
            assert result.stdout == record.expected_output
            assert judge.judge(result, problem_id).verdict is JudgeVerdict.ACCEPTED
            boundary = asyncio.run(
                client.run_with_timeout(setup + "; " + command, problem_id)
            )
            assert boundary.status is ExecutionStatus.COMPLETED
            assert boundary.exit_code == 0 and boundary.stderr == ""
            assert not boundary.timed_out and not boundary.truncated
            assert boundary.stdout == expected
    finally:
        try:
            manager.shutdown_pool()
        finally:
            client.close()
