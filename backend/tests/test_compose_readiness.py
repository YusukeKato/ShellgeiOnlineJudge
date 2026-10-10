"""初回HTTPSの一時障害、証明書拒否、待機期限、秘密値を含まない診断をDockerなしで検査する。"""

import http.client
from email.message import Message
import io
import ssl
import urllib.error
from types import SimpleNamespace
from typing import Any

import pytest

from tests import compose_support
from tests.compose_support import ComposeStack


class Clock:
    """実時間を待たずに、通信とsleepが同じ期限を消費する状況を再現する。"""

    def __init__(self) -> None:
        """仮想時刻と待機履歴を初期化する。"""
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        """テストが進めた仮想時刻を返す。"""
        return self.now

    def sleep(self, seconds: float) -> None:
        """待機時間を記録し、その分だけ期限を進める。"""
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    """起動待ちだけの時計を差し替え、実際のsleepを行わない。"""
    clock = Clock()
    monkeypatch.setattr(compose_support.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(compose_support.time, "sleep", clock.sleep)
    return clock


@pytest.fixture
def stack(monkeypatch: pytest.MonkeyPatch) -> ComposeStack:
    """Docker・証明書生成を行わず、専用serviceの固定状態を用意する。"""
    stack = ComposeStack.__new__(ComposeStack)
    monkeypatch.setattr(
        stack,
        "service",
        lambda name: SimpleNamespace(
            attrs={
                "State": {
                    "Status": "running",
                    "Health": {"Status": "starting", "Log": ["hidden credential"]},
                    "ExitCode": 0,
                    "OOMKilled": False,
                },
                "Config": {"Env": ["DATABASE_URL=hidden credential"]},
            }
        ),
    )
    return stack


@pytest.mark.parametrize(
    "failure",
    [
        urllib.error.URLError(ssl.SSLEOFError(8, "UNEXPECTED_EOF_WHILE_READING")),
        ConnectionResetError("connection reset"),
        TimeoutError("request timed out"),
        ssl.SSLEOFError(8, "UNEXPECTED_EOF_WHILE_READING"),
        http.client.IncompleteRead(b"partial private response"),
    ],
    ids=["wrapped-tls-eof", "reset", "timeout", "tls-eof", "partial-response"],
)
def test_startup_recovers_from_transport_failure_and_non_200(
    monkeypatch: pytest.MonkeyPatch,
    stack: ComposeStack,
    clock: Clock,
    failure: Exception,
) -> None:
    """一時通信障害と503の後に200へ復帰すれば、起動成功として返す。"""
    calls: list[float] = []

    def request(path: str, *, timeout: float) -> tuple[int, Any, bytes]:
        """初回の通信障害、準備中、準備完了を順に再現する。"""
        assert path == "/api/problems"
        calls.append(timeout)
        if len(calls) == 1:
            raise failure
        return (503 if len(calls) == 2 else 200), {}, b""

    monkeypatch.setattr(stack, "request", request)
    stack.wait_api(timeout=3)
    assert len(calls) == 3
    assert clock.sleeps == [0.5, 0.5]
    assert calls == [3, 2.5, 2]


@pytest.mark.parametrize("wrapped", [False, True])
def test_certificate_rejection_is_immediate(
    monkeypatch: pytest.MonkeyPatch, stack: ComposeStack, clock: Clock, wrapped: bool
) -> None:
    """直接またはURLError内の証明書エラーを、再試行やTLS無効化で隠さない。"""
    certificate = ssl.SSLCertVerificationError(1, "untrusted certificate")
    failure = urllib.error.URLError(certificate) if wrapped else certificate
    calls = []

    def request(path: str, *, timeout: float) -> tuple[int, Any, bytes]:
        """信頼できない証明書による接続拒否を再現する。"""
        calls.append(path)
        raise failure

    monkeypatch.setattr(stack, "request", request)
    with pytest.raises(type(failure)) as caught:
        stack.wait_api()
    assert caught.value is failure
    assert len(calls) == 1
    assert clock.sleeps == []


@pytest.mark.parametrize("transport_failure", [False, True])
def test_startup_timeout_reports_safe_service_state(
    monkeypatch: pytest.MonkeyPatch,
    stack: ComposeStack,
    clock: Clock,
    transport_failure: bool,
) -> None:
    """503またはTLS EOFが続く場合、期限内で終了し本文やcredentialなしの状態を報告する。"""
    timeouts = []

    def request(path: str, *, timeout: float) -> tuple[int, Any, bytes]:
        """準備未完了を繰り返し、例外本文にも診断へ出してはいけない値を置く。"""
        timeouts.append(timeout)
        if transport_failure:
            raise urllib.error.URLError(ssl.SSLEOFError(8, "hidden credential"))
        return 503, {}, b"hidden credential"

    monkeypatch.setattr(stack, "request", request)
    with pytest.raises(TimeoutError) as caught:
        stack.wait_api(timeout=1.2)
    message = str(caught.value)
    assert clock.now == pytest.approx(1.2)
    assert clock.sleeps == pytest.approx([0.5, 0.5, 0.2])
    assert timeouts == pytest.approx([1.2, 0.7, 0.2])
    assert ("SSLEOFError" if transport_failure else "HTTP 503") in message
    assert '"frontend"' in message
    assert '"health": "starting"' in message
    assert "hidden credential" not in message
    assert "DATABASE_URL" not in message


def test_slow_request_consumes_the_same_startup_deadline(
    monkeypatch: pytest.MonkeyPatch, stack: ComposeStack, clock: Clock
) -> None:
    """通信に残り時間を使い切った場合、追加sleepや次のrequestを開始しない。"""
    timeouts = []

    def request(path: str, *, timeout: float) -> tuple[int, Any, bytes]:
        """各通信が指定されたsocket timeoutを消費する状況を再現する。"""
        timeouts.append(timeout)
        clock.now += timeout
        raise TimeoutError("slow connection")

    monkeypatch.setattr(stack, "request", request)
    with pytest.raises(TimeoutError, match="last result: TimeoutError"):
        stack.wait_api(timeout=6)
    assert timeouts == [5, 0.5]
    assert clock.now == 6
    assert clock.sleeps == [0.5]


def test_diagnostic_failure_does_not_hide_original_timeout(
    monkeypatch: pytest.MonkeyPatch, stack: ComposeStack, clock: Clock
) -> None:
    """service取得が失敗しても、元の起動timeoutと例外の型だけを診断に残す。"""

    def service(name: str) -> Any:
        """Docker検査の失敗本文に秘密値があっても外へ出さないことを確認する。"""
        raise RuntimeError("hidden credential")

    monkeypatch.setattr(stack, "service", service)
    with pytest.raises(TimeoutError) as caught:
        stack.wait_api(timeout=0)
    assert "not attempted" in str(caught.value)
    assert '"inspection_error": "RuntimeError"' in str(caught.value)
    assert "hidden credential" not in str(caught.value)
    assert clock.sleeps == []


def test_programming_error_is_not_retried(
    monkeypatch: pytest.MonkeyPatch, stack: ComposeStack, clock: Clock
) -> None:
    """通信障害以外の実装エラーを起動待ちとして握りつぶさない。"""

    def request(path: str, *, timeout: float) -> tuple[int, Any, bytes]:
        """待機対象外の不正値エラーを再現する。"""
        raise ValueError("invalid request setup")

    monkeypatch.setattr(stack, "request", request)
    with pytest.raises(ValueError, match="invalid request setup"):
        stack.wait_api()
    assert clock.sleeps == []


@pytest.mark.parametrize("status", [200, 503])
def test_request_forwards_timeout_and_closes_http_response(
    monkeypatch: pytest.MonkeyPatch, stack: ComposeStack, status: int
) -> None:
    """requestが待機側のtimeoutをopenerへ渡し、HTTP errorも読み取ってcloseする。"""
    response = urllib.error.HTTPError(
        "https://test.invalid/api/problems",
        status,
        "test response",
        Message(),
        io.BytesIO(b"body"),
    )
    stack.url = "https://test.invalid"

    def open_response(request: Any, *, timeout: float) -> Any:
        """HTTP応答とHTTPErrorの両経路で同じtimeoutが渡されることを確認する。"""
        assert request.full_url == stack.url + "/api/problems"
        assert timeout == 0.25
        if status != 200:
            raise response
        return response

    monkeypatch.setattr(
        stack, "http", SimpleNamespace(open=open_response), raising=False
    )
    actual, _, body = stack.request("/api/problems", timeout=0.25)
    assert actual == status
    assert body == b"body"
    assert response.closed
