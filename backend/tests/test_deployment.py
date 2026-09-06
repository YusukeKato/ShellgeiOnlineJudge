"""CIの配備条件と、本番更新時の停止・migration・復旧境界を検証する。"""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any

import pytest

from ci import deploy as ci
from deploy import production as host


SHA = "a" * 40
REPO = "example/judge"


def workflow_run(**changes: Any) -> dict:
    """同一main SHAで完了したpush runを起点に、API境界条件を作る。"""
    return {
        "id": 10,
        "run_attempt": 1,
        "head_sha": SHA,
        "head_branch": "main",
        "event": "push",
        "path": ".github/workflows/supply_chain.yaml",
        "head_repository": {"full_name": REPO},
        "status": "completed",
        "conclusion": "success",
        **changes,
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"head_sha": "b" * 40},
        {"head_branch": "feature"},
        {"event": "pull_request"},
        {"head_repository": {"full_name": "fork/judge"}},
        {"path": ".github/workflows/other.yaml"},
    ],
)
def test_gate_ignores_unrelated_success(changes: dict) -> None:
    # 同名jobの成功でも別commit・PR・fork・workflowなら配備条件を満たさない。
    assert (
        ci.successful_run([workflow_run(**changes)], REPO, SHA, "supply_chain.yaml")
        is None
    )


@pytest.mark.parametrize(
    "status,conclusion",
    [("completed", "failure"), ("completed", "cancelled"), ("in_progress", None)],
)
def test_gate_does_not_fall_back_to_older_success(
    status: str, conclusion: str | None
) -> None:
    # 新runの失敗または再実行中を、以前の成功で隠さない。
    runs = [workflow_run(), workflow_run(id=11, status=status, conclusion=conclusion)]
    if status == "completed":
        with pytest.raises(RuntimeError):
            ci.successful_run(runs, REPO, SHA, "supply_chain.yaml")
    else:
        assert ci.successful_run(runs, REPO, SHA, "supply_chain.yaml") is None


def test_gate_waits_for_every_workflow_and_emits_runtime_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Python/React/供給網のすべてが同じSHAで成功してからartifact取得元を確定する。
    monkeypatch.setattr(ci, "context", lambda: (REPO, SHA))
    monkeypatch.setattr(ci, "latest_main", lambda *_: True)
    calls = []

    def api(path: str) -> dict:
        """workflowごとに異なるrun IDを返して取り違えを検出する。"""
        calls.append(path)
        workflow = next(name for name in ci.WORKFLOWS if name in path)
        return {
            "workflow_runs": [
                workflow_run(
                    id=20 + ci.WORKFLOWS.index(workflow),
                    path=f".github/workflows/{workflow}",
                )
            ]
        }

    monkeypatch.setattr(ci, "api", api)
    output = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    ci.wait_for_ci()
    assert output.read_text() == "run_id=22\n"
    assert len(calls) == 3
    assert all(f"head_sha={SHA}" in path for path in calls)


def test_superseded_main_does_not_produce_deployment_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # 新しいmainが届いた待機runは、SSH jobを起動するoutputを作らない。
    monkeypatch.setattr(ci, "context", lambda: (REPO, SHA))
    monkeypatch.setattr(ci, "latest_main", lambda *_: False)
    output = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    ci.wait_for_ci()
    assert not output.exists()


def test_attestation_checks_both_subjects_and_source_identity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # artifact hashだけでなく、署名workflow・main・source SHAを両fileで強制する。
    monkeypatch.setattr(ci, "context", lambda: (REPO, SHA))
    calls = []
    monkeypatch.setattr(ci.subprocess, "run", lambda args, **kwargs: calls.append(args))
    ci.verify(tmp_path)
    assert {Path(args[3]).name for args in calls} == {
        "runtime.tar",
        "build-record.json",
    }
    for args in calls:
        assert args[args.index("--source-digest") + 1] == SHA
        assert args[args.index("--source-ref") + 1] == "refs/heads/main"
        assert (
            args[args.index("--signer-workflow") + 1]
            == f"{REPO}/.github/workflows/supply_chain.yaml"
        )
        assert "--deny-self-hosted-runners" in args


def candidate(directory: Path) -> dict:
    """小さい合成archiveで、実hashと5種類のimmutable IDを持つrecordを作る。"""
    archive = directory / "runtime.tar"
    archive.write_bytes(b"synthetic image archive")
    record = {
        "source_commit": SHA,
        "worktree_dirty": False,
        "product_version": "3.0.0",
        "image_ids": {
            name: "sha256:" + hashlib.sha256(name.encode()).hexdigest()
            for name in host.SERVICES
        },
        "files": {"runtime.tar": host.digest(archive)},
    }
    (directory / "build-record.json").write_text(json.dumps(record))
    return record


