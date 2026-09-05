from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from tests.compose_support import ComposeStack, isolated_config


ROOT = Path(__file__).resolve().parents[2]
BASE = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
PROJECT = "soj-e2e-" + "a" * 32
IMAGES = {name: f"soj-{name}:e2e" for name in ("backend", "runner", "frontend")}


def test_isolation_preserves_service_security_and_original_config() -> None:
    # 名前・port・image以外の本番制約を維持し、入力や共有volumeを変更しない。
    before = deepcopy(BASE)
    result = isolated_config(BASE, PROJECT, IMAGES)
    assert BASE == before
    assert result["networks"] == BASE["networks"]
    assert result["volumes"] == BASE["volumes"]
    for name, original in BASE["services"].items():
        service = result["services"][name]
        assert service["container_name"] == f"{PROJECT}-{name}"
        for field in (
            "environment",
            "volumes",
            "networks",
            "restart",
            "logging",
            "read_only",
            "tmpfs",
            "cap_drop",
            "security_opt",
            "group_add",
        ):
            assert service.get(field) == original.get(field)
    assert result["services"]["db"]["ports"] == []
    assert result["services"]["frontend"]["ports"] == ["127.0.0.1::443"]


@pytest.mark.parametrize(
    "project", ["soj", "shellgei-online-judge", "soj-e2e-", "../test"]
)
def test_rejects_non_test_project(project: str) -> None:
    # cleanupが既存環境を対象にできないよう、専用UUID形式以外を起動前に拒否する。
    with pytest.raises(ValueError):
        isolated_config(BASE, project, IMAGES)


@pytest.mark.parametrize("section", ["volumes", "networks"])
@pytest.mark.parametrize("unsafe", [{"external": True}, {"name": "production"}])
def test_rejects_resources_outside_project(
    section: str, unsafe: dict[str, object]
) -> None:
    # 将来の本番定義に共有資源が追加されても、そのままtest環境へ流用しない。
    base = deepcopy(BASE)
    base[section][next(iter(base[section]))] = unsafe
    with pytest.raises(ValueError):
        isolated_config(base, PROJECT, IMAGES)


@pytest.mark.parametrize(
    "field,value",
    [
        ("volumes", ["/production:/data"]),
        ("env_file", ".env"),
        ("ports", ["8000:8000"]),
    ],
)
def test_rejects_unreviewed_host_resources(field: str, value: object) -> None:
    # 本番向けmountやenv fileの追加が既存testの隔離を破らないよう起動前に拒否する。
    base = deepcopy(BASE)
    base["services"]["backend"][field] = value
    with pytest.raises(ValueError):
        isolated_config(base, PROJECT, IMAGES)


def test_rejects_named_volume_backed_by_host_directory() -> None:
    # project名付きvolumeでもdriver経由で本番directoryをmountできるため、起動前に拒否する。
    base = deepcopy(BASE)
    base["volumes"]["db_data"] = {
        "driver_opts": {"type": "none", "o": "bind", "device": "/production"}
    }
    with pytest.raises(ValueError):
        isolated_config(base, PROJECT, IMAGES)


@pytest.mark.parametrize("section", ["secrets", "configs"])
def test_rejects_unreviewed_compose_file_resources(section: str) -> None:
    # Compose固有のsecret/config fileが本番hostの情報をtestへ持ち込む経路も拒否する。
    base = deepcopy(BASE)
    base[section] = {"production": {"file": "/production/credential"}}
    with pytest.raises(ValueError):
        isolated_config(base, PROJECT, IMAGES)


@pytest.mark.parametrize("failure", ["stop", "down", "sandboxes"])
def test_cleanup_attempts_remaining_resources_after_failure(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    # 各段階の例外でも残る回収を試み、runner停止を試みる前にsandboxを削除しない。
    stack = ComposeStack.__new__(ComposeStack)
    calls = []

    def compose(*arguments: str) -> str:
        """Compose操作を記録し、指定した段階だけを失敗させる。"""
        calls.append(arguments[0])
        if arguments[0] == failure:
            raise RuntimeError("injected cleanup failure")
        if arguments[0] == "down":
            assert "--volumes" in arguments
        return ""

    def sandboxes() -> None:
        """専用sandboxの回収を記録し、指定時には失敗させる。"""
        calls.append("sandboxes")
        if failure == "sandboxes":
            raise RuntimeError("injected cleanup failure")

    monkeypatch.setattr(stack, "compose", compose)
    monkeypatch.setattr(stack, "remove_sandboxes", sandboxes)
    with pytest.raises(RuntimeError, match="injected cleanup failure"):
        stack.close()
    assert calls == ["stop", "down", "sandboxes"]
