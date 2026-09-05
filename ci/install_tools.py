"""review済みのversionとSHA-256で検証toolを取得する。system環境にはinstallしない。"""

import argparse
import hashlib
import io
import json
import platform
import tarfile
import urllib.request
from pathlib import Path


MANIFEST = Path(__file__).with_name("tools.json")


def extract_binary(payload: bytes, digest: str, name: str) -> bytes:
    """archiveの固定hashを検証し、指定の通常fileだけを取り出す。不一致やlinkは拒否する。"""
    if hashlib.sha256(payload).hexdigest() != digest:
        raise ValueError("tool archive checksum mismatch")
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        member = archive.getmember(name)
        if not member.isfile() or member.size > 256 * 1024 * 1024:
            raise ValueError("unexpected tool archive member")
        binary = archive.extractfile(member)
        assert binary is not None
        return binary.read()


def install(destination: Path, names: list[str]) -> None:
    """新しい専用directoryに検証済みbinaryを配置する。既存fileの上書きは行わない。"""
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise RuntimeError("CI tool pins currently support Linux x86_64 only")
    manifest = json.loads(MANIFEST.read_text())
    destination.mkdir(parents=True, exist_ok=False)
    for name in names:
        entry = manifest[name]
        if not entry["url"].startswith("https://github.com/"):
            raise ValueError("tool must come from its reviewed HTTPS release")
        with urllib.request.urlopen(entry["url"], timeout=120) as response:
            payload = response.read(256 * 1024 * 1024 + 1)
        binary = extract_binary(payload, entry["sha256"], entry["binary"])
        path = destination / name
        with path.open("xb") as output:
            output.write(binary)
        path.chmod(0o755)
        print(f"Verified {name} {entry['version']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("tools", nargs="+", choices=json.loads(MANIFEST.read_text()))
    args = parser.parse_args()
    install(args.destination, args.tools)
