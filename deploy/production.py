"""署名検証後にSSH転送されたimageを、既存のrootless本番環境へ反映する。

Python 3.9以降の標準libraryだけを使用する。初回構築や自動DB rollbackは行わない。
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
from typing import Any
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


SERVICES = ("backend", "runner", "frontend", "db", "sandbox")


class DeploymentError(ValueError):
    """内部process出力を含まない、運用者に表示できる固定の失敗理由。"""


def run(*args: str, timeout: int = 120) -> str:
    """外部処理の出力を保持し、DB URL等をjournalへ流さない。非0とtimeoutは例外。"""
    return (
        subprocess.check_output(args, stderr=subprocess.PIPE, timeout=timeout)
        .decode()
        .strip()
    )


def digest(file: Path) -> str:
    """大きいarchiveもメモリへ全量展開せずSHA-256を求める。"""
    result = hashlib.sha256()
    with file.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def read_record(incoming: Path, sha: str) -> dict[str, Any]:
    """転送後のarchive hashと固定image ID、検査されたcommitの一致を確認する。"""
    record = json.loads((incoming / "build-record.json").read_text())
    if (
        not re.fullmatch(r"[0-9a-f]{40}", sha)
        or record["source_commit"] != sha
        or record["worktree_dirty"] is not False
        or set(record["image_ids"]) != set(SERVICES)
        or not all(
            re.fullmatch(r"sha256:[0-9a-f]{64}", value)
            for value in record["image_ids"].values()
        )
        or digest(incoming / "runtime.tar") != record["files"]["runtime.tar"]
    ):
        raise DeploymentError("invalid candidate record or archive")
    return record


def private_directory(path: Path) -> None:
    """事前に用意された本人所有の非公開directory以外への書き込みを拒否する。"""
    info = path.stat()
    if (
        not path.is_dir()
        or path.is_symlink()
        or info.st_uid != os.getuid()
        or info.st_mode & 0o077
    ):
        raise DeploymentError("a private, owned directory is required")


def image_config(image: str) -> dict:
    """daemon上のimmutable image情報を取得する。"""
    return json.loads(run("docker", "image", "inspect", image))[0]


def check_images(record: dict, old_db: str) -> None:
    """scanしたimageとversion、実行architecture、DB major/PGDATAの互換性を確認する。"""
    old = image_config(old_db)
    for name, image in record["image_ids"].items():
        inspected = image_config(image)
        if (
            inspected["Id"] != image
            or inspected["Os"] != "linux"
            or inspected["Architecture"] != old["Architecture"]
            or inspected["Config"]["Labels"].get("org.opencontainers.image.version")
            != record["product_version"]
        ):
            raise DeploymentError("unexpected image identity, architecture or version")
        if name == "db":
            for key in ("PG_MAJOR", "PGDATA"):
                prefix = key + "="
                previous = [
                    item for item in old["Config"]["Env"] if item.startswith(prefix)
                ]
                current = [
                    item
                    for item in inspected["Config"]["Env"]
                    if item.startswith(prefix)
                ]
                if len(previous) != 1 or previous != current:
                    raise DeploymentError(
                        "DB major or data directory changes require manual migration"
                    )


def override_for(record: dict) -> dict:
    """通常のCompose操作も同じimageを使うため、永続するoverrideを作る。"""
    images = record["image_ids"]
    services: dict[str, Any] = {
        name: {"image": images[name], "pull_policy": "never"}
        for name in SERVICES
        if name != "sandbox"
    }
    services["migrate"] = {"image": images["backend"], "pull_policy": "never"}
    services["runner"]["environment"] = {"SANDBOX_IMAGE_ID": images["sandbox"]}
    return {"x-soj-deployment": record["source_commit"], "services": services}


def smoke(url: str) -> None:
    """公開HTTPS経路からsandbox実行とDB保存まで確認する。本文や例外は出力しない。"""
    request = Request(
        url + "/api/v3/submissions",
        data=json.dumps(
            {"shellgei": "printf smoke-ok", "problem_id": "STANDARD-00000001"}
        ).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=30) as response:
        body = json.load(response)
    if not (
        body["api_version"] == 3
        and body["execution"]["status"] == "completed"
        and body["execution"]["exit_code"] == 0
        and body["execution"]["stdout"] == "smoke-ok"
        and body["persistence"] == "saved"
        and type(body["submission_id"]) is int
        and body["submission_id"] > 0
    ):
        raise RuntimeError("sandbox or persistence smoke test failed")


class Deployment:
    """lock取得済みの専用ホストで、停止境界と復旧記録を管理する。"""

    def __init__(self, repository: Path, incoming: Path, backups: Path, sha: str):
        """設定はhost側の.envを使用し、GitHubへ送らない。"""
        self.repository, self.incoming, self.backups, self.sha = (
            repository,
            incoming,
            backups,
            sha,
        )
        self.state = repository / ".soj-deploy"
        self.phase = "preflight"
        self.stopped = False
        self.command: list[str] = []

    def compose(self, *args: str, timeout: int = 120) -> str:
        """候補の固定Compose設定を使う。出力中の秘密情報は外部へ表示しない。"""
        return run(*self.command, *args, timeout=timeout)

    def stage(self, name: str) -> None:
        """journalへ現在の段階だけを記録する。"""
        self.phase = name
        print(f"production deployment: {name}", flush=True)

    def execute(self) -> None:
        """検証→backup→migration→起動の順に更新し、停止後の失敗は後続更新を遮断する。"""
        try:
            self.stage("preflight")
            self.update()
        except BaseException:
            if self.stopped:
                try:
                    (self.state / "FAILED").write_text(
                        json.dumps({"commit": self.sha, "phase": self.phase})
                    )
                except OSError:
                    pass  # disk障害で記録できなくても、受付停止は必ず試みる。
                try:
                    self.compose("stop", "frontend", "backend")
                except Exception:
                    pass  # 障害記録を残す。daemon障害時は運用者が停止状態を確認する。
            raise

    def update(self) -> None:
        """既存DBのある環境だけを更新する。破棄・自動rollback・pruneは実施しない。"""
        if (self.state / "FAILED").exists():
            raise RuntimeError("previous deployment needs manual recovery")
        if os.getuid() == 0:
            raise DeploymentError("run as the rootless Docker owner")
        os.environ["DOCKER_HOST"] = f"unix:///run/user/{os.getuid()}/docker.sock"
        os.environ["DOCKER_SOCKET_PATH"] = f"/run/user/{os.getuid()}/docker.sock"
        info = json.loads(run("docker", "info", "--format", "{{json .}}"))
        if (
            "name=rootless" not in info["SecurityOptions"]
            or info["CgroupVersion"] != "2"
        ):
            raise DeploymentError("rootless Docker with cgroup v2 is required")
        if run("git", "status", "--porcelain"):
            raise DeploymentError("production checkout must be clean")
        override = self.repository / "docker-compose.override.yml"
        if override.exists() and (
            override.is_symlink()
            or not json.loads(override.read_text()).get("x-soj-deployment")
        ):
            raise DeploymentError("an unmanaged Compose override exists")
        record = read_record(self.incoming, self.sha)
        previous_sha = run("git", "rev-parse", "HEAD")
        run("git", "fetch", "origin", "refs/heads/main")
        if run("git", "rev-parse", "FETCH_HEAD") != self.sha:
            self.stage("superseded; no production changes")
            return
        run("git", "merge-base", "--is-ancestor", previous_sha, self.sha)
        # git自体が未追跡fileとの衝突を拒否する。resetや強制checkoutは使用しない。
        previous_command = ["./deploy/rootless-compose.sh", "-f", "docker-compose.yml"]
        if override.exists():
            previous_command += ["-f", str(override)]
        old_config = json.loads(
            run(
                *previous_command,
                "--profile",
                "maintenance",
                "config",
                "--format",
                "json",
            )
        )
        project = old_config["name"]
        previous_command += ["--project-name", project]
        db_id = run(*previous_command, "ps", "-q", "db")
        db = json.loads(run("docker", "inspect", db_id))[0]
        if not db["State"]["Running"]:
            raise DeploymentError("existing production DB must be running")
        old_mounts = [
            m["Name"]
            for m in db["Mounts"]
            if m["Type"] == "volume" and m["Destination"] == "/var/lib/postgresql/data"
        ]
        if old_mounts != [old_config["volumes"]["db_data"]["name"]]:
            raise DeploymentError("existing DB volume does not match Compose")
        run(
            "docker", "load", "--input", str(self.incoming / "runtime.tar"), timeout=900
        )
        check_images(record, db["Image"])
        run("git", "fetch", "origin", "refs/heads/main")
        if run("git", "rev-parse", "FETCH_HEAD") != self.sha:
            self.stage("superseded after image transfer; no service changes")
            return
        backup = self.backups / self.incoming.name
        backup.mkdir(mode=0o700)  # 再試行でも既存backupを上書きしない。
        (backup / "previous-commit").write_text(previous_sha + "\n")
        (backup / "compose.json").write_text(json.dumps(old_config))
        old_images = {
            name: json.loads(
                run(
                    "docker",
                    "inspect",
                    run(*previous_command, "ps", "-q", name),
                )
            )[0]["Image"]
            for name in ("db", "runner", "backend", "frontend")
        }
        old_images["sandbox"] = old_config["services"]["runner"]["environment"][
            "SANDBOX_IMAGE_ID"
        ]
        (backup / "image-ids.json").write_text(json.dumps(old_images))
        shutil.copyfile(self.repository / ".env", backup / ".env")
        if override.exists():
            shutil.copyfile(override, backup / "docker-compose.override.yml")
        run("git", "merge", "--ff-only", self.sha)
        candidate = self.state / "candidate.json"
        candidate.write_text(json.dumps(override_for(record)))
        self.command = [
            "./deploy/rootless-compose.sh",
            "--project-name",
            project,
            "-f",
            "docker-compose.yml",
            "-f",
            str(candidate),
        ]
        config = json.loads(
            self.compose("--profile", "maintenance", "config", "--format", "json")
        )
        data_mounts = [
            (mount["type"], mount["source"], mount["target"])
            for mount in config["services"]["db"]["volumes"]
            if mount["target"] == "/var/lib/postgresql/data"
        ]
        if config["volumes"]["db_data"]["name"] != old_mounts[0] or data_mounts != [
            ("volume", "db_data", "/var/lib/postgresql/data")
        ]:
            raise DeploymentError("candidate must preserve the existing DB volume")
        origin = config["services"]["backend"]["environment"]["SERVER_URL"].rstrip("/")
        parsed = urlsplit(origin)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path
            or parsed.query
            or parsed.fragment
        ):
            raise DeploymentError("SERVER_URL must be a public HTTPS origin")
        # 起動確認は生成物の取り違えも検出する。新設定は運用時の通常Composeにも残す。
        self.stage("stop and backup")
        self.stopped = True
        (self.state / "FAILED").write_text(
            json.dumps({"commit": self.sha, "phase": "in progress"})
        )
        self.compose("stop", "frontend", "backend")
        for name, command in (
            ("database.dump", 'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc'),
            ("roles.sql", 'exec pg_dumpall -U "$POSTGRES_USER" --globals-only'),
        ):
            with (backup / name).open("xb") as output:
                subprocess.run(
                    ["docker", "exec", db_id, "sh", "-c", command],
                    stdout=output,
                    stderr=subprocess.PIPE,
                    check=True,
                    timeout=300,
                )
                output.flush()
                os.fsync(output.fileno())
            if (backup / name).stat().st_size == 0:
                raise DeploymentError("empty database backup")
        candidate.replace(override)
        self.command[-1] = str(override)
        self.stage("database migration")
        self.compose("up", "-d", "--no-build", "--pull", "never", "db")
        self.wait_database()
        self.compose(
            "run",
            "--rm",
            "--no-deps",
            "--pull",
            "never",
            "-T",
            "migrate",
            timeout=300,
        )
        self.stage("start services")
        self.compose(
            "up",
            "-d",
            "--no-build",
            "--pull",
            "never",
            "--wait",
            "--wait-timeout",
            "180",
            timeout=210,
        )
        for name in ("db", "runner", "backend", "frontend"):
            actual = json.loads(
                run("docker", "inspect", self.compose("ps", "-q", name))
            )[0]
            if actual["Image"] != record["image_ids"][name]:
                raise DeploymentError("running image differs from reviewed image")
        self.stage("public smoke test")
        self.wait_smoke(origin)
        (self.state / "current.json").write_text(json.dumps(record))
        (self.state / "FAILED").unlink()
        self.stopped = False
        self.stage("success")
        # 自分の今回のarchiveだけを削除する。旧imageとbackupは運用者が保存期間を管理する。
        (self.incoming / "runtime.tar").unlink()

    def wait_database(self) -> None:
        """新DBの接続受付を最大60秒待ち、起動失敗時にはmigrationを行わない。"""
        for _ in range(30):
            try:
                self.compose(
                    "exec",
                    "-T",
                    "db",
                    "sh",
                    "-c",
                    'pg_isready -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"',
                    timeout=10,
                )
                return
            except subprocess.SubprocessError:
                time.sleep(2)
        raise TimeoutError("database did not become ready")

    def wait_smoke(self, origin: str) -> None:
        """proxy/backendの起動待ちを含め、最大5回の公開経路確認を行う。"""
        for _ in range(5):
            try:
                smoke(origin)
                return
            except Exception:
                time.sleep(5)
        raise RuntimeError("public smoke test failed")


def terminate(signum: int, frame: Any) -> None:
    """systemd停止要求も障害記録と受付停止の対象にする。"""
    raise RuntimeError("deployment interrupted")


def main() -> None:
    """専用directoryのlockを保持して更新する。秘密値を含む例外は表示しない。"""
    os.umask(0o077)
    signal.signal(signal.SIGTERM, terminate)
    try:
        repository, incoming, backups = (Path(value) for value in sys.argv[1:4])
        for directory in (repository / ".soj-deploy", incoming, backups):
            private_directory(directory)
        if (
            repository.resolve() != repository
            or incoming.parent != repository / ".soj-deploy"
        ):
            raise DeploymentError("unexpected deployment paths")
        os.chdir(repository)
        with (repository / ".soj-deploy/lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            Deployment(repository, incoming, backups, sys.argv[4]).execute()
    except DeploymentError as error:
        raise SystemExit(f"Production deployment refused: {error}") from None
    except BaseException:
        raise SystemExit(
            "Production deployment failed; inspect phase and private backup on the host."
        ) from None


if __name__ == "__main__":
    main()
