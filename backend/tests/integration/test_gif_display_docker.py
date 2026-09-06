"""実sandboxで表示GIFの回収・制限・request分離を確認する。"""

import os
import uuid
from collections.abc import Iterator
from io import BytesIO
import base64

import pytest
from PIL import Image

from soj_backend.artifact_display import select_display_artifact
from soj_shared.models.execution import ExecutionStatus
from soj_runner.container_manager import ContainerManager
from soj_runner.run_shellgei import ShellgeiDockerClient
from tests.test_run_shellgei import PROBLEM_REPOSITORY

pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(
        os.getenv("SOJ_RUN_DOCKER_TESTS") != "1",
        reason="explicit rootless Docker opt-in required",
    ),
]
GIF_COMMAND = "seq 0 9 | xargs -I@ bash -c 'textimg \"$1\" -F100 | convert - miff:-' _ @ | convert -delay 10 miff:- media/output.gif"
SMALL_GIF = "convert -size 8x8 -delay 10 xc:red xc:blue -loop 0 media/output.gif"


@pytest.fixture(scope="module")
def gif_client() -> Iterator[ShellgeiDockerClient]:
    """専用ownerの1枠だけで実行し、終了時は今回のsandboxとthreadを回収する。"""
    manager = ContainerManager(pool_size=1, owner_id=f"gif-test-{uuid.uuid4().hex}")
    client = ShellgeiDockerClient(manager, problem_repository=PROBLEM_REPOSITORY)
    try:
        manager.initialize_pool()
        yield client
    finally:
        manager.shutdown_pool()
        client.close()


def test_original_gif_command_preserves_animation_and_does_not_leak(
    gif_client: ShellgeiDockerClient,
) -> None:
    """報告されたコマンドの全10frameとdelayを保持し、次の提出へ画像を残さない。"""
    result = gif_client.exec_shellgei(GIF_COMMAND, "STANDARD-00000001", 10, 1000)
    assert result.status is ExecutionStatus.COMPLETED
    assert result.exit_code == 0
    artifact = select_display_artifact(result)
    assert artifact is not None and artifact.media_type == "image/gif"
    with Image.open(BytesIO(base64.b64decode(artifact.data))) as image:
        frame_count = getattr(image, "n_frames", 1)
        assert frame_count == 10
        for frame in range(frame_count):
            image.seek(frame)
            assert image.info["duration"] == 100
    fresh = gif_client.exec_shellgei("echo test", "STANDARD-00000001", 10, 1000)
    assert fresh.status is ExecutionStatus.COMPLETED
    assert fresh.display_artifact is None


@pytest.mark.parametrize(
    "command",
    [
        "ln -s /etc/passwd /media/output.gif",
        "mkfifo /media/output.gif",
        "mkdir /media/output.gif",
        "printf 'GIF89a;' > media/output.gif",
        "head -c 750001 /dev/zero > media/output.gif",
        SMALL_GIF
        + "; mv /media/output.gif /media/other.gif; ln -s /media/other.gif /media/output.gif",
        "rm /work/media; mkdir /work/media; " + SMALL_GIF,
    ],
)
def test_display_capture_rejects_unsafe_missing_and_invalid_files(
    gif_client: ShellgeiDockerClient, command: str
) -> None:
    """link・FIFO・directory・不正形式・巨大file・差替えたwork/mediaを表示せず、読込で待たない。"""
    result = gif_client.exec_shellgei(command, "STANDARD-00000001", 3, 1000)
    assert result.status is ExecutionStatus.COMPLETED
    assert select_display_artifact(result) is None


@pytest.mark.parametrize(
    "command, status",
    [
        (SMALL_GIF + "; sleep 20", ExecutionStatus.TIMED_OUT),
        (SMALL_GIF + "; seq 1 2000", ExecutionStatus.OUTPUT_LIMIT),
    ],
)
def test_limited_execution_discards_display_gif(
    gif_client: ShellgeiDockerClient, command: str, status: ExecutionStatus
) -> None:
    """GIF生成後でもtimeout・出力超過なら画像を捨て、停止と次の実行を妨げない。"""
    result = gif_client.exec_shellgei(command, "STANDARD-00000001", 2, 1000)
    assert result.status is status
    assert result.artifact is None and result.display_artifact is None
