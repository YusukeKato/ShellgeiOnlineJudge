from pydantic import BaseModel

from soj_shared.models.problem import ImageMediaType


class ShellgeiResultResponse(BaseModel):
    output: str
    id: str
    date: str
    image: str
    image_media_type: ImageMediaType | None
    judge: str
