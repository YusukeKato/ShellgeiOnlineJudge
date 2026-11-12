import hashlib
import io
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ci import bootstrap_pip
from ci.check_ca_trust import FIXTURES, parse_stores, verify_store


def test_modified_bootstrap_wheel_never_reaches_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """改ざんされたpip wheelを受け取ると、installもensurepip変更も開始しない。"""
    monkeypatch.setattr(
        bootstrap_pip.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(b"tampered")
    )
    install = Mock()
    monkeypatch.setattr(bootstrap_pip.subprocess, "run", install)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        bootstrap_pip.bootstrap(seed=True)
    install.assert_not_called()


def test_verified_bootstrap_is_installed_without_network_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """hash一致後は取得済みwheelだけをoffline installし、追加のindex取得を行わない。"""
    payload = b"verified fixture"
    monkeypatch.setattr(
        bootstrap_pip, "WHEEL_SHA256", hashlib.sha256(payload).hexdigest()
    )
    monkeypatch.setattr(
        bootstrap_pip.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(payload)
    )
    install = Mock()
    monkeypatch.setattr(bootstrap_pip.subprocess, "run", install)
    bootstrap_pip.bootstrap()
    command = install.call_args.args[0]
    assert {"--no-index", "--no-deps", "--isolated"} <= set(command)
    assert install.call_args.kwargs["check"] is True


def test_ensurepip_replacement_does_not_restore_old_seed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """既知のensurepip構成ではwheelとversionを揃え、不明な構成には触れない。"""
    module = tmp_path / "ensurepip" / "__init__.py"
    bundled = module.parent / "_bundled"
    bundled.mkdir(parents=True)
    module.write_text('_PIP_VERSION = "25.0.1"\n')
    (bundled / "pip-25.0.1-py3-none-any.whl").write_bytes(b"old")
    wheel = tmp_path / bootstrap_pip.WHEEL_NAME
    wheel.write_bytes(b"new")
    monkeypatch.setitem(sys.modules, "ensurepip", SimpleNamespace(__file__=str(module)))
    bootstrap_pip.update_ensurepip(wheel)
    assert module.read_text() == f'_PIP_VERSION = "{bootstrap_pip.PIP_VERSION}"\n'
    assert list(bundled.iterdir()) == [bundled / bootstrap_pip.WHEEL_NAME]
    module.write_text("unknown layout\n")
    with pytest.raises(RuntimeError, match="unknown ensurepip layout"):
        bootstrap_pip.update_ensurepip(wheel)
    assert module.read_text() == "unknown layout\n"


def test_ca_checker_detects_restored_compromised_root() -> None:
    """正常controlだけを信頼するstoreは合格し、漏えいchainのroot追加は失敗する。"""
    trusted = (FIXTURES / "control-root.pem").read_text()
    verify_store(trusted)
    compromised = (FIXTURES / "compromised-root.pem").read_text()
    with pytest.raises(ValueError, match="not distrusted"):
        verify_store(trusted + "\n" + compromised)


def test_ca_checker_rejects_empty_or_incomplete_output() -> None:
    """storeの取得失敗・空PEM・重複名を、検査成功として扱わない。"""
    for output in [
        "",
        "SOJ_CA_STORE os\n",
        "SOJ_CA_STORE os\n-----BEGIN CERTIFICATE-----\nSOJ_CA_STORE os\n-----BEGIN CERTIFICATE-----",
    ]:
        with pytest.raises(ValueError):
            parse_stores(output)


def test_playwright_runtime_guard_rejects_old_binary_and_redirected_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同梱旧版・別pathへのoverride・CA option欠落を拒否し、修正版の通常解決だけ許可する。"""
    from ci.check_ca_trust import PYTHON_STORES
    import importlib.util
    import subprocess
    import types

    start = PYTHON_STORES.index("if importlib.util.find_spec('playwright'):")
    guard = PYTHON_STORES[start : PYTHON_STORES.index("for wheel in", start)]
    private = "/opt/venv/lib/python3.12/site-packages/playwright/driver/node"
    driver = types.ModuleType("playwright._impl._driver")
    driver.compute_driver_executable = lambda: (private, "cli.js")  # type: ignore[attr-defined]
    monkeypatch.setitem(
        sys.modules,
        "playwright",
        SimpleNamespace(
            __file__="/opt/venv/lib/python3.12/site-packages/playwright/__init__.py"
        ),
    )
    monkeypatch.setitem(sys.modules, "playwright._impl._driver", driver)
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    monkeypatch.setenv("NODE_OPTIONS", "--use-openssl-ca")
    run = Mock(return_value="v24.22.3\n")
    monkeypatch.setattr(subprocess, "check_output", run)

    def inspect() -> None:
        """同じ実image用guardを、外部processを起動しないtest doubleで通す。"""
        exec(
            guard,
            {"importlib": __import__("importlib"), "pathlib": __import__("pathlib")},
        )

    inspect()
    assert run.call_args.args[0] == [private, "--version"]
    for version in ("v24.22.1\n", "v22.23.5\n"):
        run.return_value = version
        with pytest.raises(RuntimeError, match="security floor"):
            inspect()
    run.return_value = "v24.22.3\n"
    driver.compute_driver_executable = lambda: ("/tmp/old-node", "cli.js")  # type: ignore[attr-defined]
    with pytest.raises(RuntimeError, match="inspected private Node"):
        inspect()
    driver.compute_driver_executable = lambda: (private, "cli.js")  # type: ignore[attr-defined]
    monkeypatch.delenv("NODE_OPTIONS")
    with pytest.raises(RuntimeError, match="inspected OS CA"):
        inspect()