@pytest.mark.parametrize(
    "variable,value",
    [
        ("DEPLOY_INSTANCE_ID", "host;touch /tmp/unwanted"),
        ("DEPLOY_INSTANCE_ID", "example.com"),
        ("DEPLOY_AWS_REGION", "ap-northeast-1;id"),
        ("DEPLOY_USER", "-oProxyCommand=anything"),
        ("DEPLOY_PORT", "22 -o StrictHostKeyChecking=no"),
        ("DEPLOY_REPOSITORY", "/repo/../elsewhere"),
    ],
)
def test_ssh_configuration_cannot_inject_shell_or_options(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, variable: str, value: str
) -> None:
    # 設定値はshell展開やSSH optionにならず、不正なら接続前に拒否される。
    monkeypatch.setattr(ci, "context", lambda: (REPO, SHA))
    monkeypatch.setattr(ci, "latest_main", lambda *_: True)
    for key, default in {
        "DEPLOY_INSTANCE_ID": "i-0123456789abcdef0",
        "DEPLOY_AWS_REGION": "ap-northeast-1",
        "DEPLOY_USER": "soj",
        "DEPLOY_PORT": "22",
        "DEPLOY_REPOSITORY": "/srv/judge",
    }.items():
        monkeypatch.setenv(key, default)
    monkeypatch.setenv(variable, value)
    calls = []
    monkeypatch.setattr(ci.subprocess, "run", lambda args, **kwargs: calls.append(args))
    with pytest.raises(ValueError):
        ci.transfer(tmp_path)
    assert not calls


@pytest.mark.parametrize("connection_failure", [False, True])
def test_transfer_uses_ssm_for_ssh_and_scp_and_removes_keys(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, connection_failure: bool
) -> None:
    """SSH/SCPとも指定EC2へのSSM経由に固定し、接続失敗時も秘密鍵を回収する。"""
    monkeypatch.setattr(ci, "context", lambda: (REPO, SHA))
    monkeypatch.setattr(ci, "latest_main", lambda *_: True)
    for key, value in {
        "DEPLOY_INSTANCE_ID": "i-0123456789abcdef0",
        "DEPLOY_AWS_REGION": "ap-northeast-1",
        "DEPLOY_USER": "soj",
        "DEPLOY_PORT": "22",
        "DEPLOY_REPOSITORY": "/srv/judge",
        "GITHUB_RUN_ID": "123",
        "GITHUB_RUN_ATTEMPT": "1",
        "DEPLOY_SSH_KEY": "test-private-key",
        "DEPLOY_KNOWN_HOSTS": "test-known-host",
    }.items():
        monkeypatch.setenv(key, value)
    calls = []
    keys = []

    def run(args: list[str], **kwargs: Any) -> None:
        """外部接続を代替し、転送時だけ秘密鍵がmode 600で存在することを検証する。"""
        calls.append(args)
        key = Path(args[args.index("-i") + 1])
        keys.append(key)
        assert key.read_text() == "test-private-key\n"
        assert key.stat().st_mode & 0o777 == 0o600
        assert kwargs["check"] is True
        if connection_failure:
            raise subprocess.CalledProcessError(255, args)

    monkeypatch.setattr(ci.subprocess, "run", run)
    if connection_failure:
        with pytest.raises(subprocess.CalledProcessError):
            ci.transfer(tmp_path)
        assert len(calls) == 1
    else:
        ci.transfer(tmp_path)
        assert [call[0] for call in calls] == ["ssh", "scp", "ssh"]
        assert "systemd-run" in calls[-1][-1]
    for call in calls:
        assert "StrictHostKeyChecking=yes" in call
        assert call[1:3] == ["-F", "/dev/null"]
        assert (
            "ProxyCommand=aws ssm start-session --region ap-northeast-1 "
            "--target i-0123456789abcdef0 --document-name AWS-StartSSHSession "
            "--parameters portNumber=22"
        ) in call
    assert all(not key.exists() for key in keys)


@pytest.mark.parametrize("corruption", ["archive", "commit", "dirty", "tag", "missing"])
def test_candidate_corruption_is_rejected_before_docker(
    tmp_path: Path, corruption: str
) -> None:
    # 破損転送、別commit、未検査tree、mutable tag、image欠落はすべて拒否する。
    record = candidate(tmp_path)
    if corruption == "archive":
        (tmp_path / "runtime.tar").write_bytes(b"tampered")
    elif corruption == "commit":
        record["source_commit"] = "b" * 40
    elif corruption == "dirty":
        record["worktree_dirty"] = True
    elif corruption == "tag":
        record["image_ids"]["db"] = "postgres:latest"
    else:
        del record["image_ids"]["sandbox"]
    (tmp_path / "build-record.json").write_text(json.dumps(record))
    with pytest.raises(ValueError):
        host.read_record(tmp_path, SHA)


