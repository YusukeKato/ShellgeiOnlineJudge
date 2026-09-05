import ast
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "package,forbidden",
    [
        (
            "soj_shared",
            {
                "soj_backend",
                "soj_runner",
                "soj_tools",
                "docker",
                "sqlalchemy",
                "psycopg2",
                "fastapi",
                "starlette",
                "PIL",
            },
        ),
        ("soj_backend", {"soj_runner", "soj_tools", "docker"}),
        ("soj_runner", {"soj_backend", "soj_tools", "sqlalchemy", "psycopg2", "PIL"}),
    ],
)
def test_runtime_packages_preserve_dependency_direction(
    package: str, forbidden: set[str]
) -> None:
    # 全moduleを走査し、共有から専用実装への逆依存や、反対側runtimeへの依存を防ぐ。
    directory = ROOT / "backend" / package
    assert (directory / "__init__.py").is_file()
    for path in directory.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                imports = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                imports = [node.module or ""]
            else:
                continue
            assert not {name.split(".")[0] for name in imports} & (
                forbidden | {"scripts", "models", "api", "migrations"}
            ), path


def test_runtime_dockerfile_copies_whole_responsibility_packages() -> None:
    # 新moduleを追加してもCOPY列挙を増やさずに済み、開発toolやlegacy scriptは収録しない。
    text = (ROOT / "backend/Dockerfile").read_text()
    for package in ("soj_shared", "soj_backend", "soj_runner"):
        assert f"COPY backend/{package}/ ./{package}/" in text
    assert "COPY backend/scripts" not in text
    assert "COPY backend/models" not in text
    assert "COPY backend/soj_tools" not in text
    assert '"soj_backend.main:app"' in text
    assert '"soj_runner.main:app"' in text
