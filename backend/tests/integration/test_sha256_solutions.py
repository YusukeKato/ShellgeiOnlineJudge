"""SHA-256の参照解・標準入力の別解と、入力やハッシュ方式の誤りを実sandboxで検査する。"""

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
PROBLEM_ID = "PRACTICE-sha256sum-01"


def test_sha256_solutions_and_common_mistakes_in_real_sandboxes() -> None:
    # 2正解を受理し、末尾LF・全改行・空白の削除、名前付き・大文字・MD5の6誤答を拒否する。
    repository = build_problem_repository(
        PROBLEMS / "v3", PROBLEMS / "image", PROBLEMS / "v3/manifest.json"
    )
    record = repository.require(PROBLEM_ID)
    reference = record.definition.reference_solution
    cases = [
        ("reference", reference, JudgeVerdict.ACCEPTED),
        ("stdin", "sha256sum < input.txt | awk '{print $1}'", JudgeVerdict.ACCEPTED),
        (
            "missing-final-lf",
            "printf '%s' \"$(cat input.txt)\" | sha256sum | cut -d' ' -f1",
            JudgeVerdict.WRONG_ANSWER,
        ),
        (
            "removed-newlines",
            "tr -d '\\n' < input.txt | sha256sum | cut -d' ' -f1",
            JudgeVerdict.WRONG_ANSWER,
        ),
        (
            "removed-space",
            "tr -d ' ' < input.txt | sha256sum | cut -d' ' -f1",
            JudgeVerdict.WRONG_ANSWER,
        ),
        ("included-filename", "sha256sum input.txt", JudgeVerdict.WRONG_ANSWER),
        ("uppercase", reference + " | tr 'a-f' 'A-F'", JudgeVerdict.WRONG_ANSWER),
        ("md5", reference.replace("sha256sum", "md5sum"), JudgeVerdict.WRONG_ANSWER),
    ]
    # 専用ownerのsandboxだけを作成・回収し、並行検証へ干渉しない。
    manager = ContainerManager(pool_size=1, owner_id=f"soj-sha256-{uuid.uuid4().hex}")
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
            assert execution.exit_code == 0, context
            assert execution.stderr == "", context
            assert judge.judge(execution, PROBLEM_ID).verdict is verdict, context
            if verdict is JudgeVerdict.ACCEPTED:
                assert execution.stdout == record.expected_output, context
    finally:
        try:
            manager.shutdown_pool()
        finally:
            client.close()
