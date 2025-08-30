from fastapi import APIRouter
from models.model_shellgei import ShellgeiData, ShellgeiResultResponse

router = APIRouter()

@router.post("/shellgei")
async def post_shellgei(shellgei_data: ShellgeiData) -> ShellgeiResultResponse:
    return ShellgeiResultResponse(
        output="output",
        id="id",
        date="date",
        image="image",
        judge="judge"
    )