import hashlib
import io
import json
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest

import ci.supply_chain as supply_chain
from soj_shared.version import APP_VERSION
from ci.install_tools import extract_binary
from ci.supply_chain import blocking_findings, write_record


@pytest.mark.parametrize(
    "name,version,path,old_copy,error",
    [
        ("db", "go1.26.11", "/usr/local/bin/gosu", False, None),
        ("sandbox", "go1.26.12", "/usr/local/bin/textimg", False, None),
        ("db", "go1.26.10", "/usr/local/bin/gosu", False, "security floor"),
        ("db", "go1.27.0", "/usr/local/bin/gosu", False, "security floor"),
        ("db", "devel go1.26", "/usr/local/bin/gosu", False, "security floor"),
        ("db", "go1.26.11", "/tmp/gosu", False, "missing Go binary"),
        ("db", "go1.26.11", "/usr/local/bin/gosu", True, "security floor"),
    ],
)
def test_go_floor_checks_actual_binary_location_and_every_copy(
    name: str, version: str, path: str, old_copy: bool, error: str | None
) -> None:
    # 正しい最終binaryだけを許可し、旧版・別branch初期版・不正version・残存旧copyを拒否する。
    packages = [
        {
            "name": "stdlib",
            "type": "go-module",
            "version": version,
            "locations": [{"path": path}],
        }
    ]
    if old_copy:
        packages.append(
            {
                "name": "stdlib",
                "type": "go-module",
                "version": "go1.26.10",
                "locations": [{"path": "/opt/old-copy"}],
            }
        )
    if error is None:
        supply_chain.require_go_runtime_floor({"artifacts": packages}, name)
    else:
        with pytest.raises(ValueError, match=error):
            supply_chain.require_go_runtime_floor({"artifacts": packages}, name)


def test_go_floor_rejects_missing_inventory_without_affecting_python_roles() -> None:
    # Goが必要な実imageの欠落を拒否し、Goを収録しないPython/frontend/lock検査は維持する。
    for name in ("db", "sandbox"):
        with pytest.raises(ValueError, match="missing Go binary"):
            supply_chain.require_go_runtime_floor({"artifacts": []}, name)
    for name in ("backend", "runner", "frontend", "dependencies"):
        supply_chain.require_go_runtime_floor({"artifacts": []}, name)


