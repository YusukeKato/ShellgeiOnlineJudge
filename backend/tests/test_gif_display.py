"""表示用GIFの回収・検証と、判定用artifactからの分離を確認する。"""

import base64
from io import BytesIO
from types import SimpleNamespace
from typing import Any

import pytest
from PIL import Image
from pydantic import ValidationError

from soj_backend.judge import ShellgeiJudge
from soj_backend.models.public_api import SubmitSolutionResponseV3
from soj_shared.models.execution import (
    ExecutionArtifact,
    ExecutionResult,
    ExecutionStatus,
)
from tests.test_public_api_v3 import _completed_submission
from tests.test_run_shellgei import FakeContainer, PROBLEM_REPOSITORY, make_client


def gif_bytes(size: tuple[int, int] = (10, 10)) -> bytes:
    """異なる2frameの正しいGIFを生成し、変換なしで返ることの比較に使う。"""
    stream = BytesIO()
    with (
        Image.new("RGB", size, "red") as first,
        Image.new("RGB", size, "blue") as second,
    ):
        first.save(
            stream,
            format="GIF",
            save_all=True,
            append_images=[second],
            duration=100,
            loop=0,
        )
    return stream.getvalue()


class GifContainer(FakeContainer):
    """表示GIFだけを追加で供給し、判定画像と独立した読み取りを観測する。"""

    def __init__(self, gif: bytes) -> None:
        """表示用bytesを受け取り、実問題の参照JPEGと正解stdoutを用意する。"""
        super().__init__(output=b"test\n", image=b"jpeg-data")
        self.gif = gif

    def exec_run(self, command: Any, **kwargs: Any) -> Any:
        """固定GIF pathをnonblocking・nofollowで読む場合だけ追加bytesを返す。"""
        if command[0] == "/usr/bin/dd":
            assert "if=/media/output.gif" in command
            assert "iflag=nofollow,nonblock,count_bytes" in command
            assert kwargs == {"stdout": True, "stderr": False, "stream": True}
            self.commands.append(command)
            return SimpleNamespace(output=iter((self.gif,)))
        return super().exec_run(command, **kwargs)


@pytest.mark.parametrize("problem_id", ["STANDARD-00000001", "IMAGE-00000001"])
def test_generated_gif_reaches_public_response_without_changing_judgment(
    problem_id: str,
) -> None:
    """text/imageどちらでもGIFを表示し、採点は従来のstdoutまたは判定画像だけを使う。"""
    gif = gif_bytes()
    container = GifContainer(gif)
    client, manager = make_client(container)
    try:
        execution = client.exec_shellgei("generate gif", problem_id, 1, 1000)
        judgment = ShellgeiJudge(PROBLEM_REPOSITORY).judge(execution, problem_id)
        original = ShellgeiJudge(PROBLEM_REPOSITORY).judge(
            execution.model_copy(update={"display_artifact": None}), problem_id
        )
        assert judgment == original
        response = SubmitSolutionResponseV3.from_submission(
            _completed_submission(execution=execution, judgment=judgment)
        )
        assert response.artifact is not None
        assert response.artifact.media_type == "image/gif"
        assert base64.b64decode(response.artifact.data) == gif
        if problem_id.startswith("IMAGE"):
            assert (
                execution.artifact is not None
                and execution.artifact.media_type == "image/jpeg"
            )
        else:
            assert execution.artifact is None
        assert container.kill_calls == 1
        assert manager.release_stopped_values == [True]
    finally:
        client.close()


@pytest.mark.parametrize(
    "payload",
    [b"", b"not an image", b"GIF89a;", b"x" * 750_001, gif_bytes((1500, 1500))],
)
def test_invalid_or_oversized_gif_is_not_exposed(payload: bytes) -> None:
    """欠損・偽形式・byte上限・総画素上限超過のGIFを表示せず、textの判定は維持する。"""
    client, _ = make_client(GifContainer(payload))
    try:
        execution = client.exec_shellgei("generate gif", "STANDARD-00000001", 1, 1000)
        response = SubmitSolutionResponseV3.from_submission(
            _completed_submission(execution=execution)
        )
        assert response.artifact is None
    finally:
        client.close()


