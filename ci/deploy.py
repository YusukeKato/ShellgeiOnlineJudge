"""同じmain commitのCIと署名を検証してから、SSHで本番更新を依頼する。"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import time
from typing import Any
from urllib.parse import urlencode


WORKFLOWS = ("fastapi_ci.yaml", "react_ci.yaml", "supply_chain.yaml")


def api(path: str) -> Any:
    """GitHub CLIの認証を使って読み取りAPIを呼ぶ。失敗は成功扱いしない。"""
    return json.loads(subprocess.check_output(["gh", "api", path], timeout=60))


def context() -> tuple[str, str]:
    """main push以外や不正なrepository/SHAを拒否する。"""
    repo, sha = os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_SHA"]
    if (
        os.environ["GITHUB_EVENT_NAME"] != "push"
        or os.environ["GITHUB_REF"] != "refs/heads/main"
        or not re.fullmatch(r"[\w.-]+/[\w.-]+", repo)
        or not re.fullmatch(r"[0-9a-f]{40}", sha)
    ):
        raise ValueError("deployment requires a main push")
    return repo, sha


def successful_run(runs: list[dict], repo: str, sha: str, workflow: str) -> int | None:
    """最新のpush runだけを見る。旧成功runやPR/forkの結果で失敗を隠さない。"""
    candidates = [
        run
        for run in runs
        if run["head_sha"] == sha
        and run["head_branch"] == "main"
        and run["event"] == "push"
        and run["path"] == f".github/workflows/{workflow}"
        and run["head_repository"]["full_name"] == repo
    ]
    if not candidates:
        return None
    latest = max(candidates, key=lambda run: (run["id"], run["run_attempt"]))
    if latest["status"] != "completed":
        return None
    if latest["conclusion"] != "success":
        raise RuntimeError(f"{workflow} did not succeed")
    return int(latest["id"])


def latest_main(repo: str, sha: str) -> bool:
    """待機・転送中に新しいmainが届いた場合、古い候補の配備を止める。"""
    return api(f"repos/{repo}/git/ref/heads/main")["object"]["sha"] == sha


def wait_for_ci() -> None:
    """最大55分待機し、成功したSupply Chain run IDを後続jobへ渡す。"""
    repo, sha = context()
    deadline = time.monotonic() + 55 * 60
    query = urlencode({"branch": "main", "event": "push", "head_sha": sha})
    while time.monotonic() < deadline:
        if not latest_main(repo, sha):
            print("Superseded by a newer main commit; deployment skipped.")
            return
        results = [
            successful_run(
                api(f"repos/{repo}/actions/workflows/{workflow}/runs?{query}")[
                    "workflow_runs"
                ],
                repo,
                sha,
                workflow,
            )
            for workflow in WORKFLOWS
        ]
        if all(results):
            with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:
                output.write(f"run_id={results[-1]}\n")
            return
        time.sleep(20)
    raise TimeoutError("CI did not complete within 55 minutes")


def verify(reports: Path) -> None:
    """署名者・source SHA・main refをarchiveとrecordの両方で強制する。"""
    repo, sha = context()
    for name in ("runtime.tar", "build-record.json"):
        subprocess.run(
            [
                "gh",
                "attestation",
                "verify",
                str(reports / name),
                "--repo",
                repo,
                "--signer-workflow",
                f"{repo}/.github/workflows/supply_chain.yaml",
                "--source-digest",
                sha,
                "--source-ref",
                "refs/heads/main",
                "--deny-self-hosted-runners",
            ],
            check=True,
            timeout=300,
        )


def transfer(reports: Path) -> None:
    """SSM経由のSSHでhost鍵を照合して転送し、切断後もsystemdで更新を継続する。"""
    repo, sha = context()
    if not latest_main(repo, sha):
        print("Superseded by a newer main commit; deployment skipped.")
        return
    host, user = os.environ["DEPLOY_INSTANCE_ID"], os.environ["DEPLOY_USER"]
    region = os.environ["DEPLOY_AWS_REGION"]
    port = os.environ["DEPLOY_PORT"]
    repository = os.environ["DEPLOY_REPOSITORY"]
    if not re.fullmatch(r"i-(?:[0-9a-f]{8}|[0-9a-f]{17})", host):
        raise ValueError("DEPLOY_INSTANCE_ID must be an EC2 instance ID")
    if not re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-[0-9]+", region):
        raise ValueError("invalid AWS region")
    if (
        not re.fullmatch(r"[a-z_][a-z0-9_-]*", user)
        or not port.isdecimal()
        or not 1 <= int(port) <= 65535
    ):
        raise ValueError("invalid SSH user or port")
    if (
        not re.fullmatch(r"/[A-Za-z0-9_./-]+", repository)
        or ".." in Path(repository).parts
    ):
        raise ValueError(
            "deployment paths must be absolute, without spaces or traversal"
        )
    run = os.environ["GITHUB_RUN_ID"] + "-" + os.environ["GITHUB_RUN_ATTEMPT"]
    if not re.fullmatch(r"[0-9]+-[0-9]+", run):
        raise ValueError("invalid run identity")
    incoming = f"{repository}/.soj-deploy/incoming-{run}"
    with tempfile.TemporaryDirectory(prefix="soj-ssh-") as temporary:
        private = Path(temporary) / "key"
        known = Path(temporary) / "known_hosts"
        for file, variable in (
            (private, "DEPLOY_SSH_KEY"),
            (known, "DEPLOY_KNOWN_HOSTS"),
        ):
            value = os.environ[variable].strip()
            if not value:
                raise ValueError(f"{variable} is required")
            file.write_text(value + "\n")
            file.chmod(0o600)
        options = [
            "-F",
            "/dev/null",
            "-i",
            str(private),
            "-o",
            "BatchMode=yes",
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            f"UserKnownHostsFile={known}",
            "-o",
            "ConnectTimeout=20",
            "-o",
            "ServerAliveInterval=15",
            "-o",
            "ServerAliveCountMax=4",
            "-o",
            "ForwardAgent=no",
            "-o",
            "ProxyCommand="
            + shlex.join(
                [
                    "aws",
                    "ssm",
                    "start-session",
                    "--region",
                    region,
                    "--target",
                    host,
                    "--document-name",
                    "AWS-StartSSHSession",
                    "--parameters",
                    f"portNumber={port}",
                ]
            ),
        ]
        ssh = ["ssh", *options, "-p", port, f"{user}@{host}"]
        subprocess.run(
            [*ssh, shlex.join(["mkdir", "-m", "700", "--", incoming])],
            check=True,
            timeout=60,
        )
        subprocess.run(
            [
                "scp",
                *options,
                "-P",
                port,
                str(reports / "runtime.tar"),
                str(reports / "build-record.json"),
                "deploy/production.py",
                f"{user}@{host}:{incoming}/",
            ],
            check=True,
            timeout=900,
        )
        command = [
            "systemd-run",
            "--user",
            "--wait",
            "--collect",
            f"--unit=soj-deploy-{run}",
            "--property=RuntimeMaxSec=2400",
            "--property=UMask=0077",
            "--property=TimeoutStopSec=120",
            "python3",
            f"{incoming}/production.py",
            repository,
            incoming,
            sha,
        ]
        # SSHの非対話loginでもuser systemdのbusを見つけられるようにする。
        launch = [
            "sh",
            "-c",
            'export XDG_RUNTIME_DIR="/run/user/$(id -u)"; exec "$@"',
            "sh",
            *command,
        ]
        subprocess.run([*ssh, shlex.join(launch)], check=True, timeout=2550)


def main() -> None:
    """workflowから必要な段階だけを呼び、秘密値を含む例外を出力しない。"""
    try:
        if sys.argv[1] == "wait":
            wait_for_ci()
        elif sys.argv[1] == "verify":
            verify(Path(sys.argv[2]))
        elif sys.argv[1] == "transfer":
            transfer(Path(sys.argv[2]))
        else:
            raise ValueError("unknown deployment operation")
    except Exception:
        raise SystemExit(
            "Deployment step failed; check CI status, signature or production journal."
        ) from None


if __name__ == "__main__":
    main()
