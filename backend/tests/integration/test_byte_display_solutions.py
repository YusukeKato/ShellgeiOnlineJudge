"""UTF-8のbyte表示で、別解と重複・文字単位・書式の誤解を実sandboxで区別する。"""

import asyncio
import os
import uuid
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
        reason="実sandbox実行にはSOJ_RUN_DOCKER_TESTS=1の明示指定が必要",
    ),
]
PROBLEMS = Path(__file__).resolve().parents[3] / "problems"
PROBLEM_ID = "PRACTICE-od-01"


def test_byte_display_solutions_and_common_mistakes_in_real_sandboxes() -> None:
    # 参照解・10進byte経由の別解を受理し、正常終了する6種類の誤答を拒否する。
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    cases = [
        (
            "reference",
            repository.require(PROBLEM_ID).definition.reference_solution,
            True,
        ),
        (
            "decimal-bytes",
            "od -An -v -tu1 -w1 input.txt | awk '{printf \"%02x\\n\",$1}'",
            True,
        ),
        ("compressed-duplicates", "od -An -tx1 -w1 input.txt | tr -d ' '", False),
        (
            "removed-spaces",
            "tr -d ' ' < input.txt | od -An -v -tx1 -w1 | tr -d ' '",
            False,
        ),
        (
            "unicode-scalars",
            'while IFS= read -r -n1 character; do if [ -n "$character" ]; then '
            "printf '%02x\\n' \"'$character\"; else printf '0a\\n'; fi; done < input.txt",
            False,
        ),
        (
            "removed-newlines",
            "tr -d '\\n' < input.txt | od -An -v -tx1 -w1 | tr -d ' '",
            False,
        ),
        (
            "uppercase-hex",
            "od -An -v -tx1 -w1 input.txt | tr -d ' ' | tr 'a-f' 'A-F'",
            False,
        ),
        ("included-addresses", "od -v -tx1 -w1 input.txt | tr -d ' '", False),
    ]
    # この検査専用のownerに限定し、並行テストのsandboxを回収しない。
    manager = ContainerManager(
        pool_size=1, owner_id=f"soj-byte-display-{uuid.uuid4().hex}"
    )
    client = ShellgeiDockerClient(
        container_manager=manager, max_concurrent=1, problem_repository=repository
    )
    judge = ShellgeiJudge(repository)
    try:
        manager.initialize_pool()
        for case_name, command, accepted in cases:
            execution = asyncio.run(client.run_with_timeout(command, PROBLEM_ID))
            context = (case_name, command, execution)
            assert execution.status is ExecutionStatus.COMPLETED, context
            assert execution.exit_code == 0, context
            assert execution.stderr == "", context
            expected = JudgeVerdict.ACCEPTED if accepted else JudgeVerdict.WRONG_ANSWER
            assert judge.judge(execution, PROBLEM_ID).verdict is expected, context
    finally:
        try:
            manager.shutdown_pool()
        finally:
            client.close()
