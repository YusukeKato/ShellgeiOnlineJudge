import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Connection

import soj_backend.database_migrations as migration_module
from soj_backend.migrations.versions import v0001_legacy_execution_logs
from soj_backend.database_migrations import (
    DatabaseMigration,
    DatabaseMigrationError,
    migrate_database,
)


def _memory_engine():
    """migration unit testごとに独立したSQLite memory engineを生成して返す。"""
    return create_engine("sqlite+pysqlite:///:memory:")


def _applied_revisions(database_engine) -> tuple[str, ...]:
    """入力engineのversion表から適用revisionを定義順で読み取って返す。"""
    with database_engine.connect() as connection:
        revisions = set(
            connection.scalars(text("SELECT revision FROM soj_schema_migrations"))
        )
    return tuple(
        migration.revision
        for migration in migration_module.MIGRATIONS
        if migration.revision in revisions
    )


def test_fresh_database_migrates_to_head_idempotently() -> None:
    # 空DBをheadまで作成し、再実行してもschemaとrevisionが変化しないことを確認する。
    database_engine = _memory_engine()

    first = migrate_database(database_engine)
    second = migrate_database(database_engine)

    columns = {
        column["name"]
        for column in inspect(database_engine).get_columns("execution_logs")
    }
    assert (
        first
        == second
        == tuple(migration.revision for migration in migration_module.MIGRATIONS)
    )
    assert (
        set(migration_module.v0002_structured_execution_logs.STRUCTURED_COLUMNS)
        <= columns
    )


def test_unversioned_legacy_database_is_stamped_and_backfilled() -> None:
    # 既存legacy表を破棄せずbaseline認識し、旧output・judgeを構造化列へ移すことを確認する。
    database_engine = _memory_engine()
    with database_engine.begin() as connection:
        v0001_legacy_execution_logs.upgrade(connection)
        connection.execute(
            text(
                """
                INSERT INTO execution_logs
                    (problem_id, shellgei, output, judge, created_at)
                VALUES
                    (:problem_id, :shellgei, :output, :judge, CURRENT_TIMESTAMP)
                """
            ),
            {
                "problem_id": "STANDARD-00000001",
                "shellgei": "printf legacy",
                "output": "legacy-output",
                "judge": "1",
            },
        )

    revisions = migrate_database(database_engine)

    with database_engine.connect() as connection:
        row = (
            connection.execute(
                text(
                    """
                SELECT output, execution_status, stdout, stderr, verdict,
                       exit_code, duration_ms
                FROM execution_logs
                """
                )
            )
            .mappings()
            .one()
        )
    assert revisions == tuple(
        migration.revision for migration in migration_module.MIGRATIONS
    )
    assert row == {
        "output": "legacy-output",
        "execution_status": "legacy_unknown",
        "stdout": "legacy-output",
        "stderr": "",
        "verdict": "accepted",
        "exit_code": None,
        "duration_ms": None,
    }


def test_downgrade_removes_structured_columns_and_preserves_legacy_data() -> None:
    # headからlegacy revisionへ戻しても旧列と保存済み行を維持することを確認する。
    database_engine = _memory_engine()
    migrate_database(database_engine)
    with database_engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO execution_logs
                    (problem_id, shellgei, output, judge, created_at,
                     execution_status, stdout, stderr, timed_out, truncated,
                     duration_ms, verdict)
                VALUES
                    ('STANDARD-00000001', 'true', '', '1', CURRENT_TIMESTAMP,
                     'completed', '', '', false, false, 1, 'accepted')
                """
            )
        )

    revisions = migrate_database(database_engine, "0001_legacy_execution_logs")

    columns = {
        column["name"]
        for column in inspect(database_engine).get_columns("execution_logs")
    }
    with database_engine.connect() as connection:
        legacy_row = (
            connection.execute(
                text("SELECT problem_id, shellgei, output, judge FROM execution_logs")
            )
            .mappings()
            .one()
        )
    assert revisions == ("0001_legacy_execution_logs",)
    assert columns.isdisjoint(
        migration_module.v0002_structured_execution_logs.STRUCTURED_COLUMNS
    )
    assert legacy_row == {
        "problem_id": "STANDARD-00000001",
        "shellgei": "true",
        "output": "",
        "judge": "1",
    }


def test_failed_migration_does_not_record_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # migration途中の例外を適用済みrevisionとして記録しないことを確認する。
    database_engine = _memory_engine()
    migrate_database(database_engine, "0001_legacy_execution_logs")
    original = migration_module.MIGRATIONS

    def fail_after_schema_change(connection: Connection) -> None:
        """入力connectionを使用せず模擬例外を送出し、revision記録を中断する。"""
        raise RuntimeError("migration failed")

    failing = DatabaseMigration(
        revision=original[1].revision,
        upgrade=fail_after_schema_change,
        downgrade=original[1].downgrade,
    )
    monkeypatch.setattr(migration_module, "MIGRATIONS", (original[0], failing))

    with pytest.raises(DatabaseMigrationError, match="migration to 'head' failed"):
        migrate_database(database_engine)

    assert _applied_revisions(database_engine) == ("0001_legacy_execution_logs",)


def test_unknown_database_revision_is_rejected() -> None:
    # codeが知らないrevisionを持つDBを起動時に拒否し、誤ったschema操作を防ぐことを確認する。
    database_engine = _memory_engine()
    migrate_database(database_engine, "0001_legacy_execution_logs")
    with database_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO soj_schema_migrations (revision) "
                "VALUES ('future_revision')"
            )
        )

    with pytest.raises(DatabaseMigrationError, match="unknown database revisions"):
        migrate_database(database_engine)
