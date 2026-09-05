import tomllib
from pathlib import Path


PROJECT_FILE = Path(__file__).resolve().parents[2] / "pyproject.toml"


def test_runtime_dependency_groups_separate_docker_database_and_development() -> None:
    # runtimeごとの直接依存を分離し、開発toolや旧補助packageを本番へ持ち込まない。
    poetry = tomllib.loads(PROJECT_FILE.read_text(encoding="utf-8"))["tool"]["poetry"]
    common = set(poetry["dependencies"]) - {"python"}
    groups = {
        name: set(group["dependencies"]) for name, group in poetry["group"].items()
    }

    assert groups["backend"] == {"sqlalchemy", "psycopg2-binary", "pillow"}
    assert groups["runner"] == {"docker"}
    assert {"pytest", "ruff", "mypy"} <= groups["dev"]
    assert groups["legacy"] == {"gunicorn", "pytz"}
    for name in ("backend", "runner", "dev", "legacy"):
        assert common.isdisjoint(groups[name])
    assert groups["backend"].isdisjoint(groups["runner"])
