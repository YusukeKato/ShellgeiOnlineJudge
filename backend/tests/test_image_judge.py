import base64
from io import BytesIO

import pytest
from PIL import Image

from soj_shared.models.problem import (
    ImageArtifactSpecification,
    ImageJudgeSpecification,
    ImageMediaType,
)
from soj_backend.judge import JudgeReason, JudgeVerdict, judge_image
from soj_shared.runner_protocol import ExecutionArtifact


def _image_bytes(
    image_format: str,
    *,
    color: tuple[int, int, int] = (255, 0, 0),
    quality: int = 75,
    size: tuple[int, int] = (2, 2),
) -> bytes:
    # 指定形式・色・JPEG品質・寸法の画像をmemory生成し、encoded bytesを返す。
    output = BytesIO()
    Image.new("RGB", size, color).save(
        output,
        format=image_format,
        quality=quality,
    )
    return output.getvalue()


JPEG = _image_bytes("JPEG")
GIF = _image_bytes("GIF")


def _specification(
    *,
    path: str = "media/output.jpg",
    media_type: ImageMediaType = "image/jpeg",
) -> ImageJudgeSpecification:
    # 任意のpathとMIMEを持つexact-pixel画像判定仕様を返す。
    return ImageJudgeSpecification(
        type="image",
        comparison="exact_pixels",
        artifact=ImageArtifactSpecification(
            path=path,
            media_type=media_type,
            max_bytes=750_000,
        ),
    )


def _artifact(
    payload: bytes,
    *,
    path: str = "media/output.jpg",
    media_type: ImageMediaType = "image/jpeg",
) -> ExecutionArtifact:
    # 入力画像bytesをBase64化し、任意のpathとMIMEを持つ取得artifactとして返す。
    return ExecutionArtifact(
        path=path,
        media_type=media_type,
        data=base64.b64encode(payload).decode("ascii"),
    )


@pytest.mark.parametrize(
    "payload,path,media_type",
    [
        (JPEG, "media/output.jpg", "image/jpeg"),
        (GIF, "media/output.gif", "image/gif"),
    ],
)
def test_image_judge_accepts_exact_jpeg_and_gif_pixels(
    payload: bytes,
    path: str,
    media_type: ImageMediaType,
) -> None:
    # JPEGとGIFで宣言形式・寸法・全画素が一致する場合に正解になることを確認する。
    result = judge_image(
        _specification(path=path, media_type=media_type),
        payload,
        _artifact(payload, path=path, media_type=media_type),
    )

    assert result.verdict is JudgeVerdict.ACCEPTED
    assert result.reason is None


@pytest.mark.parametrize(
    "actual,reason",
    [
        (None, JudgeReason.ARTIFACT_MISSING),
        (
            ExecutionArtifact(
                path="media/output.jpg",
                media_type="image/jpeg",
                data="not-valid-base64!",
            ),
            JudgeReason.ARTIFACT_INVALID,
        ),
        (_artifact(b"not-a-jpeg"), JudgeReason.ARTIFACT_INVALID),
        (_artifact(b"\xff\xd8prefix-only\xff\xd9"), JudgeReason.ARTIFACT_INVALID),
        (
            _artifact(JPEG, path="media/other.jpg"),
            JudgeReason.ARTIFACT_PATH_MISMATCH,
        ),
        (
            _artifact(JPEG, media_type="image/gif"),
            JudgeReason.ARTIFACT_MEDIA_TYPE_MISMATCH,
        ),
    ],
)
def test_image_judge_rejects_missing_corrupt_or_mismatched_artifact(
    actual: ExecutionArtifact | None,
    reason: JudgeReason,
) -> None:
    # 欠損、破損、headerだけの一致、path・MIME不一致を指定理由で拒否することを確認する。
    result = judge_image(_specification(), JPEG, actual)

    assert result.verdict is JudgeVerdict.WRONG_IMAGE
    assert result.reason is reason


def test_image_judge_rejects_decoded_pixel_difference() -> None:
    # headerが正常でもdecode後の画素が1色でも異なる画像を不一致にすることを確認する。
    expected = _image_bytes("JPEG", color=(255, 0, 0))
    actual = _image_bytes("JPEG", color=(0, 0, 255))

    result = judge_image(_specification(), expected, _artifact(actual))

    assert result.verdict is JudgeVerdict.WRONG_IMAGE
    assert result.reason is JudgeReason.IMAGE_MISMATCH


def test_image_judge_ignores_encoder_metadata_when_pixels_match() -> None:
    # JPEG品質等のencoding差があってもdecode後の寸法・画素が同じなら正解になることを確認する。
    expected = _image_bytes("JPEG", quality=75)
    differently_encoded = _image_bytes("JPEG", quality=95)

    result = judge_image(
        _specification(),
        expected,
        _artifact(differently_encoded),
    )

    assert expected != differently_encoded
    assert result.verdict is JudgeVerdict.ACCEPTED


def test_image_judge_rejects_decoded_pixel_limit() -> None:
    # 圧縮後byteが小さくてもdecode後の総画素上限を超える画像を拒否することを確認する。
    oversized = _image_bytes("JPEG", size=(2001, 2000))

    result = judge_image(_specification(), oversized, _artifact(oversized))

    assert result.verdict is JudgeVerdict.WRONG_IMAGE
    assert result.reason is JudgeReason.ARTIFACT_INVALID
