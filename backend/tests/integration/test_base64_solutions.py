"""Base64練習の参照解・別解と、復号単位や空白の誤解を実sandboxで検査する。"""

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
PROBLEM_ID = "PRACTICE-base64-01"


def test_base64_solutions_and_common_mistakes_in_real_sandboxes() -> None:
    # 参照解・stdin経由・折り返し除去の別解を受理し、行単位復号・空行や空白の破壊・未復号を拒否する。
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(PROBLEM_ID)
    cases = [
        ("reference", record.definition.reference_solution, JudgeVerdict.ACCEPTED),
        ("stdin", "base64 -d < input.txt", JudgeVerdict.ACCEPTED),
        ("unwrapped", "tr -d '\\n' < input.txt | base64 -d", JudgeVerdict.ACCEPTED),
        (
            "decoded-per-line",
            "while IFS= read -r line; do printf '%s' \"$line\" | base64 -d; done < input.txt",
            JudgeVerdict.EXECUTION_FAILURE,
        ),
        (
            "removed-empty-lines",
            "base64 -d input.txt | sed '/^$/d'",
            JudgeVerdict.WRONG_ANSWER,
        ),
        (
            "squeezed-spaces",
            "base64 -d input.txt | tr -s ' '",
            JudgeVerdict.WRONG_ANSWER,
        ),
        ("still-encoded", "cat input.txt", JudgeVerdict.WRONG_ANSWER),
    ]
    # 専用ownerで、この検査が作成したsandboxだけを終了時に回収する。
    manager = ContainerManager(pool_size=1, owner_id=f"soj-base64-{uuid.uuid4().hex}")
    client = ShellgeiDockerClient(
        container_manager=manager, max_concurrent=1, problem_repository=repository
    )
    judge = ShellgeiJudge(repository)
    try:
        manager.initialize_pool()
        for case_name, command, verdict in cases:
            execution = asyncio.run(client.run_with_timeout(command, PROBLEM_ID))
            context = (case_name, command, execution)
            assert execution.status is ExecutionStatus.COMPLETED, context
            assert judge.judge(execution, PROBLEM_ID).verdict is verdict, context
            if verdict is JudgeVerdict.EXECUTION_FAILURE:
                assert execution.exit_code != 0, context
                assert execution.stderr != "", context
            else:
                assert execution.exit_code == 0, context
                assert execution.stderr == "", context
            if verdict is JudgeVerdict.ACCEPTED:
                assert execution.stdout.encode(
                    "utf-8"
                ) == record.expected_output.encode("utf-8"), context
    finally:
        try:
            manager.shutdown_pool()
        finally:
            client.close()
