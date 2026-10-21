"""既知のSHA-256でpipを初期更新し、古い同梱CAに依存した追加取得を防ぐ。"""

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path


PIP_VERSION = "26.2.2"
WHEEL_NAME = f"pip-{PIP_VERSION}-py3-none-any.whl"
WHEEL_URL = (
    "https://files.pythonhosted.org/packages/3f/06/"
    "3e4420302363fbb71be3c7f35ce042f54bfca330e3e66b3a2e3c4cca579f/" + WHEEL_NAME
)
WHEEL_SHA256 = "fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70"


def update_ensurepip(wheel: Path) -> None:
    """container用Pythonのseed wheelも置き換え、新規venvへの旧pip再導入を防ぐ。"""
    import ensurepip

    source = Path(ensurepip.__file__)
    content, count = re.subn(
        r'^_PIP_VERSION = "[^"]+"$',
        f'_PIP_VERSION = "{PIP_VERSION}"',
        source.read_text(),
        flags=re.MULTILINE,
    )
    if count != 1:
        raise RuntimeError("unknown ensurepip layout; refusing to change seed wheels")
    bundled = source.parent / "_bundled"
    shutil.copyfile(wheel, bundled / WHEEL_NAME)
    source.write_text(content)
    for old in bundled.glob("pip-*.whl"):
        if old.name != WHEEL_NAME:
            old.unlink()


def bootstrap(*, seed: bool = False) -> None:
    """wheelの取得・hash検証後だけoffline installし、不一致や失敗では後続を停止する。"""
    with urllib.request.urlopen(WHEEL_URL, timeout=60) as response:
        payload = response.read(4_000_001)
    if hashlib.sha256(payload).hexdigest() != WHEEL_SHA256:
        raise ValueError("pip wheel SHA-256 mismatch")
    with tempfile.TemporaryDirectory(prefix="soj-pip-") as directory:
        wheel = Path(directory) / WHEEL_NAME
        wheel.write_bytes(payload)
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "--isolated",
                "--disable-pip-version-check",
                "install",
                "--no-index",
                "--no-deps",
                "--no-cache-dir",
                "--upgrade",
                str(wheel),
            ],
            check=True,
            timeout=120,
        )
        if seed:
            update_ensurepip(wheel)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update-ensurepip", action="store_true")
    bootstrap(seed=parser.parse_args().update_ensurepip)
