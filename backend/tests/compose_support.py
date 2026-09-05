"""本番Composeの制約を使い、専用projectだけを操作するE2E補助。"""

import json
import os
import re
import ssl
import subprocess
import time
import urllib.error
import urllib.request
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from scripts.container_manager import OWNER_LABEL


ROOT = Path(__file__).resolve().parents[2]


def isolated_config(
    base: dict[str, Any], project: str, images: dict[str, str]
) -> dict[str, Any]:
    """本番制約を複製し、test名・build済みimage・loopback動的portだけを差し替える。"""
    if re.fullmatch(r"soj-e2e-[0-9a-f]{32}", project) is None:
        raise ValueError("a unique E2E project is required")
    if set(base["services"]) != {"db", "backend", "runner", "frontend"} or set(
        images
    ) != {"backend", "runner", "frontend"}:
        raise ValueError("review isolation before adding Compose services")
    # 新しいbind mountやenv fileをtestへ暗黙に持ち込まず、隔離方法のreviewを要求する。
    mounts = {
        "db": [r"db_data:/var/lib/postgresql/data"],
        "backend": [],
        "runner": [r"\$\{DOCKER_SOCKET_PATH:\?[^}]+\}:/run/docker.sock"],
        "frontend": [
            r"\$\{TLS_CERTIFICATE_PATH:-[^}]+\}:/etc/nginx/tls/fullchain.pem:ro",
            r"\$\{TLS_PRIVATE_KEY_PATH:-[^}]+\}:/etc/nginx/tls/privkey.pem:ro",
        ],
    }
    for name, service in base["services"].items():
        volumes = service.get("volumes", [])
        if (
            "env_file" in service
            or (name not in {"db", "frontend"} and service.get("ports"))
            or len(volumes) != len(mounts[name])
            or any(
                not isinstance(value, str) or re.fullmatch(pattern, value) is None
                for pattern, value in zip(mounts[name], volumes)
            )
        ):
            raise ValueError("review isolation before adding mounts or env files")
    for section in ("volumes", "networks"):
        for config in base[section].values():
            if config and (
                config.get("external")
                or "name" in config
                or (
                    section == "volumes"
                    and ("driver" in config or "driver_opts" in config)
                )
            ):
                raise ValueError("E2E resources must be project scoped")
    if base.get("secrets") or base.get("configs"):
        raise ValueError("review isolation before adding secrets or configs")
    result = deepcopy(base)
    for name, service in result["services"].items():
        service["container_name"] = f"{project}-{name}"
        if name in images:
            service.pop("build", None)
            service["image"] = images[name]
    result["services"]["db"]["ports"] = []
    result["services"]["frontend"]["ports"] = ["127.0.0.1::443"]
    return result


