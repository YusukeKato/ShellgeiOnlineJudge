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


def test_nginx_delegates_client_admission_control_to_the_outer_proxy() -> None:
    config = NGINX_CONFIG.read_text(encoding="utf-8")
    directives = _active_directives()

    assert "limit_req_zone" not in config
    assert "limit_conn_zone" not in config
    assert not any(directive.startswith("limit_req ") for directive in directives)
    assert not any(directive.startswith("limit_conn ") for directive in directives)


def test_nginx_bounds_backend_proxy_operations() -> None:
    directives = _active_directives()

    assert "location = /api/shellgei {" in directives
    assert "location /api {" in directives
    assert "proxy_request_buffering on;" in directives
    assert "proxy_connect_timeout 5s;" in directives
    assert "proxy_send_timeout 5s;" in directives
    assert "proxy_read_timeout 30s;" in directives


def test_nginx_replaces_host_and_strips_untrusted_forwarding_headers() -> None:
    config = NGINX_CONFIG.read_text(encoding="utf-8")
    directives = _active_directives()

    assert "proxy_set_header Host $proxy_host;" in directives
    assert "proxy_set_header Host $host;" not in directives
    for header in (
        "Forwarded",
        "X-Forwarded-For",
        "X-Forwarded-Host",
        "X-Forwarded-Port",
        "X-Forwarded-Proto",
        "X-Real-IP",
    ):
        assert f'proxy_set_header {header} "";' in directives
    assert "$proxy_add_x_forwarded_for" not in config
