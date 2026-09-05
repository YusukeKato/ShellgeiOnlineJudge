import os
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DEFAULT_DATABASE_OPERATION_TIMEOUT_SECONDS = 5


def _positive_integer_from_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a positive integer") from exc
    if value < 1:
        raise RuntimeError(f"{name} must be a positive integer")
    return value


SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://soj_user:soj_password@localhost:5432/soj_db"
)
DATABASE_OPERATION_TIMEOUT_SECONDS = _positive_integer_from_env(
    "DATABASE_OPERATION_TIMEOUT_SECONDS",
    DEFAULT_DATABASE_OPERATION_TIMEOUT_SECONDS,
)


def _engine_options(database_url: str, timeout_seconds: int) -> dict[str, Any]:
    if not database_url.startswith("postgresql"):
        return {}
    timeout_milliseconds = timeout_seconds * 1000
    return {
        "pool_timeout": timeout_seconds,
        "connect_args": {
            "connect_timeout": timeout_seconds,
            "options": (
                f"-c statement_timeout={timeout_milliseconds} "
                f"-c lock_timeout={timeout_milliseconds} -c search_path=public"
            ),
        },
    }


engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    **_engine_options(
        SQLALCHEMY_DATABASE_URL,
        DATABASE_OPERATION_TIMEOUT_SECONDS,
    ),
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# 依存性注入(DI)用の関数
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
