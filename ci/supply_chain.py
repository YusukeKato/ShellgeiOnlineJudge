"""CIとlocalで同じSBOM・脆弱性検査を行い、検出とtool障害を区別して終了する。"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import docker

from soj_runner.container_manager import DEFAULT_IMAGE_ID


ROOT = Path(__file__).resolve().parents[1]
PYTHON_EXCEPTION_POLICY = ROOT / "ci/python-runtime-exceptions.json"
PYTHON_RUNTIME_FILES = (
    "/usr/local/bin/python3.12",
    "/usr/local/lib/libpython3.12.so.1.0",
    "/usr/local/lib/python3.12/http/cookies.py",
    "/usr/local/lib/python3.12/lib-dynload/pyexpat.cpython-312-x86_64-linux-gnu.so",
    "/usr/local/lib/python3.12/lib-dynload/_elementtree.cpython-312-x86_64-linux-gnu.so",
)


def utc_today() -> date:
    """CIのtimezoneに左右されないUTC日付で例外の失効を判定する。"""
    return datetime.now(timezone.utc).date()


def load_python_exception_policy() -> dict[str, Any]:
    """根拠・有限期限・実装hashを必須とし、不完全な例外設定はCI障害として拒否する。"""
    policy = json.loads(PYTHON_EXCEPTION_POLICY.read_text())
    if policy["schema_version"] != 1:
        raise ValueError("unknown Python exception policy schema")
    duration = date.fromisoformat(policy["expires_on"]) - date.fromisoformat(
        policy["reviewed_on"]
    )
    if not 0 < duration.days <= 31:
        raise ValueError("Python exception review period must be at most 31 days")
    if set(policy["artifact"]) != {"name", "version", "type", "purl"} or not all(
        isinstance(value, str) and value for value in policy["artifact"].values()
    ):
        raise ValueError("invalid Python exception artifact")
    if not policy["id"] or policy["namespace"] != "nvd:cpe":
        raise ValueError("invalid Python exception identity")
    runtime = policy["runtime"]
    if set(runtime) != {"python", "expat", "files"} or any(
        not isinstance(runtime[key], list)
        or len(runtime[key]) != 3
        or any(type(part) is not int or part < 0 for part in runtime[key])
        for key in ("python", "expat")
    ):
        raise ValueError("invalid Python exception runtime")
    if set(runtime["files"]) != set(PYTHON_RUNTIME_FILES) or not all(
        isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest)
        for digest in runtime["files"].values()
    ):
        raise ValueError("invalid Python exception file hashes")
    items = policy["vulnerabilities"]
    if not items or len({item["id"] for item in items}) != len(items):
        raise ValueError("empty or duplicate Python exception vulnerabilities")
    for item in items:
        if (
            not re.fullmatch(r"CVE-\d{4}-\d{4,}", item["id"])
            or not item["reason"]
            or not item["evidence"]
            or not all(url.startswith("https://") for url in item["evidence"])
        ):
            raise ValueError("Python exception requires advisory evidence")
    return policy


def inspect_python_runtime(image_id: str) -> dict[str, Any]:
    """scan対象IDのPython・Expat・実装hashを隔離containerで読み、timeoutや例外でも回収する。"""
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        raise ValueError("Python inspection requires an immutable image ID")
    if not os.environ.get("DOCKER_HOST", "").startswith("unix://"):
        raise RuntimeError("set DOCKER_HOST to a local rootless Unix socket")
    script = """
