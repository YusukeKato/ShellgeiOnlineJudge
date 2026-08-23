from pathlib import Path


NGINX_CONFIG = (
    Path(__file__).resolve().parents[2] / "frontend" / "nginx" / "default.conf"
)


def _active_directives() -> set[str]:
    return {
        line.strip()
        for line in NGINX_CONFIG.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def test_nginx_bounds_request_size_and_connection_lifetime() -> None:
    directives = _active_directives()

    assert "client_max_body_size 16k;" in directives
    assert "client_header_timeout 10s;" in directives
    assert "client_body_timeout 10s;" in directives
    assert "send_timeout 30s;" in directives
    assert "keepalive_timeout 15s;" in directives
    assert "keepalive_requests 100;" in directives


def test_nginx_limits_api_rate_and_concurrent_connections() -> None:
    directives = _active_directives()

    assert (
        "limit_req_zone $binary_remote_addr zone=api_per_client:10m rate=20r/s;"
        in directives
    )
    assert (
        "limit_req_zone $binary_remote_addr zone=shellgei_per_client:10m rate=5r/s;"
        in directives
    )
    assert (
        "limit_conn_zone $binary_remote_addr "
        "zone=api_connections_per_client:10m;" in directives
    )
    assert "limit_req zone=shellgei_per_client burst=5 nodelay;" in directives
    assert "limit_conn api_connections_per_client 5;" in directives
    assert "limit_req zone=api_per_client burst=40 nodelay;" in directives
    assert "limit_conn api_connections_per_client 20;" in directives
    assert "limit_req_status 429;" in directives
    assert "limit_conn_status 429;" in directives


def test_nginx_bounds_backend_proxy_operations() -> None:
    directives = _active_directives()

    assert "location = /api/shellgei {" in directives
    assert "location /api {" in directives
    assert "proxy_request_buffering on;" in directives
    assert "proxy_connect_timeout 5s;" in directives
    assert "proxy_send_timeout 5s;" in directives
    assert "proxy_read_timeout 30s;" in directives


def test_nginx_does_not_forward_an_unverified_x_forwarded_for_chain() -> None:
    config = NGINX_CONFIG.read_text(encoding="utf-8")
    directives = _active_directives()

    assert "proxy_set_header X-Forwarded-For $remote_addr;" in directives
    assert "$proxy_add_x_forwarded_for" not in config
