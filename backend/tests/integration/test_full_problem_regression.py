import asyncio
import os
from pathlib import Path

import pytest
from scripts.problem_schema import load_problem_definition
from scripts.problem_repository import build_problem_repository
from scripts.container_manager import ContainerManager
from scripts.judge import JudgeVerdict, ShellgeiJudge
from scripts.run_shellgei import ShellgeiDockerClient
from scripts.runner_protocol import ExecutionArtifact


pytestmark = [
    pytest.mark.docker,
    pytest.mark.full_regression,
    pytest.mark.skipif(
        os.getenv("SOJ_RUN_DOCKER_TESTS") != "1"
        or os.getenv("SOJ_RUN_FULL_REGRESSION") != "1",
        reason="explicit isolated-host opt-in is required for full regression",
    ),
]

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
V3_DIRECTORY = REPOSITORY_ROOT / "problems" / "v3"
PROBLEM_REPOSITORY = build_problem_repository(
    V3_DIRECTORY,
    REPOSITORY_ROOT / "problems/image",
    V3_DIRECTORY / "manifest.json",
)


def test_all_problem_answers_in_real_sandboxes() -> None:
    # 全v3問題の参照解答を実sandboxで実行し、typed judgeで正解になることを確認する。
    manager = ContainerManager(pool_size=1)
    client = ShellgeiDockerClient(
        container_manager=manager,
        max_concurrent=1,
        problem_repository=PROBLEM_REPOSITORY,
    )
    judge = ShellgeiJudge(PROBLEM_REPOSITORY)
    manager.initialize_pool()
    try:
        for yaml_path in sorted(V3_DIRECTORY.glob("*.yaml")):
            definition = load_problem_definition(yaml_path)
            output, image = asyncio.run(
                client.run_with_timeout(
                    definition.reference_solution,
                    yaml_path.stem,
                )
            )
            artifact = None
            if definition.judge.type == "image" and image:
                artifact = ExecutionArtifact(
                    path=definition.judge.artifact.path,
                    media_type=definition.judge.artifact.media_type,
                    data=image,
                )
            assert (
                judge.judge(output, artifact, yaml_path.stem).verdict
                is JudgeVerdict.ACCEPTED
            ), yaml_path.name
    finally:
        manager.shutdown_pool()
        client.close()
