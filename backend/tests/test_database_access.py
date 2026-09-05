from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, event, inspect

from soj_backend.database_access import (
    provision_runtime_role,
    validate_runtime_database,
)
from soj_backend.database_admin import database_urls, main
from soj_backend.database_migrations import migrate_database


def test_runtime_validation_does_not_initialize_empty_database() -> None:
    # 空DBのbackend起動はmigrationを暗黙実行せず拒否し、表を作成しない。
    engine = create_engine("sqlite:///:memory:")
    with pytest.raises(RuntimeError, match="maintenance"):
        validate_runtime_database(engine)
    assert inspect(engine).get_table_names() == []
    engine.dispose()


def test_runtime_validation_requires_head_and_only_reads() -> None:
    # 明示migration後だけ起動可能とし、schema確認はSELECTに限定する。
    engine = create_engine("sqlite:///:memory:")
    migrate_database(engine, "0001_legacy_execution_logs")
    with pytest.raises(RuntimeError):
        validate_runtime_database(engine)
    migrate_database(engine)
    statements = []

    def record(_conn, _cursor, statement, _params, _context, _many):
        """検証中のSQLだけを記録し、DDL/DMLの再導入を検出する。"""
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    validate_runtime_database(engine)
    assert statements and all(value.startswith("SELECT") for value in statements)
    engine.dispose()


@pytest.mark.parametrize(
    "app",
    [
        "postgresql://admin:app-pass@db/app",
        "postgresql://app:admin-pass@db/app",
        "postgresql://app:app-pass@other/app",
        "postgresql://app:app-pass@db/other",
        "postgresql://app:app-pass@db/app?options=x",
        "sqlite:///:memory:",
        "postgresql://app@db/app",
        "postgresql://app:app-pass@db:5433/app",
    ],
)
def test_management_urls_reject_shared_credentials_or_different_database(
    monkeypatch, app
):
    # 同じDBの別credential以外を拒否し、誤ったDBへの権限設定を防ぐ。
    monkeypatch.setenv("MIGRATION_DATABASE_URL", "postgresql://admin:admin-pass@db/app")
    monkeypatch.setenv("DATABASE_URL", app)
    with pytest.raises(ValueError):
        database_urls()


def test_management_urls_accept_encoded_password_and_default_port(monkeypatch):
    # URL予約文字を含む独立passwordと明示/既定portの同一性を扱う。
    monkeypatch.setenv("MIGRATION_DATABASE_URL", "postgresql://admin:admin-pass@db/app")
    monkeypatch.setenv("DATABASE_URL", "postgresql://app:app%40pass@db:5432/app")
    _, app = database_urls()
    assert app.password == "app@pass"


@pytest.mark.parametrize("role", ["admin;DROP ROLE x", "pg_reserved", "", "A" * 64])
def test_role_validation_precedes_database_changes(role):
    # role識別子の不正値はtransaction開始前に拒否する。
    engine = Mock()
    with pytest.raises(ValueError):
        provision_runtime_role(engine, role, "password")
    engine.begin.assert_not_called()


def test_maintenance_cli_sanitizes_connection_failure(monkeypatch, capsys):
    # SQLAlchemy例外やURL内のsecretをCLIへ露出しない。
    monkeypatch.setenv("MIGRATION_DATABASE_URL", "postgresql://admin:admin-pass@db/app")
    monkeypatch.setenv("DATABASE_URL", "postgresql://app:app-pass@db/app")
    monkeypatch.setattr(
        "soj_backend.database_admin.create_engine",
        Mock(side_effect=RuntimeError("admin-pass private-host")),
    )
    assert main([]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "admin-pass" not in captured.err
    assert "private-host" not in captured.err


def test_maintenance_cli_sanitizes_disposal_failure(monkeypatch, capsys):
    # 管理処理後の接続pool破棄失敗でもsecretやtracebackを出力せず、成功を報告しない。
    monkeypatch.setenv("MIGRATION_DATABASE_URL", "postgresql://admin:admin-pass@db/app")
    monkeypatch.setenv("DATABASE_URL", "postgresql://app:app-pass@db/app")
    engine = Mock()
    engine.dispose.side_effect = RuntimeError("admin-pass private-host")
    monkeypatch.setattr(
        "soj_backend.database_admin.create_engine", Mock(return_value=engine)
    )
    monkeypatch.setattr(
        "soj_backend.database_admin.migrate_database", Mock(return_value=("head",))
    )
    monkeypatch.setattr("soj_backend.database_admin.provision_runtime_role", Mock())
    assert main([]) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and "admin-pass" not in captured.err


@pytest.mark.parametrize("username", ["pg_reserved", "bad-name", "A" * 64])
def test_maintenance_rejects_invalid_role_before_migration(monkeypatch, username):
    # 通常role名の不正をschema変更前に検出する。
    monkeypatch.setenv("MIGRATION_DATABASE_URL", "postgresql://admin:admin-pass@db/app")
    monkeypatch.setenv("DATABASE_URL", f"postgresql://{username}:app-pass@db/app")
    with pytest.raises(ValueError):
        database_urls()
