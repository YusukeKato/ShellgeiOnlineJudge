from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection


revision = "0002_structured_execution_logs"

STRUCTURED_COLUMNS = (
    "execution_status",
    "stdout",
    "stderr",
    "exit_code",
    "timed_out",
    "truncated",
    "duration_ms",
    "verdict",
    "judge_reason",
)

_ADD_COLUMN_STATEMENTS = (
    "ALTER TABLE execution_logs ADD COLUMN execution_status VARCHAR(32)",
    "ALTER TABLE execution_logs ADD COLUMN stdout TEXT",
    "ALTER TABLE execution_logs ADD COLUMN stderr TEXT",
    "ALTER TABLE execution_logs ADD COLUMN exit_code INTEGER",
    "ALTER TABLE execution_logs ADD COLUMN timed_out BOOLEAN",
    "ALTER TABLE execution_logs ADD COLUMN truncated BOOLEAN",
    "ALTER TABLE execution_logs ADD COLUMN duration_ms INTEGER",
    "ALTER TABLE execution_logs ADD COLUMN verdict VARCHAR(32)",
    "ALTER TABLE execution_logs ADD COLUMN judge_reason VARCHAR(64)",
)


def upgrade(connection: Connection) -> None:
    """legacy logへ構造化実行・判定列を追加し、既存行を安全な既定値で移行する。

    入力connectionの既存outputはstdoutへ保存する。旧行では分離不能なstderr、
    exit code、所要時間、詳細理由を推測せず、空文字またはNULLのままにする。
    """
    existing_columns = {
        column["name"] for column in inspect(connection).get_columns("execution_logs")
    }
    conflicting_columns = existing_columns.intersection(STRUCTURED_COLUMNS)
    if conflicting_columns:
        names = ", ".join(sorted(conflicting_columns))
        raise RuntimeError(f"structured execution columns already exist: {names}")

    for statement in _ADD_COLUMN_STATEMENTS:
        connection.execute(text(statement))
    connection.execute(
        text(
            """
            UPDATE execution_logs
            SET execution_status = 'legacy_unknown',
                stdout = COALESCE(output, ''),
                stderr = '',
                timed_out = false,
                truncated = false,
                verdict = CASE CAST(judge AS VARCHAR)
                    WHEN '1' THEN 'accepted'
                    WHEN '2' THEN 'wrong_image'
                    WHEN '3' THEN 'wrong_answer'
                    WHEN '4' THEN 'legacy_failure'
                    ELSE 'legacy_unknown'
                END
            """
        )
    )
    if connection.dialect.name == "postgresql":
        for column_name in (
            "execution_status",
            "stdout",
            "stderr",
            "timed_out",
            "truncated",
            "verdict",
        ):
            connection.execute(
                text(
                    f"ALTER TABLE execution_logs ALTER COLUMN {column_name} "
                    "SET NOT NULL"
                )
            )


def downgrade(connection: Connection) -> None:
    """構造化列だけを逆順に削除し、legacy列と既存データを保持する。"""
    existing_columns = {
        column["name"] for column in inspect(connection).get_columns("execution_logs")
    }
    missing_columns = set(STRUCTURED_COLUMNS).difference(existing_columns)
    if missing_columns:
        names = ", ".join(sorted(missing_columns))
        raise RuntimeError(f"structured execution columns are missing: {names}")
    for column_name in reversed(STRUCTURED_COLUMNS):
        connection.execute(
            text(f"ALTER TABLE execution_logs DROP COLUMN {column_name}")
        )