def test_scan_rejects_old_go_even_before_vulnerability_matching(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # 有効なSBOMでも実Go版が古ければ、severity未設定やDB未反映を待たずGrypeの前で停止する。
    commands = []

    def create_inventory(command: list[str]) -> int:
        """外部toolを実行せず、旧gosuを示すSyft形式の最小inventoryを保存する。"""
        commands.append(command)
        (tmp_path / "db.syft.json").write_text(
            json.dumps(
                {
                    "artifacts": [
                        {
                            "name": "stdlib",
                            "type": "go-module",
                            "version": "go1.26.10",
                            "locations": [{"path": "/usr/local/bin/gosu"}],
                        }
                    ]
                }
            )
        )
        return 0

    monkeypatch.setattr(supply_chain, "run", create_inventory)
    with pytest.raises(ValueError, match="security floor"):
        supply_chain.scan(tmp_path, "docker:old-db", tmp_path, "db")
    assert len(commands) == 1 and Path(commands[0][0]).name == "syft"


@pytest.mark.parametrize("blocked_product", ["frontend", "db", "sandbox"])
def test_runtime_scan_records_and_archives_the_built_runtime_images(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, blocked_product: str
) -> None:
    # frontend・DB・sandboxのいずれかだけの検出でも失敗し、全5 imageのIDをarchive・recordへ含める。
    products = {
        name: f"soj-{name}:review"
        for name in ("backend", "runner", "frontend", "db", "sandbox")
    }
    sources = []
    commands = []

    def inspect_image(command: list[str], **kwargs: object) -> SimpleNamespace:
        """タグごとのimmutable IDを返し、Docker daemonなしで保存対象の一致を検証する。"""
        assert command[:3] == ["docker", "image", "inspect"]
        return SimpleNamespace(
            stdout="sha256:" + hashlib.sha256(command[-1].encode()).hexdigest()
        )

    def scan_image(tools: Path, source: str, reports: Path, name: str) -> bool:
        """scan対象を記録し、指定されたimageだけに停止対象がある状態を返す。"""
        sources.append(source)
        return name != blocked_product

    monkeypatch.setattr(supply_chain, "rootless", lambda: None)
    monkeypatch.setattr(supply_chain.subprocess, "run", inspect_image)
    monkeypatch.setattr(
        supply_chain.subprocess,
        "check_output",
        lambda command, **kwargs: "a" * 40 if command[1] == "rev-parse" else "",
    )
    monkeypatch.setattr(supply_chain, "scan", scan_image)
    monkeypatch.setattr(supply_chain, "run", lambda command: commands.append(command))
    assert not supply_chain.runtime_scan(tmp_path, tmp_path, products)
    record = json.loads((tmp_path / "build-record.json").read_text())
    ids = [record["image_ids"][name] for name in products]
    assert set(record["image_ids"]) == set(products)
    assert set(commands[0][4:]) == set(ids)
    assert sources == ["docker:" + image for image in ids]
    assert record["external_image_references"] == {}


def archive(*, link: bool = False) -> bytes:
    """通常fileまたはsymlinkを持つ合成archiveを作り、展開境界の検証へ渡す。"""
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as tar:
        item = tarfile.TarInfo("scanner")
        if link:
            item.type = tarfile.SYMTYPE
            item.linkname = "/etc/passwd"
            tar.addfile(item)
        else:
            item.size = 4
            tar.addfile(item, io.BytesIO(b"test"))
    return output.getvalue()


def test_installer_verifies_checksum_before_reading_binary() -> None:
    # 正しいarchiveだけを読み取り、配布物の改変を実行前に拒否する。
    payload = archive()
    digest = hashlib.sha256(payload).hexdigest()
    assert extract_binary(payload, digest, "scanner") == b"test"
    with pytest.raises(ValueError, match="checksum"):
        extract_binary(payload + b"tampered", digest, "scanner")


def test_installer_rejects_symlink_even_with_valid_checksum() -> None:
    # hashが正しくても、host fileへのlinkをbinaryとして扱わない。
    payload = archive(link=True)
    with pytest.raises(ValueError, match="member"):
        extract_binary(payload, hashlib.sha256(payload).hexdigest(), "scanner")


@pytest.mark.parametrize(
    "severity,state,blocked",
    [
        ("High", "fixed", True),
        ("Critical", "fixed", True),
        ("Medium", "fixed", False),
        ("High", "not-fixed", False),
        ("High", "", False),
    ],
)
def test_vulnerability_gate_matches_documented_fix_policy(
    severity: str, state: str, blocked: bool
) -> None:
    # 全件reportを維持しつつ、修正可能なHigh/Criticalだけが必須検査を停止させる。
    report = {
        "descriptor": {},
        "matches": [{"vulnerability": {"severity": severity, "fix": {"state": state}}}],
    }
    assert bool(blocking_findings(report)) is blocked


@pytest.mark.parametrize(
    "report",
    [
        {},
        {"matches": None, "descriptor": {}},
        {"matches": [{"vulnerability": {"severity": "new-value"}}], "descriptor": {}},
        {
            "matches": [
                {"vulnerability": {"severity": "High", "fix": {"state": "new-value"}}}
            ],
            "descriptor": {},
        },
    ],
)
def test_missing_or_unknown_scanner_results_fail_closed(report: dict) -> None:
    # report破損・未知enumを脆弱性なしへ変換しない。
    with pytest.raises(ValueError):
        blocking_findings(report)


def test_build_record_hashes_artifacts_and_records_source(tmp_path: Path) -> None:
    # 生成物をhashでsource commitと紐付け、local recordを署名済みと偽らない。
    payload = b"synthetic archive"
    (tmp_path / "runtime.tar").write_bytes(payload)
    write_record(tmp_path, {"backend": "sha256:" + "a" * 64})
    result = json.loads((tmp_path / "build-record.json").read_text())
    assert result["files"]["runtime.tar"] == hashlib.sha256(payload).hexdigest()
    assert result["product_version"] == APP_VERSION
    assert len(result["source_commit"]) == 40
    assert isinstance(result["worktree_dirty"], bool)
    assert result["image_ids"]["backend"].startswith("sha256:")
    assert "signature" not in result


def test_runtime_scan_rejects_missing_sandbox(tmp_path: Path) -> None:
    # 更新したsandboxをscan対象から落とした呼出しは、Docker操作より前に拒否する。
    with pytest.raises(ValueError, match="all five"):
        supply_chain.runtime_scan(tmp_path, tmp_path, {"backend": "test"})


def candidate_reports(tmp_path: Path) -> dict[str, str]:
    """5 imageのIDとarchive hashを持つ配備候補を作り、IDの対応を返す。"""
    ids = {
        name: "sha256:" + hashlib.sha256(name.encode()).hexdigest()
        for name in ("backend", "runner", "frontend", "db", "sandbox")
    }
    payload = b"synthetic archive"
    (tmp_path / "runtime.tar").write_bytes(payload)
    (tmp_path / "build-record.json").write_text(
        json.dumps(
            {
                "image_ids": ids,
                "files": {"runtime.tar": hashlib.sha256(payload).hexdigest()},
            }
        )
    )
    return ids


def test_load_candidate_tags_exactly_the_scanned_images(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # 同じrunのarchiveを読み込み、記録したIDの存在を確認してからCI用tagを付ける。
    ids = candidate_reports(tmp_path)
    commands: list[list[str]] = []
    monkeypatch.setattr(supply_chain, "rootless", lambda: None)
    monkeypatch.setattr(supply_chain, "run", lambda command: commands.append(command))
    monkeypatch.setattr(
        supply_chain.subprocess,
        "run",
        lambda command, **kwargs: SimpleNamespace(stdout=command[-1] + "\n"),
    )
    assert supply_chain.load_candidate(tmp_path) == ids
    assert commands[0] == ["docker", "load", "--input", str(tmp_path / "runtime.tar")]
    assert commands[1:] == [
        ["docker", "tag", image, f"soj-{name}:ci"] for name, image in ids.items()
    ]


@pytest.mark.parametrize("corruption", ["archive", "missing", "tag", "loaded"])
def test_load_candidate_rejects_unscanned_images(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, corruption: str
) -> None:
    # 破損archive、ID欠落、mutable tag、読込後のID不一致ではtagを付けずに失敗する。
    ids = candidate_reports(tmp_path)
    record = json.loads((tmp_path / "build-record.json").read_text())
    if corruption == "archive":
        (tmp_path / "runtime.tar").write_bytes(b"tampered")
    elif corruption == "missing":
        del record["image_ids"]["sandbox"]
    elif corruption == "tag":
        record["image_ids"]["db"] = "postgres:latest"
    (tmp_path / "build-record.json").write_text(json.dumps(record))
    commands: list[list[str]] = []
    monkeypatch.setattr(supply_chain, "rootless", lambda: None)
    monkeypatch.setattr(supply_chain, "run", lambda command: commands.append(command))
    monkeypatch.setattr(
        supply_chain.subprocess,
        "run",
        lambda command, **kwargs: SimpleNamespace(
            stdout=ids["backend"] if corruption == "loaded" else command[-1]
        ),
    )
    with pytest.raises(RuntimeError):
        supply_chain.load_candidate(tmp_path)
    assert not any(command[1] == "tag" for command in commands)
