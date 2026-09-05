import re
from pathlib import Path

import yaml

from scripts.container_manager import DEFAULT_IMAGE_ID


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPOSITORY_ROOT / "docker-compose.yml"
PINNED_IMAGE_REFERENCE = re.compile(r"[^@\s]+@sha256:[0-9a-f]{64}")


def _dockerfile_base_images(path: Path) -> list[str]:
    """入力Dockerfileから、既出stageの再利用を除く外部FROM imageを返す。"""
    stages: set[str] = set()
    images: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.upper().startswith("FROM "):
            continue
        fields = line.split()
        if fields[1] not in stages:
            images.append(fields[1])
        if len(fields) == 4 and fields[2].upper() == "AS":
            stages.add(fields[3])
    return images


def test_runtime_and_sandbox_images_are_pinned_by_digest() -> None:
    # backend・frontend・DB・sandboxの全runtime imageがtagだけでなくsha256 digestを持つことを確認する。
    compose = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    image_references = [
        *_dockerfile_base_images(REPOSITORY_ROOT / "backend" / "Dockerfile"),
        *_dockerfile_base_images(REPOSITORY_ROOT / "frontend" / "Dockerfile"),
        compose["services"]["db"]["image"],
        DEFAULT_IMAGE_ID,
    ]

    assert len(set(image_references)) == 5
    assert all(
        PINNED_IMAGE_REFERENCE.fullmatch(reference) is not None
        for reference in image_references
    )


def test_frontend_configuration_is_built_in_and_only_tls_files_are_mounted() -> None:
    # nginx設定をhostからmountせず、実行時mountをread-onlyのTLS証明書と秘密鍵だけに限定する。
    compose = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    volumes = compose["services"]["frontend"]["volumes"]

    assert volumes == [
        "${TLS_CERTIFICATE_PATH:-./deploy/tls/fullchain.pem}:/etc/nginx/tls/fullchain.pem:ro",
        "${TLS_PRIVATE_KEY_PATH:-./deploy/tls/privkey.pem}:/etc/nginx/tls/privkey.pem:ro",
    ]
    assert all("/etc/nginx/conf.d" not in volume for volume in volumes)


def test_browser_test_image_base_is_pinned_by_digest() -> None:
    # 任意E2E用imageも、browser packageとは別にOS/Pythonのbaseをdigestで固定する。
    references = _dockerfile_base_images(
        REPOSITORY_ROOT / "backend/tests/integration/browser/Dockerfile"
    )
    assert references
    assert all(PINNED_IMAGE_REFERENCE.fullmatch(reference) for reference in references)
