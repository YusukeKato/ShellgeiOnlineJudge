import os
import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def test_rootless_preparation_rejects_local_execution(tmp_path: Path) -> None:
    """ローカル実行ではsudoに到達せず、ホストのsystemd設定を変更しない。"""
    marker = tmp_path / "sudo-called"
    sudo = tmp_path / "sudo"
    sudo.write_text(f'#!/bin/sh\ntouch "{marker}"\nexit 1\n')
    sudo.chmod(0o700)
    env = dict(os.environ, PATH=f"{tmp_path}:{os.environ['PATH']}")
    env.pop("GITHUB_ACTIONS", None)
    result = subprocess.run(
        ["bash", str(ROOT / "ci/prepare_rootless.sh")],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "only for the GitHub-hosted runner" in result.stderr
    assert not marker.exists()


def test_runtime_prepares_user_bus_before_daemon_and_probes_before_scan() -> None:
    """daemon起動前にuser busを準備し、脆弱性検査前に制限付き起動を検証する。"""
    workflow = yaml.load(
        (ROOT / ".github/workflows/supply_chain.yaml").read_text(),
        Loader=yaml.BaseLoader,
    )
    steps = workflow["jobs"]["runtime"]["steps"]
    prepare = next(
        i
        for i, step in enumerate(steps)
        if "ci/prepare_rootless.sh" in step.get("run", "")
    )
    setup = next(
        i
        for i, step in enumerate(steps)
        if step.get("uses", "").startswith("docker/setup-docker-action@")
    )
    probe = next(
        i
        for i, step in enumerate(steps)
        if "inspect_python_runtime" in step.get("run", "")
    )
    scan = next(i for i, step in enumerate(steps) if step.get("id") == "scan")
    assert prepare < setup < probe < scan
    assert steps[setup]["with"]["rootless"] == "true"
