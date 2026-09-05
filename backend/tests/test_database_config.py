import os
from pathlib import Path
import subprocess
import sys

import pytest


BACKEND = Path(__file__).resolve().parents[1]


def _import_database(value: str | None) -> subprocess.CompletedProcess[str]:
    """独立processでDB moduleを読み、接続を行わず起動時の設定検証と診断出力を確認する。"""
    environment = dict(os.environ, PYTHONPATH=str(BACKEND))
    environment.pop("DATABASE_OPERATION_TIMEOUT_SECONDS", None)
    environment.pop("DATABASE_URL", None)
    if value is not None:
        environment["DATABASE_URL"] = value
    return subprocess.run(
        [
            sys.executable,
            "-c",
            "import os; from sqlalchemy.engine import make_url; "
            "from soj_backend.database import engine; "
            "assert engine.url == make_url(os.environ['DATABASE_URL']); "
            "print(engine.dialect.name)",
        ],
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


@pytest.mark.parametrize("value", [None, "", " \t\n"])
def test_database_configuration_requires_an_explicit_url(value: str | None) -> None:
    # 未設定・空・空白だけのURLでは既定DBへ接続せず、import時点で起動を拒否する。
    result = _import_database(value)
    assert result.returncode != 0
    assert "DATABASE_URL must be explicitly configured" in result.stderr
    assert not result.stdout


@pytest.mark.parametrize(
    "value",
    [
        "postgresql://app:password@db:secret-sentinel/app",
        "unknowndialect://app:secret-sentinel@db/app",
        "not-a-url:secret-sentinel",
    ],
)
def test_invalid_database_url_does_not_expose_credentials(value: str) -> None:
    # 不正なport・driverの例外からURLやpasswordを起動logへ流さない。
    result = _import_database(value)
    assert result.returncode != 0
    assert "check DATABASE_URL and driver" in result.stderr
    assert "secret-sentinel" not in result.stdout + result.stderr


@pytest.mark.parametrize(
    "value,dialect",
    [
        ("sqlite:///:memory:", "sqlite"),
        ("postgresql://app:explicit-password@db:5432/app", "postgresql"),
    ],
)
def test_explicit_database_url_initializes_without_connecting(
    value: str, dialect: str
) -> None:
    # 明示SQLiteとPostgreSQLは受理し、engine初期化時には実DB接続を要求しない。
    result = _import_database(value)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == dialect
