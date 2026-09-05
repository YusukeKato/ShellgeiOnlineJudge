import copy
import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import ci.supply_chain as supply_chain


@pytest.fixture
def policy() -> dict:
    """review対象の正本を読み、合成reportと実装の適用条件を揃える。"""
    return json.loads(
        (supply_chain.ROOT / "ci/python-runtime-exceptions.json").read_text()
    )


@pytest.fixture
def matches(policy: dict) -> list[dict]:
    """実Grypeのfieldに沿った3件を作り、raw reportを変更せずに評価する。"""
    return [
        {
            "vulnerability": {
                "id": item["id"],
                "namespace": policy["namespace"],
                "severity": "High",
                "fix": {"state": "fixed"},
            },
            "artifact": {
                **policy["artifact"],
                "id": "python-artifact",
                "locations": [
                    {"path": path} for path in supply_chain.PYTHON_RUNTIME_FILES[:2]
                ],
            },
        }
        for item in policy["vulnerabilities"]
    ]


@pytest.fixture
def proof(monkeypatch: pytest.MonkeyPatch, policy: dict) -> MagicMock:
    """同じimmutable imageから取得した実version・実装hashの照合結果を模擬する。"""
    mock = MagicMock(return_value=policy["runtime"])
    monkeypatch.setattr(supply_chain, "inspect_python_runtime", mock)
    monkeypatch.setattr(supply_chain, "utc_today", lambda: date(2026, 9, 5))
    return mock


def test_verified_python_findings_are_recorded_without_mutating_raw_report(
    tmp_path: Path, matches: list[dict], proof: MagicMock
) -> None:
    # 3件だけを例外へ分類し、同じreport内の新しいCVEは引き続き停止対象とする。
    unknown = copy.deepcopy(matches[0])
    unknown["vulnerability"]["id"] = "CVE-2099-0001"
    matches.append(unknown)
    original = copy.deepcopy(matches)
    source = "docker:sha256:" + "a" * 64
    result = supply_chain.python_runtime_exceptions(
        matches, source, "backend", tmp_path
    )
    assert result == matches[:3]
    assert matches == original
    proof.assert_called_once_with(source.removeprefix("docker:"))
    record = json.loads((tmp_path / "backend.python-exceptions.json").read_text())
    assert record["status"] == "applied"
    assert len(record["applied"]) == 3
    assert record["source"] == source
    assert record["policy"]["expires_on"] == "2026-10-05"


@pytest.mark.parametrize(
    "target", ["dependencies", "frontend", "db", "sandbox", "unknown"]
)
def test_exceptions_do_not_apply_to_other_targets(
    tmp_path: Path, matches: list[dict], proof: MagicMock, target: str
) -> None:
    # 同じCVEやversionが他の対象に存在しても適用せず、containerも起動しない。
    assert not supply_chain.python_runtime_exceptions(
        matches, "docker:sha256:" + "a" * 64, target, tmp_path
    )
    proof.assert_not_called()


@pytest.mark.parametrize("day", [date(2026, 9, 4), date(2026, 10, 5), date(2027, 1, 1)])
def test_expired_or_future_review_does_not_exempt_findings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    matches: list[dict],
    proof: MagicMock,
    day: date,
) -> None:
    # UTCで有効期間の外なら自動延長せず、全件を停止対象へ戻す。
    monkeypatch.setattr(supply_chain, "utc_today", lambda: day)
    assert not supply_chain.python_runtime_exceptions(
        matches, "docker:sha256:" + "a" * 64, "runner", tmp_path
    )
    proof.assert_not_called()


@pytest.mark.parametrize(
    "field,value",
    [
        ("version", "3.12.13"),
        ("name", "libexpat"),
        ("type", "python"),
        ("purl", "pkg:pypi/python@3.12.14"),
    ],
)
def test_different_artifact_is_not_exempted(
    tmp_path: Path, matches: list[dict], proof: MagicMock, field: str, value: str
) -> None:
    # CVE一致だけで別packageや旧versionを除外しない。
    for match in matches:
        match["artifact"][field] = value
    assert not supply_chain.python_runtime_exceptions(
        matches, "docker:sha256:" + "a" * 64, "backend", tmp_path
    )
    proof.assert_not_called()


@pytest.mark.parametrize("change", ["python", "expat", "files", "namespace"])
def test_unverified_runtime_or_advisory_remains_blocking(
    tmp_path: Path, matches: list[dict], proof: MagicMock, policy: dict, change: str
) -> None:
    # 古いExpat・改変実装・version違い・別advisoryを、公開修正情報だけで安全と判断しない。
    runtime = copy.deepcopy(policy["runtime"])
    if change == "namespace":
        for match in matches:
            match["vulnerability"]["namespace"] = "other:advisory"
    elif change == "files":
        runtime["files"]["/usr/local/lib/python3.12/http/cookies.py"] = "0" * 64
    else:
        runtime[change] = [0, 0, 0]
    proof.return_value = runtime
    assert not supply_chain.python_runtime_exceptions(
        matches, "docker:sha256:" + "a" * 64, "backend", tmp_path
    )


def test_runtime_inspection_failure_is_not_ignored(
    tmp_path: Path, matches: list[dict], proof: MagicMock
) -> None:
    # runtime確認の障害は判定成功へ変換せず、CIを失敗させる。
    proof.side_effect = RuntimeError("probe failed")
    with pytest.raises(RuntimeError, match="probe failed"):
        supply_chain.python_runtime_exceptions(
            matches, "docker:sha256:" + "a" * 64, "backend", tmp_path
        )


