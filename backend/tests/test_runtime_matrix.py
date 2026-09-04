import tomllib
from pathlib import Path

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SUPPORTED_PYTHON_VERSIONS = ["3.12", "3.13", "3.14"]


def test_python_support_policy_matches_ci_and_production_image() -> None:
    # pyproject・CI・本番imageが同じPython対応範囲とdigest固定済みの3.12系を使うことを確認する。
    project = tomllib.loads(
        (REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    workflow = yaml.safe_load(
        (REPOSITORY_ROOT / ".github/workflows/fastapi_ci.yaml").read_text(
            encoding="utf-8"
        )
    )
    backend_dockerfile = (REPOSITORY_ROOT / "backend/Dockerfile").read_text(
        encoding="utf-8"
    )

    assert project["tool"]["poetry"]["dependencies"]["python"] == ">=3.12,<3.15"
    assert (
        workflow["jobs"]["linting_and_testing"]["strategy"]["matrix"]["python-version"]
        == SUPPORTED_PYTHON_VERSIONS
    )
    assert backend_dockerfile.startswith("FROM python:3.12-slim@sha256:")
