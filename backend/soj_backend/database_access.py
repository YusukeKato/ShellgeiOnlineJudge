"""DB管理者と通常実行roleの境界を検証し、専用roleへ最小の権限を設定する。"""

import re

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from soj_backend.database_migrations import MIGRATIONS, _applied_revisions


ROLE_NAME = re.compile(r"[a-z_][a-z0-9_]{0,62}")


def _check_role(connection: Connection, role: str) -> None:
    """特権・他roleへの所属・所有物があるroleを拒否する。DBの状態は変更しない。"""
    unsafe = connection.scalar(
        text("""
        SELECT rolsuper OR rolcreaterole OR rolcreatedb OR rolreplication
            OR rolbypassrls OR rolinherit OR NOT rolcanlogin
            OR EXISTS (SELECT 1 FROM pg_auth_members WHERE member = r.oid)
            OR EXISTS (SELECT 1 FROM pg_shdepend
                       WHERE refclassid = 'pg_authid'::regclass
                         AND refobjid = r.oid AND deptype = 'o')
        FROM pg_roles r WHERE rolname = :role
        """),
        {"role": role},
    )
    if unsafe is not False:
        raise RuntimeError("runtime database role must be an unprivileged non-owner")


def _check_privileges(connection: Connection, role: str) -> None:
    """管理対象DB・public schema・実行ログの実効権限を確認し、過剰/不足なら拒否する。"""
    checks = [
        ("has_database_privilege(:role, current_database(), :priv)", "CONNECT", True),
        (
            "has_database_privilege(:role, current_database(), :priv)",
            "CREATE,TEMP",
            False,
        ),
        ("has_schema_privilege(:role, 'public', :priv)", "USAGE", True),
        ("has_schema_privilege(:role, 'public', :priv)", "CREATE", False),
        (
            "has_sequence_privilege(:role, 'public.execution_logs_id_seq', :priv)",
            "USAGE",
            True,
        ),
        (
            "has_sequence_privilege(:role, 'public.execution_logs_id_seq', :priv)",
            "UPDATE,USAGE WITH GRANT OPTION,SELECT WITH GRANT OPTION",
            False,
        ),
    ]
    for table, allowed in (
        ("execution_logs", {"SELECT", "INSERT", "DELETE"}),
        ("soj_schema_migrations", {"SELECT"}),
    ):
        # table名は固定値だけを用い、role・privilegeはbind parameterで渡す。
        expression = f"has_table_privilege(:role, 'public.{table}', :priv)"
        for privilege in (
            "SELECT",
            "INSERT",
            "UPDATE",
            "DELETE",
            "TRUNCATE",
            "REFERENCES",
            "TRIGGER",
        ):
            checks.append((expression, privilege, privilege in allowed))
            checks.append((expression, f"{privilege} WITH GRANT OPTION", False))
        for privilege in ("SELECT", "INSERT", "UPDATE", "REFERENCES"):
            column_expression = (
                f"has_any_column_privilege(:role, 'public.{table}', :priv)"
            )
            checks.append((column_expression, f"{privilege} WITH GRANT OPTION", False))
            if privilege not in allowed:
                checks.append((column_expression, privilege, False))
    for expression, privilege, expected in checks:
        value = connection.scalar(
            text(f"SELECT {expression}"), {"role": role, "priv": privilege}
        )
        if value is not expected:
            raise RuntimeError("runtime database privileges do not match policy")


def validate_runtime_database(database_engine: Engine) -> None:
    """schemaがheadでありPostgreSQLでは最小権限roleであることを、読み取りだけで確認する。"""
    try:
        with database_engine.connect() as connection:
            if _applied_revisions(connection) != tuple(
                item.revision for item in MIGRATIONS
            ):
                raise RuntimeError("database schema is not at head")
            if connection.dialect.name == "postgresql":
                role = str(connection.scalar(text("SELECT current_user")))
                _check_role(connection, role)
                _check_privileges(connection, role)
    except Exception:
        raise RuntimeError(
            "runtime database validation failed; run database maintenance first"
        ) from None


def provision_runtime_role(database_engine: Engine, role: str, password: str) -> None:
    """migration後の専用DBへapp roleと権限をtransaction内で設定する。既存ownerは変更しない。

    既存の特権role・所有者・所属roleは降格せず拒否する。PUBLICのCREATE/TEMPと
    管理対象表の公開権限は取り消すため、共用DBへ適用せず、backendを止めて実行する。
    """
    if (
        not ROLE_NAME.fullmatch(role)
        or role.startswith("pg_")
        or not password
        or "\x00" in password
    ):
        raise ValueError("invalid runtime role configuration")
    if database_engine.dialect.name != "postgresql":
        raise ValueError("role provisioning requires PostgreSQL")
    with database_engine.begin() as connection:
        connection.execute(text("SELECT pg_advisory_xact_lock(7316104015)"))
        quoted = connection.dialect.identifier_preparer.quote(role)
        exists = connection.scalar(
            text("SELECT 1 FROM pg_roles WHERE rolname = :role"), {"role": role}
        )
        if not exists:
            connection.execute(
                text(
                    f"CREATE ROLE {quoted} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
                )
            )
        _check_role(connection, role)
        connection.execute(
            text(f"ALTER ROLE {quoted} PASSWORD :password"), {"password": password}
        )
        database = connection.dialect.identifier_preparer.quote(
            str(connection.scalar(text("SELECT current_database()")))
        )
        connection.execute(
            text(f"REVOKE CREATE, TEMPORARY ON DATABASE {database} FROM PUBLIC")
        )
        connection.execute(text(f"REVOKE ALL ON DATABASE {database} FROM {quoted}"))
        connection.execute(text(f"GRANT CONNECT ON DATABASE {database} TO {quoted}"))
        connection.execute(text("REVOKE CREATE ON SCHEMA public FROM PUBLIC"))
        connection.execute(text(f"REVOKE ALL ON SCHEMA public FROM {quoted}"))
        connection.execute(text(f"GRANT USAGE ON SCHEMA public TO {quoted}"))
        for table, privileges in (
            ("execution_logs", "SELECT, INSERT, DELETE"),
            ("soj_schema_migrations", "SELECT"),
        ):
            connection.execute(
                text(f"REVOKE ALL ON TABLE public.{table} FROM PUBLIC, {quoted}")
            )
            connection.execute(
                text(f"GRANT {privileges} ON TABLE public.{table} TO {quoted}")
            )
        connection.execute(
            text(
                f"REVOKE ALL ON SEQUENCE public.execution_logs_id_seq FROM PUBLIC, {quoted}"
            )
        )
        connection.execute(
            text(f"GRANT USAGE ON SEQUENCE public.execution_logs_id_seq TO {quoted}")
        )
        _check_privileges(connection, role)
