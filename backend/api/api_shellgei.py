import pytz
from pathlib import Path
from typing import Annotated

import yaml
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from datetime import datetime
from sqlalchemy.orm import Session
from models.model_shellgei import ShellgeiData, ShellgeiResultResponse
from models.model_db import ExecutionLog
from scripts.database import get_db
from scripts.execution_log_retention import prune_execution_logs
from scripts.input_validation import ProblemId
from scripts.problem_catalog import (
    PROBLEM_LIST_CACHE_CONTROL,
    get_problem_catalog,
)
from scripts.runner_client import RunnerBusyError, RunnerUnavailableError, runner_client
from scripts.judge import ShellgeiJudge

router = APIRouter()
shellgei_judge = ShellgeiJudge()


@router.post("/shellgei")
async def post_shellgei(
    shellgei_data: ShellgeiData, db: Session = Depends(get_db)
) -> ShellgeiResultResponse:
    japan_timezone = pytz.timezone("Asia/Tokyo")
    japan_date = datetime.now(japan_timezone)

    base_dir = Path(__file__).resolve().parent.parent
    yaml_path = base_dir / "problems" / "yaml_data" / f"{shellgei_data.problem_id}.yaml"
    if not yaml_path.is_file():
        raise HTTPException(status_code=404, detail="Problem not found")

    # シェル芸の実行
    shellgei_str = shellgei_data.shellgei
    problem_id_str = shellgei_data.problem_id
    try:
        output, image = await runner_client.run(shellgei_str, problem_id_str)
    except RunnerBusyError:
        return ShellgeiResultResponse(
            output="Error: server is busy.",
            id="-1",
            date=f"{japan_date.strftime('%Y-%m-%d %H:%M:%S')}",
            image="",
            judge="4",
        )
    except RunnerUnavailableError:
        return ShellgeiResultResponse(
            output="Error: runner is unavailable.",
            id="-1",
            date=f"{japan_date.strftime('%Y-%m-%d %H:%M:%S')}",
            image="",
            judge="4",
        )
    judge: str = shellgei_judge.judge(output, image, problem_id_str)

    # DBに実行結果を保存
    new_log = ExecutionLog(
        problem_id=problem_id_str,
        shellgei=shellgei_str,
        output=output[:1000],  # 出力を1000文字に制限
        judge=judge,
    )
    db.add(new_log)
    prune_execution_logs(db)
    db.commit()
    db.refresh(new_log)  # 保存して自動採番されたIDを取得

    return ShellgeiResultResponse(
        output=output,
        id=str(new_log.id),  # DBで自動採番されたIDを返す
        date=f"{japan_date.strftime('%Y-%m-%d %H:%M:%S')}",
        image=image,
        judge=judge,
    )


@router.get("/problems")
async def get_problems_list(
    if_none_match: Annotated[
        str | None,
        Header(alias="If-None-Match"),
    ] = None,
) -> Response:
    catalog = get_problem_catalog()
    headers = {
        "Cache-Control": PROBLEM_LIST_CACHE_CONTROL,
        "ETag": catalog.etag,
    }
    if if_none_match is not None and catalog.etag in {
        value.strip() for value in if_none_match.split(",")
    }:
        return Response(status_code=304, headers=headers)
    return Response(
        content=catalog.response_body,
        media_type="application/json",
        headers=headers,
    )


@router.get("/problems/{problem_id}")
async def get_problem(problem_id: ProblemId):
    # backend/problems/yaml_data/{problem_id}.yaml を参照
    base_dir = Path(__file__).resolve().parent.parent
    yaml_path = base_dir / "problems" / "yaml_data" / f"{problem_id}.yaml"

    if not yaml_path.is_file():
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
