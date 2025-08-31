from fastapi import APIRouter
from datetime import datetime
import pytz
from models.model_shellgei import ShellgeiData, ShellgeiResultResponse
from scripts.run_shellgei import ShellgeiDockerClient
from scripts.judge import ShellgeiJudge
from scripts.time_manager import TimeManager
from scripts.log_manager import LogManager

router = APIRouter()
docker_client = ShellgeiDockerClient()
shellgei_judge = ShellgeiJudge()
time_manager = TimeManager()
log_manager = LogManager()

@router.post("/shellgei")
async def post_shellgei(
    shellgei_data: ShellgeiData,
    ) -> ShellgeiResultResponse:
    japan_timezone = pytz.timezone('Asia/Tokyo')
    japan_date = datetime.now(japan_timezone)
    if not time_manager.is_time_exceeded():
        return ShellgeiResultResponse(
            output="Error: server is busy.",
            id="-1",
            date=f"{japan_date.strftime('%Y-%m-%d %H:%M:%S')}",
            image="",
            judge="4",
        )
    shellgei_str = shellgei_data.shellgei.replace('\r', '')
    problem_id_str = shellgei_data.problem_id.replace('\r', '')
    output, image = await docker_client.run_with_timeout(shellgei_str, problem_id_str)
    judge: str = shellgei_judge.judge(output, image, problem_id_str)
    new_id: str = log_manager.update_shellgei_id()
    return ShellgeiResultResponse(
        output=output,
        id=new_id,
        date=f"{japan_date.strftime('%Y-%m-%d %H:%M:%S')}",
        image=image,
        judge=judge,
    )