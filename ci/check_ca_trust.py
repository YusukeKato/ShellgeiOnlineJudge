"""rootlessの実imageからCAを読み、漏えいCAの拒否と正常TLSの許可をoffline検証する。"""

import argparse
import os
import re
import shlex
import subprocess
import tempfile
from contextlib import closing
from pathlib import Path
from typing import Any

import docker


FIXTURES = Path(__file__).resolve().parents[1] / "backend/tests/fixtures/emudhra"
VERIFICATION_TIME = "1792627200"  # 2026-10-22 UTC。失効日到達をCA拒否と誤認しない。
MARKER = "SOJ_CA_STORE "
PYTHON_STORES = r"""
import importlib.util, pathlib, zipfile
for module in ['certifi', 'pip._vendor.certifi']:
    try:
        spec = importlib.util.find_spec(module)
    except ModuleNotFoundError:
        spec = None
    if spec:
        package = __import__(module, fromlist=['where'])
        print('SOJ_CA_STORE ' + module)
        print(pathlib.Path(package.where()).read_text())
import ensurepip
if importlib.util.find_spec('playwright'):
    import os
    if os.environ.get('NODE_OPTIONS') != '--use-openssl-ca':
        raise RuntimeError('Playwright private Node must exclusively use the inspected OS CA')
for wheel in (pathlib.Path(ensurepip.__file__).parent / '_bundled').glob('pip-*.whl'):
    with zipfile.ZipFile(wheel) as archive:
        print('SOJ_CA_STORE ensurepip/' + wheel.name)
        print(archive.read('pip/_vendor/certifi/cacert.pem').decode())
spec = importlib.util.find_spec('virtualenv')
if spec:
    import sys
    from virtualenv.seed.wheels.embed import get_embed_wheel
    # このimageのPythonへ実際に選択されるseedを、virtualenv自身のhash検証を通して読む。
    selected = get_embed_wheel('pip', f'{sys.version_info.major}.{sys.version_info.minor}')
    if selected is None:
        raise RuntimeError('no virtualenv pip seed for the image Python')
    with zipfile.ZipFile(selected.path) as archive:
        print('SOJ_CA_STORE virtualenv-selected/' + selected.path.name)
        print(archive.read('pip/_vendor/certifi/cacert.pem').decode())

"""


def parse_stores(output: str) -> dict[str, str]:
    """固定markerで区切られた公開PEMだけを受け取り、不完全なstoreは拒否する。"""
    stores = {}
    for block in output.split(MARKER)[1:]:
        name, _, bundle = block.partition("\n")
        if name in stores or "-----BEGIN CERTIFICATE-----" not in bundle:
            raise ValueError(f"invalid CA store: {name}")
        stores[name] = bundle
    if not stores:
        raise ValueError("image has no inspectable CA store")
    return stores


def inspect_stores(client: Any, image: str) -> dict[str, str]:
    """通信・mount・書込みなしでCAの各コピーを読み、timeout時も専用containerを回収する。"""
    script = r"""
set -eu
printf 'SOJ_CA_STORE os-bundle\n'
cat /etc/ssl/certs/ca-certificates.crt
set -- /etc/ssl/certs/*.[0-9]*
if test -f "$1"; then
    printf 'SOJ_CA_STORE os-hashed-directory\n'
    for cert in /etc/ssl/certs/*.[0-9]*; do cat "$cert"; done
fi
"""
    for python in ("/usr/local/bin/python", "/opt/venv/bin/python"):
        script += (
            f"\nif test -x {python}; then {python} -I -c "
            + shlex.quote(
                PYTHON_STORES.replace("SOJ_CA_STORE ", f"SOJ_CA_STORE {python}/")
            )
            + "; fi\n"
        )
    script += """
if command -v node >/dev/null; then
    printf 'SOJ_CA_STORE node-builtin\\n'
    node -e 'console.log(require("tls").rootCertificates.join("\\n"))'
fi
"""
    container = client.containers.create(
        client.images.get(image).id,
        entrypoint="/bin/sh",
        command=["-c", script],
        network_mode="none",
        read_only=True,
        cap_drop=["ALL"],
        security_opt=["no-new-privileges:true"],
        pids_limit=32,
        mem_limit="256m",
        memswap_limit="256m",
        nano_cpus=500_000_000,
        environment={"PYTHONDONTWRITEBYTECODE": "1"},
    )
    try:
        container.start()
        if container.wait(timeout=60)["StatusCode"] != 0:
            raise RuntimeError(container.logs().decode(errors="replace"))
        return parse_stores(container.logs(stdout=True, stderr=False).decode())
    finally:
        container.remove(force=True, v=True)


def verify_store(bundle: str, fixtures: Path = FIXTURES) -> None:
    """12 chainをissuer不信頼で拒否し、無関係な正常chainは同じ条件で許可する。"""
    compromised = sorted(fixtures.glob("*-emudhra.we-have-a-problem.com.pem"))
    if len(compromised) != 12:
        raise ValueError("expected all twelve compromised TLS chain fixtures")
    with tempfile.TemporaryDirectory(prefix="soj-ca-check-") as directory:
        ca = Path(directory) / "ca.pem"
        ca.write_text(bundle)
        for chain in [*compromised, fixtures / "shellgei-online-judge.com.pem"]:
            result = subprocess.run(
                [
                    "openssl",
                    "verify",
                    "-no-CApath",
                    "-no-CAstore",
                    "-CAfile",
                    str(ca),
                    "-attime",
                    VERIFICATION_TIME,
                    "-purpose",
                    "sslserver",
                    "-verify_hostname",
                    chain.stem,
                    "-untrusted",
                    str(chain),
                    str(chain),
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if chain in compromised:
                if (
                    result.returncode == 0
                    or re.search(r"error (20|21) at \d+ depth", result.stderr) is None
                ):
                    raise ValueError(f"compromised chain not distrusted: {chain.name}")
            elif result.returncode != 0:
                raise ValueError(f"legitimate TLS chain rejected: {result.stderr}")


def check_images(images: list[str]) -> None:
    """明示されたlocal rootless daemonの既存imageを検査し、1 storeの失敗でも停止する。"""
    if not os.environ.get("DOCKER_HOST", "").startswith("unix://"):
        raise RuntimeError("set DOCKER_HOST to a local rootless Unix socket")
    with closing(docker.from_env(timeout=30)) as client:
        if "name=rootless" not in client.info()["SecurityOptions"]:
            raise RuntimeError("rootful Docker is not allowed")
        for image in images:
            for name, bundle in inspect_stores(client, image).items():
                verify_store(bundle)
                print(
                    f"{image}: {name}: 12 distrusted, legitimate control accepted",
                    flush=True,
                )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("images", nargs="+")
    check_images(parser.parse_args().images)
