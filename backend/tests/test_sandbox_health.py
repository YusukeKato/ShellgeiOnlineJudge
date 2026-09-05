import json
from copy import deepcopy
from typing import Any
from unittest.mock import Mock

import docker
import pytest

from soj_runner.container_manager import INSTANCE_LABEL, MANAGED_LABEL, OWNER_LABEL
from soj_tools.sandbox_health import inspect_health, main


def _client() -> Mock:
    """秘密情報を含むinspect応答を持つ、読み取り専用APIの代役を返す。"""
    client = Mock()
    client.api.info.return_value = {"SecurityOptions": ["name=rootless"]}
    client.api.containers.return_value = [
        {
            "State": "running",
            "Labels": {
                MANAGED_LABEL: "true",
                OWNER_LABEL: "test-owner",
                INSTANCE_LABEL: "test-instance",
            },
        }
        for _ in range(3)
    ]
    client.api.inspect_container.return_value = {
        "Config": {
            "Env": ["SANDBOX_OWNER_ID=test-owner", "RUNNER_SHARED_SECRET=secret-value"],
            "Labels": {"com.docker.compose.service": "runner"},
        },
        "State": {"Status": "running", "Health": {"Status": "healthy"}},
        "RestartCount": 2,
    }
    return client


def test_healthy_snapshot_uses_only_read_apis_and_reports_restart_counter() -> None:
    # 完全poolは正常とし、過去の再起動は異常に固定せず累積値として返す。
    client = _client()
    report = inspect_health(client, "test-owner", "test-runner")
    assert report["status"] == "ok"
    assert report["runner_restarts"] == 2
    assert report["sandbox_count"] == 3
    assert report["instance_count"] == 1
    assert report["issues"] == []
    assert [call[0] for call in client.mock_calls] == [
        "api.info",
        "api.containers",
        "api.inspect_container",
    ]
    client.api.containers.assert_called_once_with(
        all=True,
        filters={"label": [f"{MANAGED_LABEL}=true", f"{OWNER_LABEL}=test-owner"]},
    )


@pytest.mark.parametrize("state", ["exited", "restarting", "paused", "dead"])
def test_inactive_runner_with_sandboxes_alerts(state: str) -> None:
    # runner停止中の残存sandboxを、runner自身へHTTP接続せず検出する。
    client = _client()
    client.api.inspect_container.return_value["State"]["Status"] = state
    report = inspect_health(client, "test-owner", "test-runner")
    assert report["status"] == "alert"
    assert "runner_not_running" in report["issues"]
    assert "sandboxes_without_running_runner" in report["issues"]


@pytest.mark.parametrize("health", ["unhealthy", "starting", "none"])
def test_runner_not_ready_alerts(health: str) -> None:
    # 回収失敗や起動未完了でreadinessが正常でない場合を通知する。
    client = _client()
    client.api.inspect_container.return_value["State"]["Health"]["Status"] = health
    assert (
        "runner_not_healthy"
        in inspect_health(client, "test-owner", "test-runner")["issues"]
    )


def test_missing_runner_preserves_sandbox_count() -> None:
    # runner削除後もowner単位の残存数を返し、監視処理自身は削除しない。
    client = _client()
    client.api.inspect_container.side_effect = docker.errors.NotFound("secret-value")
    report = inspect_health(client, "test-owner", "test-runner")
    assert report["runner_state"] == "missing"
    assert report["sandbox_count"] == 3
    assert "runner_missing" in report["issues"]


@pytest.mark.parametrize("count", [0, 2, 4])
def test_capacity_difference_alerts(count: int) -> None:
    # poolの不足・超過を検出し、起動・補充中の一時的変化もsnapshotとして表す。
    client = _client()
    sample = client.api.containers.return_value[0]
    client.api.containers.return_value = [deepcopy(sample) for _ in range(count)]
    assert (
        "sandbox_capacity_mismatch"
        in inspect_health(client, "test-owner", "test-runner")["issues"]
    )


def test_stopped_sandbox_and_mixed_instances_alert() -> None:
    # 削除失敗による停止containerと旧instanceの混在を集計する。
    client = _client()
    client.api.containers.return_value[0]["State"] = "exited"
    client.api.containers.return_value[0]["Labels"][INSTANCE_LABEL] = "old-instance"
    report = inspect_health(client, "test-owner", "test-runner")
    assert report["sandbox_not_running"] == 1
    assert report["instance_count"] == 2
    assert {"sandbox_not_running", "mixed_sandbox_instances"} <= set(report["issues"])


@pytest.mark.parametrize("change", ["owner", "service", "instance", "state", "restart"])
def test_unverifiable_snapshot_is_rejected(change: str) -> None:
    # 別環境のrunnerや欠損metadataを正常扱いしない。
    client = _client()
    runner = client.api.inspect_container.return_value
    if change == "owner":
        runner["Config"]["Env"] = ["SANDBOX_OWNER_ID=other-owner"]
    elif change == "service":
        runner["Config"]["Labels"]["com.docker.compose.service"] = "backend"
    elif change == "instance":
        del client.api.containers.return_value[0]["Labels"][INSTANCE_LABEL]
    elif change == "state":
        client.api.containers.return_value[0]["State"] = "unknown"
    else:
        runner["RestartCount"] = -1
    with pytest.raises(ValueError):
        inspect_health(client, "test-owner", "test-runner")


