from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    func,
    inspect,
)
from sqlalchemy.engine import Connection


revision = "0001_legacy_execution_logs"

_metadata = MetaData()
_execution_logs = Table(
    "execution_logs",
    _metadata,
    Column("id", Integer, primary_key=True),
    Column("problem_id", String),
    Column("shellgei", Text),
    Column("output", Text),
    Column("judge", String),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)
Index("ix_execution_logs_id", _execution_logs.c.id)
Index("ix_execution_logs_problem_id", _execution_logs.c.problem_id)
Index("ix_execution_logs_created_at", _execution_logs.c.created_at)


def upgrade(connection: Connection) -> None:
    """空のDBへlegacy実行ログ表と索引を作成する。

    入力はmigration transaction内のconnection。既存表がある場合は、runnerが
    baselineとしてstampするため、この関数は新規DBだけを対象にする。
    """
    if inspect(connection).has_table(_execution_logs.name):
        raise RuntimeError("execution_logs already exists before baseline migration")
    _execution_logs.create(connection)


def downgrade(connection: Connection) -> None:
    """入力connectionの実行ログ表を削除し、schemaをmigration前へ戻す。"""
    _execution_logs.drop(connection, checkfirst=True)
