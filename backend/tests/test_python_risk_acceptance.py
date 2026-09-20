import copy
import hashlib
import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import ci.supply_chain as supply_chain


@pytest.fixture
def risk(monkeypatch: pytest.MonkeyPatch) -> tuple[dict, dict, MagicMock]:
    """承認済みpolicyと合成Grype検出を用意し、実装照合だけを模擬する。"""
    policy = supply_chain.load_python_risk_policy()
    match = {
        "vulnerability": {
            "id": "CVE-2026-82049",
            "namespace": "nvd:cpe",
            "severity": "High",
            "fix": {"state": "fixed"},
        },
        "artifact": {
            **policy["artifact"],
            "locations": [
                {"path": path} for path in supply_chain.PYTHON_RUNTIME_FILES[:2]
            ],
        },
    }
    probe = MagicMock(return_value=copy.deepcopy(policy["runtime"]))
    monkeypatch.setattr(supply_chain, "inspect_python_runtime", probe)
    monkeypatch.setattr(supply_chain, "utc_today", lambda: date(2026, 9, 20))
    return policy, match, probe


@pytest.mark.parametrize("target", ["backend", "runner"])
@pytest.mark.parametrize("other_severity", [None, "High", "Critical"])
def test_scan_distinguishes_accepted_risk_and_keeps_other_findings_blocking(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    risk: tuple,
    target: str,
    other_severity: str | None,
) -> None:
    # 同じreportの未知High/Criticalは停止させ、未修正CVEを誤検出件数へ混入させない。
    _, match, probe = risk
    matches = [match]
    if other_severity:
        other = copy.deepcopy(match)
        other["vulnerability"].update(id="CVE-2099-0001", severity=other_severity)
        matches.append(other)
    raw = json.dumps({"descriptor": {}, "matches": matches})

    def scanner(command: list[str]) -> None:
        """実scannerのfile出力を模擬し、scanの判定・監査記録は本体を通す。"""
        if Path(command[0]).name == "syft":
            (tmp_path / f"{target}.syft.json").write_text(
                json.dumps({"artifacts": [match["artifact"]]})
            )
        else:
            (tmp_path / f"{target}.grype.json").write_text(raw)

    monkeypatch.setattr(supply_chain, "run", scanner)
    source = "docker:sha256:" + "a" * 64
    assert supply_chain.scan(tmp_path, source, tmp_path, target) is (
        other_severity is None
    )
    assert (tmp_path / f"{target}.grype.json").read_text() == raw
    summary = json.loads((tmp_path / f"{target}.summary.json").read_text())
    assert summary["exceptions"] == 0
    assert summary["risk_acceptances"] == 1
    assert summary["blocking"] == int(other_severity is not None)
    record = json.loads(
        (tmp_path / f"{target}.python-risk-acceptance.json").read_text()
    )
    assert record["kind"] == "risk-acceptance"
    assert record["source"] == source
    assert record["applied"] == [match]
    assert record["policy"]["remediation"]
    probe.assert_called_once_with(source[7:], supply_chain.PYTHON_RISK_FILES)
    supply_chain.write_record(tmp_path, {target: source[7:]})
    build = json.loads((tmp_path / "build-record.json").read_text())
    assert (
        build["python_risk_acceptance_policy_sha256"]
        == hashlib.sha256(supply_chain.PYTHON_RISK_POLICY.read_bytes()).hexdigest()
    )
    assert f"{target}.python-risk-acceptance.json" in build["files"]


@pytest.mark.parametrize(
    "day", [date(2026, 9, 19), date(2026, 10, 4), date(2027, 1, 1)]
)
def test_risk_acceptance_expires_without_runtime_probe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, risk: tuple, day: date
) -> None:
    # UTC失効日当日と承認前は全件停止へ戻し、自動延長しない。
    _, match, probe = risk
    monkeypatch.setattr(supply_chain, "utc_today", lambda: day)
    assert not supply_chain.python_runtime_risk_acceptances(
        [match], "docker:sha256:" + "a" * 64, "backend", tmp_path
    )
    probe.assert_not_called()


@pytest.mark.parametrize("target", ["dependencies", "frontend", "db", "sandbox"])
def test_risk_acceptance_excludes_other_products(
    tmp_path: Path, risk: tuple, target: str
) -> None:
    # 同一CVEでも承認範囲外の製品・lockへ許容を流用しない。
    _, match, probe = risk
    assert not supply_chain.python_runtime_risk_acceptances(
        [match], "dir:locks", target, tmp_path
    )
    probe.assert_not_called()


@pytest.mark.parametrize(
    "change", ["id", "namespace", "name", "version", "type", "purl", "locations"]
)
def test_risk_acceptance_requires_exact_finding(
    tmp_path: Path, risk: tuple, change: str
) -> None:
    # CVE・advisory・package・install先のいずれかが違えば許容しない。
    _, match, probe = risk
    if change in {"id", "namespace"}:
        match["vulnerability"][change] = "different"
    else:
        match["artifact"][change] = (
            [{"path": "/opt/python"}] if change == "locations" else "different"
        )
    assert not supply_chain.python_runtime_risk_acceptances(
        [match], "docker:sha256:" + "a" * 64, "runner", tmp_path
    )
    probe.assert_not_called()


@pytest.mark.parametrize("change", ["python", "expat", *supply_chain.PYTHON_RISK_FILES])
def test_changed_runtime_is_not_accepted(
    tmp_path: Path, risk: tuple, change: str
) -> None:
    # tarfileを含む実装hashまたはversionが変われば、以前の影響評価を流用しない。
    _, match, probe = risk
    if change in {"python", "expat"}:
        probe.return_value[change] = [0, 0, 0]
    else:
        probe.return_value["files"][change] = "0" * 64
    assert not supply_chain.python_runtime_risk_acceptances(
        [match], "docker:sha256:" + "a" * 64, "backend", tmp_path
    )


def test_probe_failure_keeps_risk_unverified(tmp_path: Path, risk: tuple) -> None:
    # 実装確認に失敗した場合は障害を伝え、適用済み記録を作らない。
    _, match, probe = risk
    probe.side_effect = RuntimeError("probe failed")
    with pytest.raises(RuntimeError, match="probe failed"):
        supply_chain.python_runtime_risk_acceptances(
            [match], "docker:sha256:" + "a" * 64, "runner", tmp_path
        )
    record = json.loads((tmp_path / "runner.python-risk-acceptance.json").read_text())
    assert record["applied"] == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("expires_on", "2026-10-05"),
        ("kind", "verified-fix"),
        ("targets", ["backend", "runner", "sandbox"]),
        ("accepted_by", ""),
        ("exposure", ""),
        ("remediation", ""),
        ("revoke_when", ""),
        ("vulnerabilities", []),
        ("runtime", {}),
    ],
)
def test_incomplete_or_broad_risk_policy_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    risk: tuple,
    field: str,
    value: object,
) -> None:
    # 承認理由・撤去条件の欠落、期限や対象の拡大、不完全実装は許容設定として拒否する。
    policy, _, _ = risk
    policy[field] = value
    path = tmp_path / "risk.json"
    path.write_text(json.dumps(policy))
    monkeypatch.setattr(supply_chain, "PYTHON_RISK_POLICY", path)
    with pytest.raises(ValueError):
        supply_chain.load_python_risk_policy()
