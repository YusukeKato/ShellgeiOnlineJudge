"""CIの検査範囲を選び、同じmain commitのCIと署名を検証してからSSHで本番更新を依頼する。"""

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
# 本番側production.pyが前回成功時のarchiveを残す場所。repositoryからの相対path。
TRANSFER_BASIS = ".soj-deploy/basis"
# runtime imageと配備archiveを作るSupply Chainのjob名。
RUNTIME_JOB = "Rootless runtime build and image scan"
# 本番のcurrent.jsonが対象commitへ更新されたことを確認した場合だけ実行するstep名。
# Deployments APIの成功はSuperseded時も記録されるため、配備済みcommitの根拠にしない。
DEPLOY_RECORD_STEP = "Record completed production update"
# Markdownでもimageへcopy・bundleされ得る、または配備処理に含まれるdirectory。
IMAGE_INPUT_PREFIXES = (
    "problems/",
    "frontend/src/",
    "frontend/public/",
    "backend/soj_backend/",
    "backend/soj_runner/",
    "backend/soj_shared/",
    "deploy/",
)


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


def documentation_only(paths: list[str]) -> bool:
    """imageへ入らないMarkdownだけの差分ならTrue。空の差分は判定不能としてFalseにする。"""
    return bool(paths) and all(
        path.endswith(".md") and not path.startswith(IMAGE_INPUT_PREFIXES)
        for path in paths
    )


