import pytest
from sqlalchemy.engine import make_url

from soj_backend.database_url import database_driver_url


@pytest.mark.parametrize(
    "value",
    [
        "sqlite:///:memory:",
        "postgresql+psycopg2://app:pass@db/app",
        "postgresql+psycopg://app:pass@db/app",
    ],
)
def test_explicit_drivers_and_other_databases_are_preserved(value: str) -> None:
    # driverを明示したURLとPostgreSQL以外のURLを変更せず、文字列とURL object両方を受理する。
    url = make_url(value)
    assert database_driver_url(value) == url
    assert database_driver_url(url) == url


def test_default_postgres_driver_preserves_connection_fields() -> None:
    # driverだけを変更し、特殊文字password、IPv6、port、database、query設定を保持する。
    url = make_url(
        "postgresql://app:p%40ss%2Fword@[::1]:5433/logs?application_name=soj"
    )
    resolved = database_driver_url(url)
    assert resolved.drivername == "postgresql+psycopg2"
    assert resolved.set(drivername="postgresql") == url
    assert resolved.password == "p@ss/word"
