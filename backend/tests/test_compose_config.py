from pathlib import Path

import yaml


COMPOSE_FILE = Path(__file__).resolve().parents[2] / "docker-compose.yml"


def test_all_compose_services_have_bounded_local_logs() -> None:
    compose = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    expected_logging = {
        "driver": "local",
        "options": {
            "max-size": "10m",
            "max-file": "3",
        },
    }

    assert set(compose["services"]) == {"db", "runner", "backend", "frontend"}
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