@pytest.mark.parametrize("failure", [False, True])
def test_runtime_probe_always_removes_its_isolated_container(
    monkeypatch: pytest.MonkeyPatch, policy: dict, failure: bool
) -> None:
    # 成功・wait timeoutの両方で専用containerを回収し、rootless・通信禁止・read-onlyを維持する。
    monkeypatch.setenv("DOCKER_HOST", "unix:///test/rootless.sock")
    client = MagicMock()
    client.info.return_value = {"SecurityOptions": ["name=rootless"]}
    container = client.containers.create.return_value
    container.wait.return_value = {"StatusCode": 0}
    container.logs.return_value = json.dumps(policy["runtime"]).encode()
    monkeypatch.setattr(supply_chain.docker, "from_env", lambda **kwargs: client)
    if failure:
        container.wait.side_effect = TimeoutError("probe timeout")
        with pytest.raises(TimeoutError):
            supply_chain.inspect_python_runtime("sha256:" + "a" * 64)
    else:
        assert (
            supply_chain.inspect_python_runtime("sha256:" + "a" * 64)
            == policy["runtime"]
        )
    container.remove.assert_called_once_with(force=True, v=True)
    client.close.assert_called_once()
    options = client.containers.create.call_args.kwargs
    assert options["network_mode"] == "none"
    assert options["read_only"]
    assert options["cap_drop"] == ["ALL"]
    assert options["security_opt"] == ["no-new-privileges:true"]
    assert options["user"] == "10001:10001"


def test_runtime_probe_rejects_rootful_daemon(monkeypatch: pytest.MonkeyPatch) -> None:
    # local socketでもrootlessでないdaemonへcontainerを作成しない。
    monkeypatch.setenv("DOCKER_HOST", "unix:///test/rootful.sock")
    client = MagicMock()
    client.info.return_value = {"SecurityOptions": []}
    monkeypatch.setattr(supply_chain.docker, "from_env", lambda **kwargs: client)
    with pytest.raises(RuntimeError, match="rootful"):
        supply_chain.inspect_python_runtime("sha256:" + "a" * 64)
    client.containers.create.assert_not_called()
    client.close.assert_called_once()


def test_unverified_install_location_is_not_exempted(
    tmp_path: Path, matches: list[dict], proof: MagicMock
) -> None:
    # 同versionでも別pathにあるPythonは、/usr/localの修正確認を流用して除外しない。
    for match in matches:
        match["artifact"]["locations"] = [{"path": "/opt/other/python"}]
    assert not supply_chain.python_runtime_exceptions(
        matches, "docker:sha256:" + "a" * 64, "backend", tmp_path
    )
    proof.assert_not_called()


@pytest.mark.parametrize(
    "source",
    ["docker:soj-backend:latest", "registry:python:latest", "docker:sha256:bad"],
)
def test_mutable_or_unverified_source_is_rejected(
    tmp_path: Path, matches: list[dict], proof: MagicMock, source: str
) -> None:
    # tag更新raceやregistryからの別対象へ、実imageの確認結果を適用しない。
    with pytest.raises(ValueError, match="immutable"):
        supply_chain.python_runtime_exceptions(matches, source, "backend", tmp_path)
    proof.assert_not_called()


@pytest.mark.parametrize("change", ["schema", "expiry", "hash", "evidence"])
def test_invalid_policy_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, policy: dict, change: str
) -> None:
    # 未知schema、長期期限、不完全なhashや根拠があれば、例外を有効にせずCI障害とする。
    if change == "schema":
        policy["schema_version"] = 2
    elif change == "expiry":
        policy["expires_on"] = "2099-01-01"
    elif change == "hash":
        policy["runtime"]["files"].pop(supply_chain.PYTHON_RUNTIME_FILES[0])
    else:
        policy["vulnerabilities"][0]["evidence"] = []
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(policy))
    monkeypatch.setattr(supply_chain, "PYTHON_EXCEPTION_POLICY", path)
    with pytest.raises(ValueError):
        supply_chain.load_python_exception_policy()


@pytest.mark.parametrize("unknown_cve", [False, True])
def test_scan_preserves_raw_report_and_uses_only_effective_gate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    matches: list[dict],
    proof: MagicMock,
    unknown_cve: bool,
) -> None:
    # scan全体でrawの3件を保持し、未知CVEを追加した場合だけ引き続き失敗する。
    if unknown_cve:
        unknown = copy.deepcopy(matches[0])
        unknown["vulnerability"]["id"] = "CVE-2099-0001"
        matches.append(unknown)
    report = {"descriptor": {}, "matches": matches}

    def run_scanner(command: list[str]) -> None:
        """scannerの出力fileだけを再現し、scan本体の判定とreport生成を実行する。"""
        if Path(command[0]).name == "syft":
            (tmp_path / "backend.syft.json").write_text(
                json.dumps({"artifacts": [matches[0]["artifact"]]})
            )
        else:
            (tmp_path / "backend.grype.json").write_text(json.dumps(report))

    monkeypatch.setattr(supply_chain, "run", run_scanner)
    assert (
        supply_chain.scan(tmp_path, "docker:sha256:" + "a" * 64, tmp_path, "backend")
        is not unknown_cve
    )
    assert json.loads((tmp_path / "backend.grype.json").read_text()) == report
    summary = json.loads((tmp_path / "backend.summary.json").read_text())
    assert summary["blocking_before_exceptions"] == 3 + unknown_cve
    assert summary["exceptions"] == 3
    assert summary["blocking"] == int(unknown_cve)
