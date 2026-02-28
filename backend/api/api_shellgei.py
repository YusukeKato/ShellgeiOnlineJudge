from fastapi import APIRouter, Depends
from datetime import datetime, timezone
import pytz
from sqlalchemy.orm import Session
from sqlalchemy import desc
from models.model_shellgei import ShellgeiData, ShellgeiResultResponse
from models.model_db import ExecutionLog
from scripts.database import get_db
from scripts.run_shellgei import ShellgeiDockerClient
from scripts.judge import ShellgeiJudge

router = APIRouter()
docker_client = ShellgeiDockerClient()
shellgei_judge = ShellgeiJudge()

# 実行間隔の制限 [s]
TIME_LIMIT_SECONDS = 0.1

@router.post("/shellgei")
async def post_shellgei(
    shellgei_data: ShellgeiData,
    db: Session = Depends(get_db)
) -> ShellgeiResultResponse:
    japan_timezone = pytz.timezone("Asia/Tokyo")
    japan_date = datetime.now(japan_timezone)

    # DBから最新の実行ログを取得して実行間隔をチェック
    latest_log = db.query(ExecutionLog).order_by(desc(ExecutionLog.created_at)).first()
    if latest_log:
        time_diff = (datetime.now(timezone.utc) - latest_log.created_at).total_seconds()
        if time_diff < TIME_LIMIT_SECONDS:
            return ShellgeiResultResponse(
                output="Error: server is busy.",
                id="-1",
                date=f"{japan_date.strftime('%Y-%m-%d %H:%M:%S')}",
                image="",
                judge="4",
            )

    # シェル芸の実行
    shellgei_str = shellgei_data.shellgei.replace("\r", "")
    problem_id_str = shellgei_data.problem_id.replace("\r", "")
    output, image = await docker_client.run_with_timeout(shellgei_str, problem_id_str)
    judge: str = shellgei_judge.judge(output, image, problem_id_str)

    # DBに実行結果を保存
    new_log = ExecutionLog(
        problem_id=problem_id_str,
        shellgei=shellgei_str,
        output=output[:1000], # 出力を1000文字に制限
        judge=judge
    )
    db.add(new_log)
    db.commit()
    db.refresh(new_log) # 保存して自動採番されたIDを取得

    return ShellgeiResultResponse(
        output=output,
        id=str(new_log.id), # DBで自動採番されたIDを返す
        date=f"{japan_date.strftime('%Y-%m-%d %H:%M:%S')}",
        image=image,
        judge=judge,
    )