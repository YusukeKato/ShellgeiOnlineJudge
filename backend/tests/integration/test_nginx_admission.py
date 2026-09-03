import json
import os
import shutil
import socket
import ssl
import subprocess
import time
import uuid
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import docker
import pytest


pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(
        os.getenv("SOJ_RUN_DOCKER_TESTS") != "1",
        reason="set SOJ_RUN_DOCKER_TESTS=1 on an isolated Docker test host",
    ),
]

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_NGINX_CONFIG = REPOSITORY_ROOT / "frontend" / "nginx" / "default.conf"
NGINX_IMAGE = "nginx:alpine"


def _available_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind(("127.0.0.1", 0))
        return int(server_socket.getsockname()[1])


def _generate_test_certificate(directory: Path) -> tuple[Path, Path]:
    openssl = shutil.which("openssl")
    if openssl is None:
        pytest.skip("openssl is required for the nginx integration test")

    certificate = directory / "fullchain.pem"
    private_key = directory / "privkey.pem"
    subprocess.run(
        [
            openssl,
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-sha256",
            "-nodes",
            "-days",
            "1",
            "-keyout",
            str(private_key),
            "-out",
            str(certificate),
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=DNS:localhost,IP:127.0.0.1",
        ],
        check=True,
        capture_output=True,
    )
    return certificate, private_key


def _request_result(
    url: str,
    request: Request,
    context: ssl.SSLContext,
) -> tuple[int, Message]:
    try:
        with urlopen(request, context=context, timeout=2) as response:
            return response.status, response.headers
    except HTTPError as exc:
        return exc.code, exc.headers
    except URLError as exc:
        raise AssertionError(f"nginx request failed: {exc}") from exc


def _request_status(url: str, request: Request, context: ssl.SSLContext) -> int:
    return _request_result(url, request, context)[0]


def test_non_executing_requests_do_not_consume_a_shared_nginx_start_budget(
    tmp_path: Path,
) -> None:
    certificate, private_key = _generate_test_certificate(tmp_path)
    backend_config = tmp_path / "backend.conf"
    backend_config.write_text(
        """server {
    listen 8000;
    location / {
        add_header X-SOJ-Upstream-Host $http_host always;
        add_header X-SOJ-Upstream-Forwarded $http_forwarded always;
        add_header X-SOJ-Upstream-X-Forwarded-For $http_x_forwarded_for always;
        add_header X-SOJ-Upstream-X-Forwarded-Host $http_x_forwarded_host always;
        add_header X-SOJ-Upstream-X-Forwarded-Port $http_x_forwarded_port always;
        add_header X-SOJ-Upstream-X-Forwarded-Proto $http_x_forwarded_proto always;
        add_header X-SOJ-Upstream-X-Real-IP $http_x_real_ip always;
        return 204;
    }
}
""",
        encoding="utf-8",
    )

    suffix = uuid.uuid4().hex
    network_name = f"soj-nginx-admission-{suffix}"
    backend_name = f"soj-nginx-backend-{suffix}"
    frontend_name = f"soj-nginx-frontend-{suffix}"
    host_port = _available_loopback_port()
    client = docker.from_env(timeout=15)
    containers = []
    network = None
    try:
        assert "name=rootless" in client.info().get("SecurityOptions", [])
        network = client.networks.create(network_name, driver="bridge")
        backend = client.containers.create(
            NGINX_IMAGE,
            name=backend_name,
            volumes={
                str(backend_config): {
                    "bind": "/etc/nginx/conf.d/default.conf",
                    "mode": "ro",
                }
            },
        )
        containers.append(backend)
        network.connect(backend, aliases=["backend"])
        backend.start()
        frontend = client.containers.run(
            NGINX_IMAGE,
            detach=True,
            name=frontend_name,
            network=network_name,
            ports={"443/tcp": ("127.0.0.1", host_port)},
            volumes={
                str(FRONTEND_NGINX_CONFIG): {
                    "bind": "/etc/nginx/conf.d/default.conf",
                    "mode": "ro",
                },
                str(certificate): {
                    "bind": "/etc/nginx/tls/fullchain.pem",
                    "mode": "ro",
                },
                str(private_key): {
                    "bind": "/etc/nginx/tls/privkey.pem",
                    "mode": "ro",
                },
            },
        )
        containers.append(frontend)

        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        url = f"https://127.0.0.1:{host_port}/api/shellgei"
        deadline = time.monotonic() + 10
        while True:
            try:
                status = _request_status(url, Request(url, method="GET"), context)
                break
            except AssertionError:
                if time.monotonic() >= deadline:
                    raise AssertionError(
                        frontend.logs().decode("utf-8", errors="replace")
                    )
                time.sleep(0.05)
        assert status == 204

        boundary_status, boundary_headers = _request_result(
            url,
            Request(
                url,
                method="GET",
                headers={
                    "Host": "attacker.invalid",
                    "Forwarded": "host=attacker.invalid;proto=http",
                    # RFC 5737の文書・テスト専用範囲TEST-NET-2で偽装client IPを表す。
                    "X-Forwarded-For": "198.51.100.10",
                    "X-Forwarded-Host": "attacker.invalid",
                    "X-Forwarded-Port": "80",
                    "X-Forwarded-Proto": "http",
                    "X-Real-IP": "198.51.100.10",
                },
            ),
            context,
        )
        assert boundary_status == 204
        assert boundary_headers["X-SOJ-Upstream-Host"] == "backend:8000"
        for header in (
            "X-SOJ-Upstream-Forwarded",
            "X-SOJ-Upstream-X-Forwarded-For",
            "X-SOJ-Upstream-X-Forwarded-Host",
            "X-SOJ-Upstream-X-Forwarded-Port",
            "X-SOJ-Upstream-X-Forwarded-Proto",
            "X-SOJ-Upstream-X-Real-IP",
        ):
            assert header not in boundary_headers

        requests = [
            Request(url, method="GET"),
            Request(
                url,
                method="OPTIONS",
                headers={
                    "Origin": "https://example.com",
                    "Access-Control-Request-Method": "POST",
                },
            ),
            Request(
                url,
                data=b"{",
                method="POST",
                headers={"Content-Type": "application/json"},
            ),
            Request(
                url,
                data=json.dumps(
                    {"shellgei": "true", "problem_id": "MISSING-00000001"}
                ).encode("utf-8"),
                method="POST",
                headers={"Content-Type": "application/json"},
            ),
            Request(
                url,
                data=json.dumps(
                    {"shellgei": "printf ok", "problem_id": "STANDARD-00000001"}
                ).encode("utf-8"),
                method="POST",
                headers={"Content-Type": "application/json"},
            ),
        ]
        requests.extend(Request(url, method="GET") for _ in range(5))

        statuses = [_request_status(url, request, context) for request in requests]

        assert statuses == [204] * len(requests)
    finally:
        for container in reversed(containers):
            try:
                container.remove(force=True)
            except docker.errors.DockerException:
                pass
        if network is not None:
            try:
                network.remove()
            except docker.errors.DockerException:
                pass
        client.close()