@pytest.fixture
def deployment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[host.Deployment, list[str], dict]:
    """外部processだけを置換し、実際の更新分岐・記録file・migration順序を試す。"""
    monkeypatch.setenv("DOCKER_HOST", "unix:///tmp/ci-daemon/docker.sock")
    monkeypatch.setenv("DOCKER_SOCKET_PATH", "/tmp/ci-daemon/docker.sock")
    state = tmp_path / ".soj-deploy"
    state.mkdir()
    incoming = state / "incoming-123-1"
    incoming.mkdir()
    (tmp_path / ".env").write_text("private fixture configuration")
    record = candidate(incoming)
    events: list[str] = []
    controls: dict[str, Any] = {
        "fail": "",
        "rootless": True,
        "dirty": False,
        "latest": SHA,
        "major": "15",
    }
    config = {
        "name": "isolated-test",
        "volumes": {"db_data": {"name": "existing-db"}},
        "services": {
            "db": {
                "volumes": [
                    {
                        "type": "volume",
                        "source": "db_data",
                        "target": "/var/lib/postgresql/data",
                    }
                ]
            },
            "backend": {"environment": {"SERVER_URL": "https://example.invalid"}},
            "runner": {"environment": {"SANDBOX_IMAGE_ID": "sha256:" + "b" * 64}},
        },
    }

    def run(*args: str, **kwargs: Any) -> str:
        """Docker/Git境界でfixtureを返し、停止後の処理順と禁止操作を記録する。"""
        if args[:2] == ("docker", "info"):
            return json.dumps(
                {
                    "SecurityOptions": ["name=rootless"]
                    if controls["rootless"]
                    else [],
                    "CgroupVersion": "2",
                }
            )
        if args[:3] == ("git", "status", "--porcelain"):
            return " M dirty" if controls["dirty"] else ""
        if args[:2] == ("git", "rev-parse"):
            return "b" * 40 if args[-1] == "HEAD" else controls["latest"]
        if args[:1] == ("git",):
            events.append("git " + args[1])
            return ""
        if args[:2] == ("docker", "load"):
            events.append("load")
            return ""
        if args[:3] == ("docker", "image", "inspect"):
            image = args[-1]
            return json.dumps(
                [
                    {
                        "Id": image,
                        "Os": "linux",
                        "Architecture": "amd64",
                        "Config": {
                            "Labels": {"org.opencontainers.image.version": "3.0.0"},
                            "Env": [
                                "PG_MAJOR="
                                + ("15" if image == "old-db" else controls["major"]),
                                "PGDATA=/var/lib/postgresql/data",
                            ],
                        },
                    }
                ]
            )
        if args[:2] == ("docker", "inspect"):
            name = args[-1].removeprefix("container-")
            updated = "up db" in events
            return json.dumps(
                [
                    {
                        "Image": record["image_ids"][name]
                        if updated
                        else "old-" + name,
                        "State": {"Running": True},
                        "Mounts": [
                            {
                                "Type": "volume",
                                "Destination": "/var/lib/postgresql/data",
                                "Name": "existing-db",
                            }
                        ],
                    }
                ]
            )
        if args[0] == "./deploy/rootless-compose.sh":
            if "config" in args:
                return json.dumps(config)
            if "ps" in args:
                return "container-" + args[-1]
            if "stop" in args:
                events.append("stop")
            elif "run" in args:
                events.append("migration")
                if controls["fail"] == "migration":
                    raise subprocess.CalledProcessError(1, args)
            elif "up" in args:
                events.append("up db" if args[-1] == "db" else "up services")
            return ""
        raise AssertionError(args)

    def smoke(url: str) -> None:
        """公開経路の失敗を、DB変更後の復旧境界として再現する。"""
        events.append("smoke")
        if controls["fail"] == "smoke":
            raise RuntimeError("smoke failed")

    monkeypatch.setattr(host, "run", run)
    monkeypatch.setattr(host, "smoke", smoke)
    monkeypatch.setattr(host.time, "sleep", lambda _: None)
    monkeypatch.setattr(host.os, "getuid", lambda: 1000)
    return host.Deployment(tmp_path, incoming, SHA), events, controls


