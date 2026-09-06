"""採点用artifactを変更せず、公開APIで表示する画像だけを選ぶ。"""

import base64
import binascii

from soj_backend.image_validation import decode_image_pixels, matches_media_type
from soj_shared.models.execution import ExecutionArtifact, ExecutionResult


def select_display_artifact(execution: ExecutionResult) -> ExecutionArtifact | None:
    """形式・全frameの画素上限を検証したGIFを優先し、無効なら従来の判定画像へ戻す。

    bytesを再encodeせず返すため、アニメーションのdelay・loop設定を保持する。
    不正な表示用GIFは判定や保存の成功に影響させない。
    """
    candidate = execution.display_artifact
    if candidate is not None:
        try:
            payload = base64.b64decode(candidate.data, validate=True)
            if (
                matches_media_type(payload, "image/gif")
                and decode_image_pixels(payload, "image/gif") is not None
            ):
                return candidate
        except (binascii.Error, ValueError):
            pass
    return execution.artifact
