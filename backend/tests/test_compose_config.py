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

    assert set(compose["services"]) == {"db", "backend", "frontend"}
    for service in compose["services"].values():
        assert service["logging"] == expected_logging
