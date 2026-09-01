import argparse
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from sqlalchemy import (
    Column,
    DateTime,
    MetaData,
    String,
    Table,
    func,
    inspect,
    select,
    text,
)
from sqlalchemy.engine import Connection, Engine

from migrations.versions import (
    v0001_legacy_execution_logs,
    v0002_structured_execution_logs,
)


MIGRATION_LOCK_ID = 7_316_104_014
BASE_REVISION = "base"
HEAD_REVISION = "head"


class DatabaseMigrationError(RuntimeError):
    """schema revisionが未知、不連続、またはmigration失敗の場合に送出する。"""


@dataclass(frozen=True)
class DatabaseMigration:
    """revision名とforward・rollback関数を不変な1 migrationとして保持する。"""

    revision: str
    upgrade: Callable[[Connection], None]
    downgrade: Callable[[Connection], None]


MIGRATIONS = (
    DatabaseMigration(
        revision=v0001_legacy_execution_logs.revision,
        upgrade=v0001_legacy_execution_logs.upgrade,
        downgrade=v0001_legacy_execution_logs.downgrade,
    ),
    DatabaseMigration(
        revision=v0002_structured_execution_logs.revision,
        upgrade=v0002_structured_execution_logs.upgrade,
        downgrade=v0002_structured_execution_logs.downgrade,
    ),
)

_migration_metadata = MetaData()
_migration_table = Table(
    "soj_schema_migrations",
    _migration_metadata,
    Column("revision", String(128), primary_key=True),
    Column(
        "applied_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
)


def _acquire_migration_lock(connection: Connection) -> None:
    """PostgreSQLではtransaction advisory lockを取得し、他dialectでは何もしない。"""
    if connection.dialect.name == "postgresql":
        connection.execute(
            text("SELECT pg_advisory_xact_lock(:lock_id)"),
            {"lock_id": MIGRATION_LOCK_ID},
        )


def _legacy_execution_log_columns(connection: Connection) -> set[str]:
    """入力connectionのlegacy実行ログ列名を返し、表がなければ空集合を返す。"""
    if not inspect(connection).has_table("execution_logs"):
        return set()
    return {
        column["name"] for column in inspect(connection).get_columns("execution_logs")
    }


def _stamp_unversioned_legacy_database(connection: Connection) -> None:
    """既存legacy表だけがあるDBを初期revisionとして記録する。

    入力DBにversion記録がなく、旧必須列が揃う場合だけbaselineをstampする。
    構造化列を含む不明なschemaは誤認せず例外にする。戻り値はない。
    """
    applied = set(connection.scalars(select(_migration_table.c.revision)))
    if applied:
        return
    columns = _legacy_execution_log_columns(connection)
    if not columns:
        return
    required = {"id", "problem_id", "shellgei", "output", "judge", "created_at"}
    if not required.issubset(columns):
        missing = ", ".join(sorted(required.difference(columns)))
        raise DatabaseMigrationError(
            f"unversioned execution_logs is missing: {missing}"
        )
    structured = set(v0002_structured_execution_logs.STRUCTURED_COLUMNS)
    if columns.intersection(structured):
        raise DatabaseMigrationError(
            "unversioned execution_logs already contains structured columns"
        )
    connection.execute(
        _migration_table.insert().values(revision=MIGRATIONS[0].revision)
    )


def _applied_revisions(connection: Connection) -> tuple[str, ...]:
    """適用済みrevisionを定義順で返し、未知または途中抜けなら例外にする。"""
    applied = set(connection.scalars(select(_migration_table.c.revision)))
    known = tuple(migration.revision for migration in MIGRATIONS)
    unknown = applied.difference(known)
    if unknown:
        raise DatabaseMigrationError(
            f"unknown database revisions: {', '.join(sorted(unknown))}"
        )
    ordered = tuple(revision for revision in known if revision in applied)
    if ordered != known[: len(ordered)]:
        raise DatabaseMigrationError("database revisions are not a contiguous prefix")
    return ordered


def _target_count(target: str) -> int:
    """入力target revisionを適用migration数へ変換し、未知targetなら例外にする。"""
    if target == BASE_REVISION:
        return 0
    if target == HEAD_REVISION:
        return len(MIGRATIONS)
    revisions = [migration.revision for migration in MIGRATIONS]
    try:
        return revisions.index(target) + 1
    except ValueError as exc:
        raise DatabaseMigrationError(f"unknown migration target: {target}") from exc


def migrate_database(
    database_engine: Engine, target: str = HEAD_REVISION
) -> tuple[str, ...]:
    """DBを入力target revisionへtransaction内でforwardまたはrollbackする。

    戻り値は完了後の適用revision列。PostgreSQLでは同時起動をadvisory lockで
    直列化し、transactional DDLとrevision記録を失敗時にまとめてrollbackする。
    """
    try:
        with database_engine.begin() as connection:
            _acquire_migration_lock(connection)
            _migration_table.create(connection, checkfirst=True)
            _stamp_unversioned_legacy_database(connection)
            applied = _applied_revisions(connection)
            desired_count = _target_count(target)
            if len(applied) < desired_count:
                for migration in MIGRATIONS[len(applied) : desired_count]:
                    migration.upgrade(connection)
                    connection.execute(
                        _migration_table.insert().values(revision=migration.revision)
                    )
            elif len(applied) > desired_count:
                for migration in reversed(MIGRATIONS[desired_count : len(applied)]):
                    migration.downgrade(connection)
                    connection.execute(
                        _migration_table.delete().where(
                            _migration_table.c.revision == migration.revision
                        )
                    )
            return _applied_revisions(connection)
    except DatabaseMigrationError:
        raise
    except Exception as exc:
        raise DatabaseMigrationError(
            f"database migration to {target!r} failed"
        ) from exc


def build_parser() -> argparse.ArgumentParser:
    """upgrade/downgrade先を受け取るmigration CLI parserを生成して返す。"""
    parser = argparse.ArgumentParser(description="Migrate the SOJ database schema")
    parser.add_argument(
        "target",
        nargs="?",
        default=HEAD_REVISION,
        help="head, base, or an explicit revision",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI引数のtargetまで既定DBをmigrationし、完了revisionを表示して0を返す。"""
    from scripts.database import engine

    args = build_parser().parse_args(argv)
    revisions = migrate_database(engine, args.target)
    print(revisions[-1] if revisions else BASE_REVISION)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
