"""CIとlocalで同じSBOM・脆弱性検査を行い、検出とtool障害を区別して終了する。"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import yaml

from scripts.container_manager import DEFAULT_IMAGE_ID


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], *, expected: tuple[int, ...] = (0,)) -> int:
    """shellを介さず上限付きでtoolを呼び、想定外終了は検査失敗として伝える。"""
    result = subprocess.run(command, check=False, timeout=600)
    if result.returncode not in expected:
        raise RuntimeError(
            f"{Path(command[0]).name} failed with exit {result.returncode}"
        )
    return result.returncode


def scan(tools: Path, source: str, reports: Path, name: str) -> bool:
    """同じinventoryからSBOMと全脆弱性reportを作り、修正版のあるHigh/CriticalでFalseを返す。"""
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
    summary = {
        "target": name,
        "packages": len(inventory["artifacts"]),
        "findings": len(result["matches"]),
        "blocking": len(blocked),
    }
    (reports / f"{name}.summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary), flush=True)
    return not blocked


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
    """本番3 imageと正本のDB/sandbox imageをscanし、配布候補archiveとhash記録を作る。"""
    rootless()
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    external = {
        "db": compose["services"]["db"]["image"],
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
            {name: getattr(args, name) for name in ("backend", "runner", "frontend")},
        )
    raise SystemExit(0 if ok else 2)


if __name__ == "__main__":
    main()
