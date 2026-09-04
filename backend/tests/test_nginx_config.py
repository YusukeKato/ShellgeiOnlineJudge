from pathlib import Path


NGINX_CONFIG = (
    Path(__file__).resolve().parents[2] / "frontend" / "nginx" / "default.conf"
)
FRONTEND_INDEX = Path(__file__).resolve().parents[2] / "frontend" / "index.html"


def _active_directives() -> set[str]:
    # コメントと空行を除いたnginx directiveを集合で返す。
    return {
        line.strip()
        for line in NGINX_CONFIG.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def test_nginx_bounds_request_size_and_connection_lifetime() -> None:
    # request body、header/body受信、送信、keep-aliveに上限があることを確認する。
    directives = _active_directives()

    assert "client_max_body_size 16k;" in directives
    assert "client_header_timeout 10s;" in directives
    assert "client_body_timeout 10s;" in directives
    assert "send_timeout 30s;" in directives
    assert "keepalive_timeout 15s;" in directives
    assert "keepalive_requests 100;" in directives


def test_nginx_delegates_client_admission_control_to_the_outer_proxy() -> None:
    # 中間proxy単位になるCompose nginxではIP別受付制御を行わないことを確認する。
    config = NGINX_CONFIG.read_text(encoding="utf-8")
    directives = _active_directives()

    assert "limit_req_zone" not in config
    assert "limit_conn_zone" not in config
    assert not any(directive.startswith("limit_req ") for directive in directives)
    assert not any(directive.startswith("limit_conn ") for directive in directives)


def test_nginx_bounds_backend_proxy_operations() -> None:
    # legacy・v3提出APIと一般APIのbackend転送にtimeoutとbufferingを設定することを確認する。
    directives = _active_directives()

    assert "location = /api/shellgei {" in directives
    assert "location = /api/v3/submissions {" in directives
    assert "location /api {" in directives
    assert "proxy_request_buffering on;" in directives
    assert "proxy_connect_timeout 5s;" in directives
    assert "proxy_send_timeout 5s;" in directives
    assert "proxy_read_timeout 30s;" in directives


def test_nginx_replaces_host_and_strips_untrusted_forwarding_headers() -> None:
    # backend向けHostを固定し、client指定のforwarded headerを除去することを確認する。
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


def test_nginx_does_not_persist_request_or_client_logs() -> None:
    # client IP・header・queryをaccess/error logへ保存しない設定を確認する。
    directives = _active_directives()

    assert "access_log off;" in directives
    assert "error_log /dev/null;" in directives


def test_nginx_restricts_frontend_content_to_the_same_origin() -> None:
    # CSPでscript・API通信・fontを同一originへ限定し、画像data URLだけを追加許可することを確認する。
    directives = _active_directives()

    assert (
        "add_header Content-Security-Policy \"default-src 'self'; base-uri 'self'; "
        "connect-src 'self'; font-src 'self'; form-action 'self'; frame-ancestors 'none'; "
        "img-src 'self' data:; manifest-src 'self'; object-src 'none'; script-src 'self'; "
        "style-src 'self'\" always;"
    ) in directives


def test_frontend_index_does_not_load_third_party_code_or_fonts() -> None:
    # Vite entry以外のscriptとGoogleのanalytics・web font URLがHTMLへ再導入されないことを確認する。
    index = FRONTEND_INDEX.read_text(encoding="utf-8")

    assert index.count("<script") == 1
    assert '<script type="module" src="/src/main.tsx"></script>' in index
    for forbidden_origin in (
        "googletagmanager.com",
        "google-analytics.com",
        "fonts.googleapis.com",
        "fonts.gstatic.com",
    ):
        assert forbidden_origin not in index