@pytest.mark.parametrize(
    "docker_host", [None, "unix:///tmp/isolated-daemon/docker.sock"]
)
def test_deployment_selects_local_rootless_socket(
    deployment: tuple, monkeypatch: pytest.MonkeyPatch, docker_host: str | None
) -> None:
    """専用socketを保持し、未指定だけ標準socketへ補完してComposeのmount先も揃える。"""
    task, _, _ = deployment
    if docker_host is None:
        monkeypatch.delenv("DOCKER_HOST")
    else:
        monkeypatch.setenv("DOCKER_HOST", docker_host)
    monkeypatch.setenv("DOCKER_SOCKET_PATH", "/wrong/socket")
    task.execute()
    expected = docker_host or "unix:///run/user/1000/docker.sock"
    assert os.environ["DOCKER_HOST"] == expected
    assert os.environ["DOCKER_SOCKET_PATH"] == expected.removeprefix("unix://")


@pytest.mark.parametrize(
    "docker_host", ["", "tcp://localhost:2375", "unix://relative", "unix:///"]
)
def test_deployment_rejects_nonlocal_socket_before_updates(
    deployment: tuple, monkeypatch: pytest.MonkeyPatch, docker_host: str
) -> None:
    """不正な接続先は標準daemonへfallbackせず、Git・image・service変更前に拒否する。"""
    task, events, _ = deployment
    monkeypatch.setenv("DOCKER_HOST", docker_host)
    with pytest.raises(host.DeploymentError, match="local Unix socket"):
        task.execute()
    assert not events


def test_deployment_promotes_exact_images_without_backup(deployment: tuple) -> None:
    # backup先なしで停止→migration→起動→実行/保存確認が成功し、秘密設定を複製しない。
    task, events, _ = deployment
    task.execute()
    assert (
        events.index("stop")
        < events.index("migration")
        < events.index("up services")
        < events.index("smoke")
    )
    current = json.loads((task.state / "current.json").read_text())
    override = json.loads((task.repository / "docker-compose.override.yml").read_text())
    assert override["services"]["migrate"]["image"] == current["image_ids"]["backend"]
    assert (
        override["services"]["runner"]["environment"]["SANDBOX_IMAGE_ID"]
        == current["image_ids"]["sandbox"]
    )
    assert not (task.state / "FAILED").exists()
    assert not (task.incoming / "runtime.tar").exists()
    assert list(task.repository.rglob(".env")) == [task.repository / ".env"]
    assert not list(task.repository.rglob("database.dump"))
    assert not list(task.repository.rglob("roles.sql"))


@pytest.mark.parametrize("failure", ["migration", "smoke"])
def test_failure_stops_acceptance_and_blocks_automatic_retry(
    deployment: tuple, failure: str
) -> None:
    # migration後の失敗でもDBを削除・自動rollbackせず停止記録を残す。
    task, events, controls = deployment
    controls["fail"] = failure
    with pytest.raises((RuntimeError, subprocess.CalledProcessError)):
        task.execute()
    assert events[-1] == "stop"
    assert (task.state / "FAILED").is_file()
    assert not (task.state / "current.json").exists()
    if failure != "smoke":
        assert "up services" not in events
    previous = copy.copy(events)
    task.stopped = False
    with pytest.raises(RuntimeError, match="manual recovery"):
        task.execute()
    assert events == previous


@pytest.mark.parametrize(
    "control,value", [("rootless", False), ("dirty", True), ("major", "16")]
)
def test_unsafe_preflight_never_stops_services(
    deployment: tuple, control: str, value: Any
) -> None:
    # rootful接続・作業tree変更・DB major変更を、既存サービスを停止する前に拒否する。
    task, events, controls = deployment
    controls[control] = value
    with pytest.raises(ValueError):
        task.execute()
    assert "stop" not in events and "migration" not in events
    assert not (task.state / "FAILED").exists()


def test_host_rejects_stale_commit_without_updating_git_or_services(
    deployment: tuple,
) -> None:
    # SSH転送中にmainが進んだ場合、checkoutやDBを古い候補へ更新しない。
    task, events, controls = deployment
    controls["latest"] = "c" * 40
    task.execute()
    assert events == ["git fetch"]


def test_state_write_failure_still_attempts_to_stop_acceptance(
    deployment: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    # disk障害でFAILEDを書けない場合も、例外処理から受付停止が抜け落ちない。
    task, events, _ = deployment
    original = Path.write_text

    def write(path: Path, data: str, *args: Any, **kwargs: Any) -> int:
        """状態記録の書き込みだけを失敗させ、他の事前検証を通過させる。"""
        if path.name == "FAILED":
            raise OSError("fixture disk full")
        return original(path, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", write)
    with pytest.raises(OSError):
        task.execute()
    assert events[-1] == "stop"
    assert "migration" not in events
