from pathlib import Path

import yaml


COMPOSE_FILE = Path(__file__).resolve().parents[2] / "docker-compose.yml"


def test_database_is_not_published_to_the_host() -> None:
    # DB管理は内部networkのserviceで行い、loopbackを含むhost portへDBを公開しない。
    compose = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    db = compose["services"]["db"]
    assert not db.get("ports")
    assert db.get("network_mode") != "host"
    assert db["networks"] == ["backend_db"]
    assert compose["networks"]["backend_db"]["internal"] is True


def test_all_compose_services_have_bounded_local_logs() -> None:
    compose = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    expected_logging = {
        "driver": "local",
        "options": {
            "max-size": "10m",
            "max-file": "3",
        },
    }

    assert set(compose["services"]) == {
        "db",
        "runner",
        "backend",
        "frontend",
        "migrate",
    }
    for service in compose["services"].values():
        assert service["logging"] == expected_logging


def test_only_private_runner_receives_the_docker_socket() -> None:
    compose = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    services = compose["services"]

    assert "volumes" not in services["backend"]
    assert (
        "DOCKER_HOST=unix:///run/docker.sock" not in services["backend"]["environment"]
    )
    assert services["runner"]["volumes"] == [
        "${DOCKER_SOCKET_PATH:?Set DOCKER_SOCKET_PATH to the rootless Docker socket}:/run/docker.sock"
    ]
    assert "DOCKER_HOST=unix:///run/docker.sock" in services["runner"]["environment"]
    assert (
        "SANDBOX_OWNER_ID=${SANDBOX_OWNER_ID:-shellgei-online-judge}"
        in services["runner"]["environment"]
    )
    assert "ports" not in services["runner"]
    assert services["runner"]["networks"] == ["backend_runner"]
    assert set(services["backend"]["networks"]) == {
        "frontend_backend",
        "backend_db",
        "backend_runner",
    }
    assert services["frontend"]["networks"] == ["frontend_backend"]
    assert services["db"]["networks"] == ["backend_db"]
    assert compose["networks"]["backend_runner"]["internal"] is True
    assert compose["networks"]["backend_db"]["internal"] is True


def test_runner_secret_is_only_given_to_backend_and_runner() -> None:
    compose = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    services = compose["services"]

    assert all("env_file" not in service for service in services.values())
    assert any(
        value.startswith("RUNNER_SHARED_SECRET=")
        for value in services["backend"]["environment"]
    )
    assert any(
        value.startswith("RUNNER_SHARED_SECRET=")
        for value in services["runner"]["environment"]
    )
    assert all(
        not value.startswith("RUNNER_SHARED_SECRET=")
        for service_name in ("db", "frontend")
        for value in services[service_name].get("environment", [])
    )
    assert all(
        not value.startswith("DATABASE_URL=")
        for value in services["runner"]["environment"]
    )


def test_frontend_defaults_to_loopback_for_outer_admission_control() -> None:
    compose = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))

    assert compose["services"]["frontend"]["ports"] == [
        "${HTTPS_BIND_ADDRESS:-127.0.0.1}:${HTTPS_PORT:-8443}:443"
    ]


def test_backend_database_operations_have_a_bounded_default() -> None:
    compose = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))

    assert (
        "DATABASE_OPERATION_TIMEOUT_SECONDS=${DATABASE_OPERATION_TIMEOUT_SECONDS:-5}"
        in compose["services"]["backend"]["environment"]
    )


def test_private_runner_disables_request_access_logs() -> None:
    # internal requestでも接続元IP等をservice logへ残さないrunner起動optionを確認する。
    compose = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))

    assert "--no-access-log" in compose["services"]["runner"]["command"]


def test_runner_healthcheck_uses_pool_readiness_endpoint() -> None:
    # Composeがrunner processの生存だけでなく、problem dataとpoolの準備完了をhealthcheckする。
    compose = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    healthcheck = compose["services"]["runner"]["healthcheck"]["test"]

    assert "/internal/ready" in healthcheck[-1]
    assert "/internal/health" not in healthcheck[-1]


def test_runtime_services_use_separate_targets_and_read_only_filesystems() -> None:
    # 公開APIとrunnerを別targetでbuildし、両方のroot filesystemと権限を制限する。
    services = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))["services"]

    for name in ("backend", "runner"):
        service = services[name]
        assert service["build"]["target"] == name
        assert service["read_only"] is True
        assert service["cap_drop"] == ["ALL"]
        assert service["security_opt"] == ["no-new-privileges:true"]
        assert service["tmpfs"] == ["/tmp:rw,noexec,nosuid,nodev,size=16M,mode=1777"]
    assert "group_add" not in services["backend"]
    assert services["runner"]["group_add"] == [
        "${DOCKER_SOCKET_GID:?Set DOCKER_SOCKET_GID to the socket group inside the rootless container}"
    ]


def test_migration_credentials_are_only_available_to_manual_maintenance_service() -> (
    None
):
    # 管理URLをbackend/runnerへ渡さず、通常upでmaintenance serviceが起動しないことを確認する。
    services = yaml.safe_load(COMPOSE_FILE.read_text())["services"]
    migrate = services["migrate"]
    assert migrate["profiles"] == ["maintenance"]
    assert migrate["networks"] == ["backend_db"]
    assert migrate["restart"] == "no"
    assert migrate["build"]["target"] == "backend"
    assert (
        migrate["read_only"] and not migrate.get("volumes") and not migrate.get("ports")
    )
    assert "soj_backend.database_admin" in migrate["command"]
    for name in ("backend", "runner", "frontend"):
        assert not any(
            value.startswith("MIGRATION_DATABASE_URL=")
            for value in services[name].get("environment", [])
        )
    assert any(
        value.startswith("MIGRATION_DATABASE_URL=") for value in migrate["environment"]
    )


def test_only_runner_requires_an_explicit_sandbox_image() -> None:
    # image設定をpublic backendへ渡さず、runnerだけで必須化する。
    services = yaml.safe_load(COMPOSE_FILE.read_text())["services"]
    for name, service in services.items():
        values = [
            value
            for value in service.get("environment", [])
            if value.startswith("SANDBOX_IMAGE_ID=")
        ]
        if name == "runner":
            assert values == [
                "SANDBOX_IMAGE_ID=${SANDBOX_IMAGE_ID:?Build sandbox and set its immutable image ID}"
            ]
        else:
            assert values == []