def test_display_artifact_uses_shared_payload_budget_and_fixed_identity() -> None:
    """二画像で従来のBase64合計上限を超えず、表示用には固定pathのGIFだけを許可する。"""
    execution = _completed_submission().execution
    assert execution is not None
    data = execution.model_dump()
    display = dict(
        path="media/output.gif",
        media_type="image/gif",
        data=base64.b64encode(gif_bytes()).decode(),
    )
    valid = ExecutionResult.model_validate({**data, "display_artifact": display})
    assert valid.model_dump()["display_artifact"] == display
    for changed in ({"path": "media/other.gif"}, {"media_type": "image/jpeg"}):
        with pytest.raises(ValidationError):
            ExecutionResult.model_validate(
                {**data, "display_artifact": {**display, **changed}}
            )
    with pytest.raises(ValidationError):
        ExecutionResult.model_validate(
            {
                **data,
                "artifact": ExecutionArtifact(
                    path="media/output.jpg",
                    media_type="image/jpeg",
                    data="A" * 1_000_000,
                ),
                "display_artifact": display,
            }
        )
    with pytest.raises(ValidationError):
        ExecutionResult.model_validate(
            {
                **data,
                "status": ExecutionStatus.TIMED_OUT,
                "timed_out": True,
                "display_artifact": display,
            }
        )


def test_invalid_display_gif_preserves_jpeg_and_exact_pixel_verdict() -> None:
    """破損GIFがあっても、正しい参照JPEGの採点と従来のJPEG表示を維持する。"""
    record = PROBLEM_REPOSITORY.get("IMAGE-00000001")
    assert record is not None
    container = GifContainer(b"GIF89a;")
    container.image = record.answer_image
    client, _ = make_client(container)
    try:
        execution = client.exec_shellgei("generate images", "IMAGE-00000001", 1, 1000)
        judgment = ShellgeiJudge(PROBLEM_REPOSITORY).judge(execution, "IMAGE-00000001")
        assert judgment.verdict.value == "accepted"
        response = SubmitSolutionResponseV3.from_submission(
            _completed_submission(execution=execution, judgment=judgment)
        )
        assert (
            response.artifact is not None
            and response.artifact.media_type == "image/jpeg"
        )
    finally:
        client.close()


def test_runner_reserves_judge_bytes_before_reading_display_gif() -> None:
    """JPEGが共有枠を使い切る場合、GIFを読まずに判定画像を上限内で返す。"""
    container = GifContainer(gif_bytes())
    container.image = b"x" * 750_000
    client, _ = make_client(container)
    try:
        execution = client.exec_shellgei("generate images", "IMAGE-00000001", 1, 1000)
        assert execution.artifact is not None
        assert execution.display_artifact is None
        assert not any(command[0] == "/usr/bin/dd" for command in container.commands)
    finally:
        client.close()


def test_gif_cannot_expand_canvas_in_later_frames() -> None:
    """後続frameのoffsetでcanvasを拡大するGIFを拒否し、宣言サイズによる画素制限回避を防ぐ。"""
    from soj_backend.artifact_display import select_display_artifact

    payload = bytearray(gif_bytes())
    descriptor = payload.rfind(b",")
    assert payload[descriptor + 5 : descriptor + 9] == b"\x0a\x00\x0a\x00"
    payload[descriptor + 1 : descriptor + 5] = (3000).to_bytes(2, "little") * 2
    execution = _completed_submission().execution
    assert execution is not None
    artifact = ExecutionArtifact(
        path="media/output.gif",
        media_type="image/gif",
        data=base64.b64encode(payload).decode(),
    )
    assert (
        select_display_artifact(
            execution.model_copy(update={"display_artifact": artifact})
        )
        is None
    )


def test_truncated_gif_frame_header_is_not_a_submission_error() -> None:
    """後続frameのheaderが途中で欠けたGIFを公開せず、decoderの例外をAPIへ漏らさない。"""
    from soj_backend.artifact_display import select_display_artifact

    payload = gif_bytes()
    descriptor = payload.rfind(b",")
    execution = _completed_submission().execution
    assert execution is not None
    for header_length in range(1, 10):
        artifact = ExecutionArtifact(
            path="media/output.gif",
            media_type="image/gif",
            data=base64.b64encode(
                payload[: descriptor + header_length] + b";"
            ).decode(),
        )
        assert (
            select_display_artifact(
                execution.model_copy(update={"display_artifact": artifact})
            )
            is None
        )
