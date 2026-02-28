import pytz
import yaml
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
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
    shellgei_data: ShellgeiData, db: Session = Depends(get_db)
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
        output=output[:1000],  # 出力を1000文字に制限
        judge=judge,
    )
    db.add(new_log)
    db.commit()
    db.refresh(new_log)  # 保存して自動採番されたIDを取得

    return ShellgeiResultResponse(
        output=output,
        id=str(new_log.id),  # DBで自動採番されたIDを返す
        date=f"{japan_date.strftime('%Y-%m-%d %H:%M:%S')}",
        image=image,
        judge=judge,
    )


@router.get("/problems/{problem_id}")
async def get_problem(problem_id: str):
    # backend/problems/yaml_data/{problem_id}.yaml を参照
    base_dir = Path(__file__).resolve().parent.parent
    yaml_path = base_dir / "problems" / "yaml_data" / f"{problem_id}.yaml"

    if not yaml_path.exists():
        raise HTTPException(status_code=404, detail="Problem not found")

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return {
        "title_ja": data.get("title_ja", ""),
        "title_en": data.get("title_en", ""),
        "statement_ja": data.get("statement_ja", ""),
        "statement_en": data.get("statement_en", ""),
        "input": data.get("input", ""),
        "expected_output": data.get("expected_output", ""),
        "answer": data.get("answer", ""),
        "image": f"/image/{problem_id}.jpg",  # Nginxから配信される画像URL
    }
