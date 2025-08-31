from fastapi import APIRouter
from models.model_shellgei import ShellgeiData, ShellgeiResultResponse
from scripts.run_shellgei import ShellgeiDockerClient

router = APIRouter()
docker_client = ShellgeiDockerClient()

@router.post("/shellgei")
async def post_shellgei(
    shellgei_data: ShellgeiData,
    ) -> ShellgeiResultResponse:
    shellgei_str = shellgei_data.shellgei.replace('\r', '')
    problem_id_str = shellgei_data.problem_id.replace('\r', '')
    output = await docker_client.run_with_timeout(shellgei_str, problem_id_str)
    return ShellgeiResultResponse(
        output=output,
        image="image",
        judge="judge"
    )