import hashlib, json, pathlib, pyexpat, sys
files = {}
for name in json.loads(sys.argv[1]):
    path = pathlib.Path(name)
    files[name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
print(json.dumps(dict(python=list(sys.version_info[:3]), expat=list(pyexpat.version_info), files=files)))
"""
    client = docker.from_env(timeout=30)
    try:
        if "name=rootless" not in client.info()["SecurityOptions"]:
            raise RuntimeError("rootful Docker is not allowed")
        container = client.containers.create(
            image_id,
            entrypoint="/usr/local/bin/python3.12",
            command=["-I", "-c", script, json.dumps(PYTHON_RUNTIME_FILES)],
            working_dir="/",
            user="10001:10001",
            network_mode="none",
            read_only=True,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],
            pids_limit=16,
            mem_limit="64m",
            memswap_limit="64m",
            nano_cpus=500_000_000,
        )
        try:
            container.start()
            if container.wait(timeout=30)["StatusCode"] != 0:
                raise RuntimeError("Python runtime inspection failed")
            result = json.loads(container.logs(stdout=True, stderr=False))
            if not isinstance(result, dict):
                raise ValueError("invalid Python runtime inspection result")
            return result
        finally:
            container.remove(force=True, v=True)
    finally:
        client.close()


def python_runtime_exceptions(
    blocked: list[dict[str, Any]], source: str, target: str, reports: Path
) -> list[dict[str, Any]]:
    """本番Pythonの期限付き例外を実装hashまで照合し、元reportを変更せず適用記録と対象を返す。"""
    if target not in {"backend", "runner"}:
        return []
    if not re.fullmatch(r"docker:sha256:[0-9a-f]{64}", source):
        raise ValueError("Python exceptions require the scanned immutable image ID")
    policy = load_python_exception_policy()
    today = utc_today()
    active = (
        date.fromisoformat(policy["reviewed_on"])
        <= today
        < date.fromisoformat(policy["expires_on"])
    )
    ids = {item["id"] for item in policy["vulnerabilities"]}
    candidates = [
        match
        for match in blocked
        if match["vulnerability"].get("id") in ids
        and match["vulnerability"].get("namespace") == policy["namespace"]
        and all(
            match.get("artifact", {}).get(key) == value
            for key, value in policy["artifact"].items()
        )
        and {
            location["path"]
            for location in match.get("artifact", {}).get("locations", [])
        }
        == set(PYTHON_RUNTIME_FILES[:2])
    ]
    record: dict[str, Any] = {
        "policy": policy,
        "evaluated_on": today.isoformat(),
        "source": source,
        "status": "unverified" if active and candidates else "not-applicable",
        "applied": [],
    }
    if not active:
        record["status"] = "inactive"
    path = reports / f"{target}.python-exceptions.json"
    # probe障害時も適用していないことと評価時のpolicyをartifactへ残す。
    path.write_text(json.dumps(record, indent=2) + "\n")
    exempted = []
    if active and candidates:
        record["runtime"] = inspect_python_runtime(source.removeprefix("docker:"))
        record["status"] = "runtime-mismatch"
        if record["runtime"] == policy["runtime"]:
            exempted = candidates
            record["status"] = "applied"
            record["applied"] = candidates
        path.write_text(json.dumps(record, indent=2) + "\n")
    return exempted


def run(command: list[str], *, expected: tuple[int, ...] = (0,)) -> int:
    """shellを介さず上限付きでtoolを呼び、想定外終了は検査失敗として伝える。"""
    result = subprocess.run(command, check=False, timeout=600)
    if result.returncode not in expected:
        raise RuntimeError(
            f"{Path(command[0]).name} failed with exit {result.returncode}"
        )
    return result.returncode


def scan(tools: Path, source: str, reports: Path, name: str) -> bool:
    """SBOMと全検出を保存し、検証済み期限付き例外を除く修正可能なHigh/CriticalでFalseを返す。"""
    sbom = reports / f"{name}.syft.json"
    run(
        [
            str(tools / "syft"),
            source,
            "--source-name",
            name,
            "-o",
            f"syft-json={sbom}",
            "-o",
            f"cyclonedx-json={reports / f'{name}.cdx.json'}",
        ]
    )
    inventory = json.loads(sbom.read_text())
    if not inventory.get("artifacts"):
        raise RuntimeError(f"{name}: package inventory is empty")
    if name == "dependencies" and not {"fastapi", "react"} <= {
        package["name"] for package in inventory["artifacts"]
    }:
        raise RuntimeError("both Python and frontend lock inventories are required")
    report = reports / f"{name}.grype.json"
    run([str(tools / "grype"), f"sbom:{sbom}", "-o", "json", "--file", str(report)])
    result = json.loads(report.read_text())
    blocked = blocking_findings(result)
    exempted = python_runtime_exceptions(blocked, source, name, reports)
    summary = {
        "target": name,
        "packages": len(inventory["artifacts"]),
        "findings": len(result["matches"]),
        "blocking_before_exceptions": len(blocked),
        "exceptions": len(exempted),
        "blocking": len(blocked) - len(exempted),
    }
    (reports / f"{name}.summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary), flush=True)
    return len(blocked) == len(exempted)


def blocking_findings(report: dict[str, Any]) -> list[dict[str, Any]]:
    """完全なGrype reportを要求し、修正可能なHigh/Criticalを抽出する。欠損は成功扱いにしない。"""
    if not isinstance(report.get("matches"), list) or not isinstance(
        report.get("descriptor"), dict
    ):
        raise ValueError("invalid Grype report")
    blocked = []
    for match in report["matches"]:
        vulnerability = match["vulnerability"]
        severity = vulnerability["severity"]
        if severity not in {
            "Unknown",
            "Negligible",
            "Low",
            "Medium",
            "High",
            "Critical",
        }:
            raise ValueError("unknown Grype severity")
        fix = vulnerability["fix"]
        # Grype v0.118.0のOS advisoryには未設定の空stateもある。修正版なしの場合だけ未知扱いする。
        if fix["state"] == "" and not fix.get("versions"):
            continue
        if fix["state"] not in {"fixed", "not-fixed", "unknown", "wont-fix"}:
            raise ValueError("unknown Grype fix state")
        if severity in {"High", "Critical"} and fix["state"] == "fixed":
            blocked.append(match)
    return blocked


def source_scan(tools: Path, reports: Path) -> bool:
    """lock fileだけを専用directoryへcopyし、ホストvenvや未追跡資産を依存inventoryへ混入させない。"""
    with tempfile.TemporaryDirectory(prefix="soj-locks-") as directory:
        target = Path(directory)
        (target / "frontend").mkdir()
        for filename in (
            "pyproject.toml",
            "poetry.lock",
            "frontend/package.json",
            "frontend/yarn.lock",
        ):
            shutil.copyfile(ROOT / filename, target / filename)
        return scan(tools, f"dir:{target}", reports, "dependencies")


def rootless() -> None:
    """imageを扱う前に明示的なlocal Unix socketとrootless daemonを確認し、fallbackを拒否する。"""
    if not os.environ.get("DOCKER_HOST", "").startswith("unix://"):
        raise RuntimeError("set DOCKER_HOST to a local rootless Unix socket")
    result = subprocess.run(
        ["docker", "info", "--format", "{{json .SecurityOptions}}"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if "name=rootless" not in json.loads(result.stdout):
        raise RuntimeError("rootful Docker is not allowed")


def runtime_scan(tools: Path, reports: Path, products: dict[str, str]) -> bool:
    """DBを含む本番4 imageと正本のsandboxをscanし、配布候補archiveとhash記録を作る。"""
    rootless()
    external = {
        "sandbox": DEFAULT_IMAGE_ID,
    }
    ids = {}
    ok = True
    for name, reference in products.items():
        result = subprocess.run(
            ["docker", "image", "inspect", "--format", "{{.Id}}", reference],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        ids[name] = result.stdout.strip()
        ok = scan(tools, f"docker:{ids[name]}", reports, name) and ok
    # 大きなsandboxをdaemonから再exportせず、正本の固定digestから直接inventoryを作る。
    for name, reference in external.items():
        if "@sha256:" not in reference:
            raise ValueError("infrastructure images must be digest pinned")
        ok = scan(tools, f"registry:{reference}", reports, name) and ok
    archive = reports / "runtime.tar"
    # scanしたimmutable IDを指定し、並行したtag更新が保存内容へ影響しないようにする。
    run(["docker", "save", "--output", str(archive), *(ids[name] for name in products)])
    write_record(reports, ids, external)
    return ok


def write_record(
    reports: Path, image_ids: dict[str, str], external: dict[str, str] | None = None
) -> None:
    """source commit・dirty状態・scan対象ID・file hashを記録する。署名保証はGitHub attestationが担う。"""
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    dirty = bool(
        subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    )
    files = {}
    for path in sorted(reports.iterdir()):
        if path.name == "build-record.json" or not path.is_file():
            continue
        with path.open("rb") as stream:
            files[path.name] = hashlib.file_digest(stream, "sha256").hexdigest()
    record = {
        "source_commit": commit,
        "worktree_dirty": dirty,
        "image_ids": image_ids,
        "external_image_references": external or {},
        "tool_manifest_sha256": hashlib.sha256(
            (ROOT / "ci/tools.json").read_bytes()
        ).hexdigest(),
        "python_exception_policy_sha256": hashlib.sha256(
            PYTHON_EXCEPTION_POLICY.read_bytes()
        ).hexdigest(),
        "files": files,
    }
    (reports / "build-record.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n"
    )


def scanner_fixtures(tools: Path, reports: Path) -> None:
    """実scannerが合成secretと既知の脆弱packageを検出し、破損SBOMを成功扱いしないことを確認する。"""
    with tempfile.TemporaryDirectory(prefix="soj-scanner-fixture-") as directory:
        fixture = Path(directory)
        # 合成tokenを実行時に組み立て、無効な検証値をtracked sourceの例外へ登録しない。
        token = (
            "ghp_" + hashlib.sha256(b"SOJ synthetic scanner fixture").hexdigest()[:36]
        )
        (fixture / "token.txt").write_text("token=" + token)
        run(
            [
                str(tools / "gitleaks"),
                "dir",
                str(fixture),
                "--redact=100",
                "--no-banner",
            ],
            expected=(1,),
        )
        run(
            [
                str(tools / "grype"),
                "pkg:pypi/django@1.2",
                "--only-fixed",
                "--fail-on",
                "high",
                "-o",
                "json",
                "--file",
                str(reports / "fixture.grype.json"),
            ],
            expected=(2,),
        )
        (fixture / "broken.json").write_text("not a valid SBOM")
        run(
            [str(tools / "grype"), f"sbom:{fixture / 'broken.json'}", "--quiet"],
            expected=(1,),
        )


def main() -> None:
    """専用tool・report・cache directoryを引数で受け、検出なら2、tool障害なら例外で終了する。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("source", "runtime", "fixtures"))
    parser.add_argument("--tools", type=Path, required=True)
    parser.add_argument("--reports", type=Path, required=True)
    parser.add_argument("--backend", default="soj-backend:ci")
    parser.add_argument("--runner", default="soj-runner:ci")
    parser.add_argument("--frontend", default="soj-frontend:ci")
    parser.add_argument("--db", default="soj-db:ci")
    args = parser.parse_args()
    args.reports.mkdir(parents=True, exist_ok=False)
    os.environ.setdefault("SYFT_CACHE_DIR", str(args.reports.parent / "syft-cache"))
    os.environ.update(
        {
            "SYFT_CHECK_FOR_APP_UPDATE": "false",
            "GRYPE_CHECK_FOR_APP_UPDATE": "false",
            "GRYPE_DB_AUTO_UPDATE": "false",
        }
    )
    if args.mode == "fixtures":
        scanner_fixtures(args.tools, args.reports)
        return
    if args.mode == "source":
        ok = source_scan(args.tools, args.reports)
        write_record(args.reports, {})
    else:
        ok = runtime_scan(
            args.tools,
            args.reports,
            {
                name: getattr(args, name)
                for name in ("backend", "runner", "frontend", "db")
            },
        )
    raise SystemExit(0 if ok else 2)


if __name__ == "__main__":
    main()
