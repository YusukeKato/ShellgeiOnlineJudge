import os
import subprocess
from pathlib import Path

import yaml
import pytest


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("reload_failure", [False, True])
def test_rootless_preparation_uses_dropin_before_start(
    tmp_path: Path, reload_failure: bool
) -> None:
    """host操作を代替し、drop-inの内容・reload順序と設定失敗時の停止を検証する。"""
    stub = tmp_path / "stub.sh"
    stub.write_text(
        r"""
id() { if [[ $1 == -u ]]; then echo 1001; else echo runner; fi; }
sudo() {
  echo "$*" >> "$SOJ_TEST_DIR/calls"
  case "$*" in
    *set-property*) return 1 ;;
    'tee /run/systemd/system/user@1001.service.d/soj-delegate.conf')
      cat > "$SOJ_TEST_DIR/dropin" ;;
    'tee /etc/sudoers.d/soj-rootless-dbus') cat > "$SOJ_TEST_DIR/sudoers" ;;
    'systemctl daemon-reload') return "$SOJ_RELOAD_FAILURE" ;;
    '-u #1001 printenv DBUS_SESSION_BUS_ADDRESS') printenv DBUS_SESSION_BUS_ADDRESS ;;
  esac
}
systemctl() { echo "user $*" >> "$SOJ_TEST_DIR/calls"; }
busctl() { :; }
test() {
  if [[ $1 == -S && $2 == /run/user/1001/bus ]]; then return 0; fi
  builtin test "$@"
}
"""
    )
    env = dict(
        os.environ,
        BASH_ENV=str(stub),
        SOJ_TEST_DIR=str(tmp_path),
        SOJ_RELOAD_FAILURE=str(int(reload_failure)),
        GITHUB_ACTIONS="true",
        RUNNER_ENVIRONMENT="github-hosted",
        GITHUB_ENV=str(tmp_path / "github-env"),
    )
    result = subprocess.run(
        ["bash", str(ROOT / "ci/prepare_rootless.sh")], env=env, check=False
    )
    assert result.returncode == int(reload_failure)
    assert (tmp_path / "dropin").read_text() == (
        "[Service]\nDelegate=cpu cpuset io memory pids\n"
    )
    calls = (tmp_path / "calls").read_text()
    assert "set-property" not in calls
    if reload_failure:
        assert "systemctl start" not in calls
        assert not (tmp_path / "github-env").exists()
    else:
        assert calls.index("systemctl daemon-reload") < calls.index(
            "systemctl start user@1001.service"
        )
        assert (tmp_path / "github-env").read_text() == (
            "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1001/bus\n"
        )


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
