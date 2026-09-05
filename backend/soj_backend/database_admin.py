"""常時稼働backendへ管理者資格情報を渡さず、専用serviceからmigrationとrole設定を行う。"""

import os
import sys
from collections.abc import Sequence

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url

from soj_backend.database_access import ROLE_NAME, provision_runtime_role
from soj_backend.database_migrations import (
    BASE_REVISION,
    HEAD_REVISION,
    build_parser,
    migrate_database,
)


def database_urls() -> tuple[URL, URL]:
    """同じPostgreSQL DBを指す別ユーザーの管理用・通常用URLを環境から検証して返す。"""
    admin = make_url(os.environ["MIGRATION_DATABASE_URL"])
    app = make_url(os.environ["DATABASE_URL"])
    for url in (admin, app):
        if (
            url.drivername not in {"postgresql", "postgresql+psycopg2"}
            or not all((url.username, url.password, url.host, url.database))
            or url.query
        ):
            raise ValueError("explicit PostgreSQL credentials are required")
    if (
        (admin.host, admin.port or 5432, admin.database)
        != (app.host, app.port or 5432, app.database)
        or admin.username == app.username
        or admin.password == app.password
    ):
        raise ValueError("use distinct credentials for the same database")
    assert app.username is not None and app.password is not None
    if (
        not ROLE_NAME.fullmatch(app.username)
        or app.username.startswith("pg_")
        or "\x00" in app.password
    ):
        raise ValueError("invalid runtime role configuration")
    return admin, app


def main(argv: Sequence[str] | None = None) -> int:
    """管理URLでmigrationを行い、headではruntime roleを設定する。失敗時は秘密情報を表示しない。"""
    args = build_parser().parse_args(argv)
    engine = None
    completed = False
    revision = BASE_REVISION
    try:
        admin, app = database_urls()
        engine = create_engine(
            admin,
            hide_parameters=True,
            connect_args={
                "connect_timeout": 5,
                "options": "-c statement_timeout=30000 -c lock_timeout=5000 -c search_path=public",
            },
        )
        revisions = migrate_database(engine, args.target)
        if args.target == HEAD_REVISION:
            assert app.username is not None and app.password is not None
            provision_runtime_role(engine, app.username, app.password)
        revision = revisions[-1] if revisions else BASE_REVISION
        completed = True
    except Exception:
        completed = False
    finally:
        if engine is not None:
            try:
                engine.dispose()
            except Exception:
                completed = False
    if completed:
        print(revision)
        return 0
    print(
        "database maintenance failed; check configuration and database state",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