class ComposeStack:
    """専用env file・projectと、検証済みrootless clientを保持する一時Compose環境。"""

    def __init__(self, client: Any, directory: Path, project: str) -> None:
        """起動前に設定を隔離する。実行用image未指定・未buildの場合は失敗する。"""
        self.client = client
        self.directory = directory
        self.project = project
        images = {
            name: client.images.get(os.environ[f"SOJ_COMPOSE_{name.upper()}_IMAGE"]).id
            for name in ("backend", "runner", "frontend", "browser")
        }
        self.browser_image = images.pop("browser")
        base = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
        config = isolated_config(base, project, images)
        client.images.get(config["services"]["db"]["image"])
        (directory / "compose.yml").write_text(yaml.safe_dump(config))
        # 呼出元の.env、COMPOSE_*、proxy、DB接続情報を一切継承しない。
        self.environment = {
            key: os.environ[key]
            for key in (
                "PATH",
                "HOME",
                "XDG_RUNTIME_DIR",
                "DOCKER_HOST",
                "DOCKER_CONFIG",
            )
            if key in os.environ
        }
        socket = os.environ["DOCKER_HOST"].removeprefix("unix://")
        gid = (
            client.containers.run(
                images["runner"],
                [
                    "python",
                    "-c",
                    "import os; print(os.stat('/run/docker.sock').st_gid)",
                ],
                user="0:0",
                network_mode="none",
                remove=True,
                read_only=True,
                cap_drop=["ALL"],
                security_opt=["no-new-privileges:true"],
                volumes={socket: {"bind": "/run/docker.sock", "mode": "ro"}},
            )
            .decode()
            .strip()
        )
        assert gid.isdecimal()
        cert, key = directory / "cert.pem", directory / "key.pem"
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-days",
                "1",
                "-subj",
                "/CN=localhost",
                "-addext",
                "subjectAltName=DNS:localhost,DNS:frontend,IP:127.0.0.1",
                "-keyout",
                str(key),
                "-out",
                str(cert),
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        secret = os.urandom(32).hex()
        env = {
            "POSTGRES_USER": "e2e",
            "POSTGRES_DB": "e2e",
            "POSTGRES_PASSWORD": secret,
            "DATABASE_URL": f"postgresql://e2e:{secret}@db:5432/e2e",
            "RUNNER_SHARED_SECRET": secret,
            "SANDBOX_OWNER_ID": project,
            "DOCKER_SOCKET_PATH": socket,
            "DOCKER_SOCKET_GID": gid,
            "TLS_CERTIFICATE_PATH": str(cert),
            "TLS_PRIVATE_KEY_PATH": str(key),
            "SERVER_URL": "https://frontend",
        }
        env_file = directory / "test.env"
        env_file.touch(mode=0o600)
        env_file.write_text("".join(f"{k}={v}\n" for k, v in env.items()))
        self.http = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPSHandler(
                context=ssl.create_default_context(cafile=cert)
            ),
        )
        self.url = ""

    def compose(self, *arguments: str) -> str:
        """rootless確認wrapper経由で専用projectを操作し、秘密情報を失敗出力に含めない。"""
        result = subprocess.run(
            [
                str(ROOT / "deploy/rootless-compose.sh"),
                "--project-name",
                self.project,
                "--env-file",
                str(self.directory / "test.env"),
                "--file",
                str(self.directory / "compose.yml"),
                *arguments,
            ],
            env=self.environment,
            cwd=self.directory,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode:
            raise RuntimeError(
                f"E2E Compose {arguments[0]} failed (exit {result.returncode})"
            )
        return result.stdout

    def service(self, name: str) -> Any:
        """専用projectのservice containerだけを返す。"""
        return self.client.containers.get(f"{self.project}-{name}")

    def wait_command(self, service: str, command: list[str]) -> bytes:
        """一時serviceの復帰を上限付きで待ち、成功した固定commandの出力を返す。"""
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            container = self.service(service)
            if container.status == "running":
                result = container.exec_run(command)
                if result.exit_code == 0:
                    return result.output
            time.sleep(0.5)
        raise TimeoutError(f"E2E {service} did not become ready")

    def wait_runner(self) -> None:
        """runnerの実readiness endpointで受付再開を待つ。"""
        self.wait_command(
            "runner",
            [
                "python",
                "-c",
                "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/internal/ready').read()",
            ],
        )

    def request(
        self, path: str, payload: dict[str, Any] | None = None
    ) -> tuple[int, Any, bytes]:
        """test nginxへTLS検証付きでアクセスし、HTTP errorも検証用の値として返す。"""
        request = urllib.request.Request(
            self.url + path,
            data=None if payload is None else json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            response = self.http.open(request, timeout=40)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, response.headers, response.read()

    def submit(
        self, command: str, problem_id: str = "STANDARD-00000001", expected: int = 200
    ) -> dict[str, Any]:
        """実APIへ提出する。開始前の429だけを待ち直し、実行失敗は再試行で隠さない。"""
        for _ in range(10):
            status, headers, body = self.request(
                "/api/v3/submissions", {"shellgei": command, "problem_id": problem_id}
            )
            if status != 429:
                break
            assert headers["Retry-After"] == "1"
            time.sleep(1)
        assert status == expected, (problem_id, status)
        assert headers["Cache-Control"] == "no-store"
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert re.fullmatch("[0-9a-f]{32}", headers["X-Request-ID"])
        return json.loads(body)

    def sandboxes(self) -> list[Any]:
        """当該test ownerのsandboxのみ列挙し、本番・他testを対象にしない。"""
        return self.client.containers.list(
            all=True, filters={"label": f"{OWNER_LABEL}={self.project}"}
        )

    def close(self) -> None:
        """部分起動やassert失敗でもservice停止・専用sandbox回収・volume削除を試みる。"""
        with ExitStack() as cleanup:
            # stop失敗時もdownによるrunner停止を先に試み、回収中のpool再補充を避ける。
            cleanup.callback(self.remove_sandboxes)
            cleanup.callback(
                self.compose, "down", "--volumes", "--remove-orphans", "--timeout", "20"
            )
            cleanup.callback(self.compose, "stop", "--timeout", "20")

    def remove_sandboxes(self) -> None:
        """runner停止後、所有labelの一致するsandboxをすべて回収する。"""
        with ExitStack() as cleanup:
            for sandbox in self.sandboxes():
                cleanup.callback(sandbox.remove, force=True, v=True)