def changed_paths(base: str, head: str) -> list[str] | None:
    """2 commitのtree差分を返す。SHA不正・履歴不足・Git障害はNone（判定不能）にする。"""
    if not all(re.fullmatch(r"[0-9a-f]{40}", sha) for sha in (base, head)):
        return None
    try:
        result = subprocess.run(
            ["git", "diff", "--no-renames", "--name-only", "-z", base, head, "--"],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return [path for path in result.stdout.split("\0") if path]


def deployed_commit(repo: str) -> str | None:
    """本番更新の完了を確認できた最新のdeploy runのcommitを返す。見つからなければNone。

    deploy workflowはconcurrencyで直列実行されるため、run IDが大きいほど後の更新になる。
    直近30 runに記録がなければ、古い基準を推測せずNoneとして全検査・配備側へ倒す。
    """
    query = urlencode(
        {"branch": "main", "event": "push", "status": "completed", "per_page": 30}
    )
    runs = api(f"repos/{repo}/actions/workflows/deploy.yaml/runs?{query}")[
        "workflow_runs"
    ]
    for run in sorted(runs, key=lambda run: run["id"], reverse=True):
        if (
            run["path"] != ".github/workflows/deploy.yaml"
            or run["head_branch"] != "main"
            or run["event"] != "push"
            or run["head_repository"]["full_name"] != repo
            or not re.fullmatch(r"[0-9a-f]{40}", run["head_sha"])
        ):
            continue
        # 再実行も含め、いずれかのattemptで本番更新を確認できたrunを採用する。
        jobs = api(f"repos/{repo}/actions/runs/{run['id']}/jobs?filter=all")["jobs"]
        if any(
            job["name"] == "deploy"
            and any(
                step["name"] == DEPLOY_RECORD_STEP and step["conclusion"] == "success"
                for step in job.get("steps", [])
            )
            for job in jobs
        ):
            return str(run["head_sha"])
    return None


def deployment_unchanged(repo: str, sha: str) -> bool:
    """配備済みcommitとの差分が文書だけならTrue。基準不明・取得失敗はFalse。"""
    try:
        base = deployed_commit(repo)
    except (KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError):
        print("Deployed commit unavailable; treating the change as deployable.")
        return False
    if base is None:
        print(
            "No confirmed production update found; treating the change as deployable."
        )
        return False
    paths = changed_paths(base, sha)
    if paths is None:
        print(
            "Diff from deployed commit unavailable; treating the change as deployable."
        )
        return False
    return documentation_only(paths)


def runtime_job_succeeded(repo: str, run_id: int) -> bool:
    """Supply Chain runでimage build・検査・archive作成のjobが実行され成功したか。"""
    jobs = api(f"repos/{repo}/actions/runs/{run_id}/jobs")["jobs"]
    return any(
        job["name"] == RUNTIME_JOB and job["conclusion"] == "success" for job in jobs
    )


def scope() -> None:
    """Supply Chainのruntime jobが必要かをGITHUB_OUTPUTへ`runtime=true|false`で書く。

    PRはbase commit、main pushは本番更新を確認できたcommitと比べる。直前のpushと比べると、
    Supersededで未配備のcommitの後に文書だけのcommitが来た場合にimageを作らず、
    未配備のコードを残してしまうためである。週次・手動・判定不能は必要側にする。
    """
    event_name = os.environ.get("GITHUB_EVENT_NAME")
    repo, sha = os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_SHA"]
    unchanged = False
    try:
        if event_name == "pull_request":
            event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
            paths = changed_paths(event["pull_request"]["base"]["sha"], sha)
            unchanged = paths is not None and documentation_only(paths)
        elif event_name == "push" and os.environ.get("GITHUB_REF") == "refs/heads/main":
            unchanged = deployment_unchanged(repo, sha)
    except (KeyError, TypeError, ValueError, OSError):
        unchanged = False
    required = "false" if unchanged else "true"
    print(f"Runtime image verification required: {required}")
    with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:
        output.write(f"runtime={required}\n")


def wait_for_ci() -> None:
    """最大55分待機し、配備が必要なら成功したSupply Chain run IDを後続jobへ渡す。

    配備済みcommitとの差分が文書だけなら出力せず配備をskipする。判定はconcurrencyで
    他の配備が終わった後に行い、Supply Chain開始時の判定より新しい基準を使う。
    配備が必要なのにruntime jobがskipされていれば、archiveがないため失敗させる。
    """
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
            if deployment_unchanged(repo, sha):
                print(
                    "Only documentation changed since the deployed commit; deployment skipped."
                )
                return
            run_id = results[-1]
            assert run_id is not None
            if not runtime_job_succeeded(repo, run_id):
                raise RuntimeError(
                    "deployment requires runtime images; re-run Supply Chain CI for this commit"
                )
            with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:
                output.write(f"run_id={run_id}\n")
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
    """SSM経由のSSHでhost鍵を照合して差分転送し、切断後もsystemdで更新を継続する。"""
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
        transfer_started = time.monotonic()
        # 前回成功時のarchiveを基準に差分だけを送る。基準がなければ全量を送る。
        # 組み立て結果は本番側で署名済みrecordのSHA-256と照合される。
        subprocess.run(
            [
                "rsync",
                "--rsh",
                shlex.join(["ssh", *options, "-p", port]),
                # 同じサイズ・更新時刻の基準fileを無検査で複製せず、常に内容を照合する。
                "--ignore-times",
                f"--copy-dest={repository}/{TRANSFER_BASIS}",
                "--stats",
                str(reports / "runtime.tar"),
                str(reports / "build-record.json"),
                "deploy/production.py",
                f"{user}@{host}:{incoming}/",
            ],
            check=True,
            timeout=900,
        )
        print(
            f"Image transfer completed in {time.monotonic() - transfer_started:.2f}s",
            flush=True,
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
        update_started = time.monotonic()
        subprocess.run([*ssh, shlex.join(launch)], check=True, timeout=2550)
        print(
            f"Host update completed in {time.monotonic() - update_started:.2f}s",
            flush=True,
        )
        # host側でSupersededになっても成功終了するため、成功記録を読み戻して確認する。
        current = subprocess.run(
            [
                *ssh,
                shlex.join(["cat", "--", f"{repository}/.soj-deploy/current.json"]),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if json.loads(current.stdout).get("source_commit") == sha:
            with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:
                output.write("deployed=true\n")
        else:
            print("Production kept another commit; this candidate was not deployed.")


def main() -> None:
    """workflowから必要な段階だけを呼び、秘密値を含む例外を出力しない。"""
    try:
        if sys.argv[1] == "scope":
            scope()
        elif sys.argv[1] == "wait":
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
