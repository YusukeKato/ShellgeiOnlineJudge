"""製品versionの正本とAPI・package・imageの宣言が一致することを検証する。"""

import json
import re
import tomllib
from pathlib import Path

from soj_backend.main import app as backend_app
from soj_runner.main import app as runner_app

ROOT = Path(__file__).resolve().parents[2]


def test_product_version_is_consistent() -> None:
    """正本のSemVerと両API・package metadata・全runtimeのOCI labelを照合する。"""
    version = json.loads((ROOT / "backend/soj_shared/version.json").read_text())[
        "version"
    ]
    assert re.fullmatch(r"\d+\.\d+\.\d+", version)
    assert backend_app.openapi()["info"]["version"] == version
    assert runner_app.version == version
    assert (
        tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["poetry"][
            "version"
        ]
        == version
    )
    assert (
        json.loads((ROOT / "frontend/package.json").read_text())["version"] == version
    )
    for path in (
        "backend/Dockerfile",
        "frontend/Dockerfile",
        "deploy/postgres/Dockerfile",
        "deploy/sandbox/Dockerfile",
    ):
        assert (
            f'LABEL org.opencontainers.image.version="{version}"'
            in (ROOT / path).read_text()
        )
