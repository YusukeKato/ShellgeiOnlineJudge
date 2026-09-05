"""ホストからrootless daemonを読み取り、runnerとsandboxの異常を匿名集計するCLI。"""

import argparse
import json
import os
import re
from typing import Any

import docker

from soj_runner.sandbox_identity import (
    DEFAULT_POOL_SIZE,
    DEFAULT_SANDBOX_OWNER_ID,
    INSTANCE_LABEL,
    MANAGED_LABEL,
    OWNER_LABEL,
    SANDBOX_OWNER_ID_PATTERN,
)


CONTAINER_STATES = {
    "created",
    "restarting",
    "running",
    "removing",
    "paused",
    "exited",
    "dead",
}
HEALTH_STATES = {"healthy", "unhealthy", "starting", "none"}
RUNNER_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")


def inspect_health(client: Any, owner: str, runner_name: str) -> dict[str, Any]:
    """Dockerの読み取りAPIだけを使い固定fieldのsnapshotを返す。確認不能時は例外を送出する。

    listとinspectは非atomicなので、起動・補充・再起動中は一時的なalertになり得る。
    inspect内の環境変数、command、healthcheck出力、例外文字列はreportへ含めない。
    """
    options = client.api.info().get("SecurityOptions")
    if not isinstance(options, list) or "name=rootless" not in options:
        raise ValueError("rootless daemon required")
    sandboxes = client.api.containers(
        all=True,
        filters={"label": [f"{MANAGED_LABEL}=true", f"{OWNER_LABEL}={owner}"]},
    )
    instances = set()
    stopped = 0
    for sandbox in sandboxes:
        labels = sandbox["Labels"]
        instance = labels.get(INSTANCE_LABEL)
        state = sandbox["State"]
        if (
            labels.get(MANAGED_LABEL) != "true"
            or labels.get(OWNER_LABEL) != owner
            or not isinstance(instance, str)
            or not instance
            or state not in CONTAINER_STATES
        ):
            raise ValueError("sandbox metadata unavailable")
        instances.add(instance)
        stopped += state != "running"

    issues = []
    runner_state = "missing"
    runner_health = "none"
    restarts = None
    try:
        runner = client.api.inspect_container(runner_name)
    except docker.errors.NotFound:
        issues.append("runner_missing")
    else:
        config = runner["Config"]
        owners = [
            entry.removeprefix("SANDBOX_OWNER_ID=")
            for entry in config["Env"]
            if entry.startswith("SANDBOX_OWNER_ID=")
        ]
        if config["Labels"].get("com.docker.compose.service") != "runner" or owners != [
            owner
        ]:
            raise ValueError("runner identity does not match configured owner")
        runner_state = runner["State"]["Status"]
        runner_health = runner["State"].get("Health", {}).get("Status", "none")
        restarts = runner["RestartCount"]
        if (
            runner_state not in CONTAINER_STATES
            or runner_health not in HEALTH_STATES
            or type(restarts) is not int
            or restarts < 0
        ):
            raise ValueError("runner metadata unavailable")
        if runner_state != "running":
            issues.append("runner_not_running")
        if runner_health != "healthy":
            issues.append("runner_not_healthy")
    if runner_state != "running" and sandboxes:
        issues.append("sandboxes_without_running_runner")
    if len(sandboxes) != DEFAULT_POOL_SIZE:
        issues.append("sandbox_capacity_mismatch")
    if stopped:
        issues.append("sandbox_not_running")
    if len(instances) > 1:
        issues.append("mixed_sandbox_instances")
    return {
        "status": "alert" if issues else "ok",
        "issues": issues,
        "runner_state": runner_state,
        "runner_health": runner_health,
        "runner_restarts": restarts,
        "sandbox_count": len(sandboxes),
        "sandbox_not_running": stopped,
        "instance_count": len(instances),
    }


def main(argv: list[str] | None = None) -> int:
    """明示したUnix socketを検査しJSONを出力する。正常0・異常1・設定/確認失敗2を返す。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--owner", default=os.getenv("SANDBOX_OWNER_ID", DEFAULT_SANDBOX_OWNER_ID)
    )
    parser.add_argument("--runner-container", default="soj-runner")
    args = parser.parse_args(argv)
    host = os.getenv("DOCKER_HOST", "")
    report: dict[str, Any] = {"status": "error", "issues": ["invalid_configuration"]}
    client = None
    if (
        host.startswith("unix:///")
        and host != "unix:///"
        and SANDBOX_OWNER_ID_PATTERN.fullmatch(args.owner)
        and RUNNER_NAME.fullmatch(args.runner_container)
    ):
        try:
            client = docker.DockerClient(base_url=host, timeout=5)
            report = inspect_health(client, args.owner, args.runner_container)
        except Exception:
            # Docker応答にはsocket pathや内部情報が含まれ得るため、固定codeだけを公開する。
            report = {"status": "error", "issues": ["inspection_failed"]}
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    report = {"status": "error", "issues": ["inspection_failed"]}
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return {"ok": 0, "alert": 1, "error": 2}[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
