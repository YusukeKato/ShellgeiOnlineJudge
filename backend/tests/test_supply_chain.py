import hashlib
import io
import json
import tarfile
from pathlib import Path

import pytest

from ci.install_tools import extract_binary
from ci.supply_chain import blocking_findings, write_record


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
    assert len(result["source_commit"]) == 40
    assert isinstance(result["worktree_dirty"], bool)
    assert result["image_ids"]["backend"].startswith("sha256:")
    assert "signature" not in result
