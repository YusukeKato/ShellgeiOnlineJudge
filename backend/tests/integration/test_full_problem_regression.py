import asyncio
import os
from pathlib import Path

import pytest
import yaml

from scripts.container_manager import ContainerManager
from scripts.judge import ShellgeiJudge
from scripts.run_shellgei import ShellgeiDockerClient


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
YAML_DIR = REPOSITORY_ROOT / "problems" / "yaml_data"


def test_all_problem_answers_in_real_sandboxes() -> None:
    manager = ContainerManager(pool_size=1)
    client = ShellgeiDockerClient(container_manager=manager, max_concurrent=1)
    client.base_dir = REPOSITORY_ROOT
    judge = ShellgeiJudge()
    judge.base_dir = REPOSITORY_ROOT
    manager.initialize_pool()
    try:
        for yaml_path in sorted(YAML_DIR.glob("*.yaml")):
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            output, image = asyncio.run(
                client.run_with_timeout(
                    data["answer"],
                    yaml_path.stem,
                )
            )
            assert judge.judge(output, image, yaml_path.stem) == "1", yaml_path.name
    finally:
        manager.shutdown_pool()
        client.close()