def test_rootful_daemon_is_rejected_before_container_access() -> None:
    # rootless確認に失敗した場合はcontainer情報も取得しない。
    client = _client()
    client.api.info.return_value = {"SecurityOptions": []}
    with pytest.raises(ValueError):
        inspect_health(client, "test-owner", "test-runner")
    client.api.containers.assert_not_called()
    client.api.inspect_container.assert_not_called()


@pytest.mark.parametrize("host", ["", "tcp://localhost:2375", "unix://relative"])
def test_cli_rejects_implicit_or_remote_daemon(
    monkeypatch: pytest.MonkeyPatch, capsys: Any, host: str
) -> None:
    # DOCKER_HOST未指定やTCP・相対pathは、接続前に固定errorで拒否する。
    monkeypatch.setenv("DOCKER_HOST", host)
    factory = Mock()
    monkeypatch.setattr("soj_tools.sandbox_health.docker.DockerClient", factory)
    assert main([]) == 2
    factory.assert_not_called()
    assert json.loads(capsys.readouterr().out)["status"] == "error"


@pytest.mark.parametrize("failure", [None, "unhealthy", "daemon"])
def test_cli_returns_exit_status_and_never_prints_inspect_or_exception(
    monkeypatch: pytest.MonkeyPatch, capsys: Any, failure: str | None
) -> None:
    # 正常0・異常1・確認不能2を区別し、秘密情報や内部例外を出力せずclientをcloseする。
    client = _client()
    if failure == "unhealthy":
        client.api.inspect_container.return_value["State"]["Health"]["Status"] = failure
    elif failure == "daemon":
        client.api.containers.side_effect = RuntimeError("secret-value /host/path")
    factory = Mock(return_value=client)
    monkeypatch.setenv("DOCKER_HOST", "unix:///run/user/1000/docker.sock")
    monkeypatch.setattr("soj_tools.sandbox_health.docker.DockerClient", factory)
    assert (
        main(["--owner", "test-owner", "--runner-container", "test-runner"])
        == {None: 0, "unhealthy": 1, "daemon": 2}[failure]
    )
    factory.assert_called_once_with(
        base_url="unix:///run/user/1000/docker.sock", timeout=5
    )
    output = capsys.readouterr()
    assert "secret-value" not in output.out + output.err
    assert "/host/path" not in output.out + output.err
    assert "test-instance" not in output.out
    json.loads(output.out)
    client.close.assert_called_once()


@pytest.mark.parametrize("field", ["owner", "runner-container"])
def test_cli_invalid_identity_never_connects(
    monkeypatch: pytest.MonkeyPatch, capsys: Any, field: str
) -> None:
    # owner/nameの不正値はDocker接続前に拒否し、入力値をreportへ反映しない。
    monkeypatch.setenv("DOCKER_HOST", "unix:///run/user/1000/docker.sock")
    factory = Mock()
    monkeypatch.setattr("soj_tools.sandbox_health.docker.DockerClient", factory)
    assert main([f"--{field}", "/invalid-private-path"]) == 2
    factory.assert_not_called()
    assert "/invalid-private-path" not in capsys.readouterr().out


def test_import_does_not_initialize_runtime_manager_with_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 監視専用CLIは不正なowner環境変数でも起動し、tracebackではなく設定errorを返す。
    import os
    import subprocess
    import sys

    monkeypatch.setenv("SANDBOX_OWNER_ID", "/invalid-private-path")
    environment = {**os.environ, "PYTHONPATH": "backend"}
    result = subprocess.run(
        [sys.executable, "-m", "soj_tools.sandbox_health"],
        env=environment,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert result.returncode == 2
    assert json.loads(result.stdout)["issues"] == ["invalid_configuration"]
    assert result.stderr == ""


@pytest.mark.parametrize("failure", ["constructor", "rootful", "close"])
def test_cli_connection_and_close_failures_are_sanitized(
    monkeypatch: pytest.MonkeyPatch, capsys: Any, failure: str
) -> None:
    # 接続・daemon確認・closeの失敗を正常とせず、固定errorへ変換する。
    monkeypatch.setenv("DOCKER_HOST", "unix:///run/user/1000/docker.sock")
    client = _client()
    factory = Mock(return_value=client)
    if failure == "constructor":
        factory.side_effect = RuntimeError("secret-value")
    elif failure == "rootful":
        client.api.info.return_value = {"SecurityOptions": ["name=seccomp"]}
    else:
        client.close.side_effect = RuntimeError("secret-value")
    monkeypatch.setattr("soj_tools.sandbox_health.docker.DockerClient", factory)
    assert main(["--owner", "test-owner"]) == 2
    output = capsys.readouterr()
    assert "secret-value" not in output.out + output.err
    assert json.loads(output.out)["issues"] == ["inspection_failed"]
