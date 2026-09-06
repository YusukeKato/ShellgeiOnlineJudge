"""判定と表示で共有する、上限付きJPEG/GIF検証。"""

import warnings
import struct
from io import BytesIO

from PIL import Image, UnidentifiedImageError

MAX_DECODED_IMAGE_PIXELS = 4_000_000
# PillowがGIFの後続frameをseekする途中でも、巨大canvasの確保前に上限検査する。
# request単位でglobalを変更せず、backendで使うdecoderの固定上限として設定する。
Image.MAX_IMAGE_PIXELS = MAX_DECODED_IMAGE_PIXELS


def matches_media_type(payload: bytes, media_type: str) -> bool:
    """入力画像bytesが宣言MIMEの完全なJPEG/GIF外形ならTrueを返す。"""
    if media_type == "image/jpeg":
        return (
            len(payload) >= 4
            and payload.startswith(b"\xff\xd8")
            and payload.endswith(b"\xff\xd9")
        )
    return (
        len(payload) >= 7
        and payload[:6] in {b"GIF87a", b"GIF89a"}
        and payload.endswith(b";")
    )


def decode_image_pixels(
    payload: bytes,
    media_type: str,
) -> tuple[tuple[int, int], tuple[bytes, ...]] | None:
    """JPEG/GIF bytesを上限内でdecodeし、寸法と全frameのRGBA画素列を返す。"""
    expected_format = "JPEG" if media_type == "image/jpeg" else "GIF"
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(payload)) as image:
                if image.format != expected_format:
                    return None
                width, height = image.size
                frame_count = getattr(image, "n_frames", 1)
                if width * height * frame_count > MAX_DECODED_IMAGE_PIXELS:
                    return None
                frames: list[bytes] = []
                for frame_index in range(frame_count):
                    image.seek(frame_index)
                    if image.size != (width, height):
                        return None
                    frames.append(image.convert("RGBA").tobytes())
                return (width, height), tuple(frames)
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        OSError,
        EOFError,
        IndexError,
        struct.error,
        UnidentifiedImageError,
        ValueError,
    ):
        return None
