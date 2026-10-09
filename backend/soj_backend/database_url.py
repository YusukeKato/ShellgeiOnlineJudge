from sqlalchemy.engine import URL, make_url


def database_driver_url(value: str | URL) -> URL:
    """driver省略のPostgreSQL URLだけに既存のpsycopg2を指定し、他の設定を保持する。

    SQLAlchemy 2.1の既定driver変更から既存の環境設定を保護する。
    URL objectのまま扱いpasswordの再encodeや文字列化を避け、不正URLは呼出元へ返す。
    """
    url = make_url(value)
    if url.drivername == "postgresql":
        return url.set(drivername="postgresql+psycopg2")
    return url
