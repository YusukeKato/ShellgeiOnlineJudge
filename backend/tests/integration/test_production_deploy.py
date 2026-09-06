"""一時rootless Compose環境で、配備scriptのDB保持・migration・HTTPS確認を通す。"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import uuid

import docker
import pytest
import yaml

from deploy import production
from soj_shared.version import APP_VERSION
from tests.compose_support import ComposeStack, ROOT


pytestmark = [
    pytest.mark.docker,
    pytest.mark.compose_e2e,
    pytest.mark.skipif(
        os.getenv("SOJ_RUN_DOCKER_TESTS") != "1"
        or os.getenv("SOJ_RUN_COMPOSE_E2E") != "1",
        reason="explicit rootless opt-in and prebuilt Compose images required",
    ),
]


@pytest.mark.parametrize("migration_failure", [False, True])
def test_production_update_preserves_db_and_checks_public_execution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, migration_failure: bool
) -> None:
    # Git取得・archive loadだけを省略し、実Compose/DBで成功とmigration失敗の受付停止を確認する。
    assert os.environ["DOCKER_HOST"].startswith("unix://")
    client = docker.from_env(timeout=30)
    stack = None
    try:
        assert "name=rootless" in client.info()["SecurityOptions"]
        project = f"soj-e2e-{uuid.uuid4().hex}"
        stack = ComposeStack(client, tmp_path, project)
        stack.compose("up", "-d", "--no-build", "--pull", "never", "db")
        stack.wait_command("db", ["pg_isready", "-U", "e2e", "-d", "e2e"])
        stack.compose("run", "--rm", "--no-deps", "--pull", "never", "migrate")
        stack.compose(
            "up",
            "-d",
            "--no-build",
            "--pull",
            "never",
            "--wait",
            "--wait-timeout",
            "90",
        )
        before_volume = stack.service("db").attrs["Mounts"][0]["Name"]
        port = stack.service("frontend").attrs["NetworkSettings"]["Ports"]["443/tcp"][
            0
        ]["HostPort"]
        origin = f"https://127.0.0.1:{port}"
        stack.url = origin
        for _ in range(60):
            if stack.request("/api/problems")[0] == 200:
                break
            time.sleep(1)
        else:
            pytest.fail("initial fixture API did not become ready")
        before = stack.submit("printf before-update")
        config = yaml.safe_load((tmp_path / "compose.yml").read_text())
        config["name"] = project
        config["services"]["frontend"]["ports"] = [f"127.0.0.1:{port}:443"]
        (tmp_path / "docker-compose.yml").write_text(yaml.safe_dump(config))
        environment = (
            (tmp_path / "test.env")
            .read_text()
            .replace("SERVER_URL=https://frontend", f"SERVER_URL={origin}")
        )
        if migration_failure:
            admin = next(
                line.partition("=")[2]
                for line in environment.splitlines()
                if line.startswith("MIGRATION_DATABASE_URL=")
            )
            environment = (
                "\n".join(
                    "DATABASE_URL=" + admin
                    if line.startswith("DATABASE_URL=")
                    else line
                    for line in environment.splitlines()
                )
                + "\n"
            )
        (tmp_path / ".env").write_text(environment)
        (tmp_path / "deploy").mkdir()
        shutil.copy(
            ROOT / "deploy/rootless-compose.sh", tmp_path / "deploy/rootless-compose.sh"
        )
        state = tmp_path / ".soj-deploy"
        state.mkdir(mode=0o700)
        incoming = state / "incoming-1-1"
        incoming.mkdir(mode=0o700)
        sha = "a" * 40
        images = {
            name: stack.service(name).image.id
            for name in ("backend", "runner", "frontend", "db")
        }
        images["sandbox"] = client.images.get(os.environ["SANDBOX_IMAGE_ID"]).id
        (incoming / "runtime.tar").write_bytes(b"already loaded fixture images")
        record = {
            "source_commit": sha,
            "worktree_dirty": False,
            "product_version": APP_VERSION,
            "image_ids": images,
            "files": {"runtime.tar": production.digest(incoming / "runtime.tar")},
        }
        (incoming / "build-record.json").write_text(json.dumps(record))
        original_run = production.run

        def run(*args: str, timeout: int = 120) -> str:
            """検査済みのlocal imageを使い、外部Gitとarchive再取得だけを省略する。"""
            if args[0] == "git":
                return sha if args[1] == "rev-parse" else ""
            if args[:2] == ("docker", "load"):
                return ""
            return original_run(*args, timeout=timeout)

        monkeypatch.setattr(production, "run", run)
        monkeypatch.chdir(tmp_path)
        for key in tuple(os.environ):
            monkeypatch.delenv(key)
        for key, value in stack.environment.items():
            monkeypatch.setenv(key, value)
        monkeypatch.setenv("SSL_CERT_FILE", str(tmp_path / "cert.pem"))
        task = production.Deployment(tmp_path, incoming, sha)
        if migration_failure:
            with pytest.raises(subprocess.CalledProcessError):
                task.execute()
            assert (state / "FAILED").is_file()
            assert stack.service("backend").status == "exited"
            assert stack.service("frontend").status == "exited"
        else:
            task.execute()
            assert (
                json.loads((state / "current.json").read_text())["image_ids"] == images
            )
            assert not (state / "FAILED").exists()
            assert (
                stack.submit("printf after-update")["submission_id"]
                > before["submission_id"]
            )
        assert stack.service("db").attrs["Mounts"][0]["Name"] == before_volume
        assert not list(state.rglob("database.dump"))
        assert not list(state.rglob("roles.sql"))
        assert not list(state.rglob(".env"))
    finally:
        if stack is not None:
            stack.close()
            owned = {"label": f"com.docker.compose.project={stack.project}"}
            assert not client.containers.list(all=True, filters=owned)
            assert not client.volumes.list(filters=owned)
        client.close()
