import logging
from datetime import datetime
from typing import Annotated

import pytz
from fastapi import APIRouter, Header, HTTPException, Response

from models.model_shellgei import ShellgeiData, ShellgeiResultResponse
from scripts.execution_log_persistence import (
    ExecutionLogPersistenceError,
    persist_execution_log_async,
)
from scripts.input_validation import ProblemId
from scripts.judge import ShellgeiJudge
from scripts.problem_catalog import PROBLEM_LIST_CACHE_CONTROL
from scripts.problem_repository import get_problem_repository
from scripts.runner_client import (
    RunnerBusyError,
    RunnerUnavailableError,
    runner_gateway,
)

router = APIRouter()
shellgei_judge = ShellgeiJudge()
logger = logging.getLogger(__name__)


@router.post("/shellgei")
async def post_shellgei(shellgei_data: ShellgeiData) -> ShellgeiResultResponse:
    """提出commandをrunnerで実行・判定・記録し、既存形式の結果を返す。

    入力は検証済みのcommandとproblem ID。未登録問題は404を送出し、runnerの
    混雑・停止やDB保存失敗は既存のerror responseへ変換する。
    """
    japan_timezone = pytz.timezone("Asia/Tokyo")
    japan_date = datetime.now(japan_timezone)

    if get_problem_repository().get(shellgei_data.problem_id) is None:
        raise HTTPException(status_code=404, detail="Problem not found")

    # シェル芸の実行
    shellgei_str = shellgei_data.shellgei
    problem_id_str = shellgei_data.problem_id
    try:
        execution = await runner_gateway.execute(shellgei_str, problem_id_str)
    except RunnerBusyError:
        return ShellgeiResultResponse(
            output="Error: server is busy.",
            id="-1",
            date=f"{japan_date.strftime('%Y-%m-%d %H:%M:%S')}",
            image="",
            image_media_type=None,
            judge="4",
        )
    except RunnerUnavailableError:
        return ShellgeiResultResponse(
            output="Error: runner is unavailable.",
            id="-1",
            date=f"{japan_date.strftime('%Y-%m-%d %H:%M:%S')}",
            image="",
            image_media_type=None,
            judge="4",
        )
    output = execution.legacy_output()
    artifact = execution.artifact
    image = artifact.data if artifact is not None else ""
    image_media_type = artifact.media_type if artifact is not None else None
    judge_result = shellgei_judge.judge(execution, problem_id_str)
    judge = judge_result.legacy_code()

    try:
        log_id = await persist_execution_log_async(
            problem_id_str,
            shellgei_str,
            output,
            judge,
        )
    except ExecutionLogPersistenceError:
        logger.warning("Execution log persistence unavailable")
        log_id = -1

    return ShellgeiResultResponse(
        output=output,
        id=str(log_id),
        date=f"{japan_date.strftime('%Y-%m-%d %H:%M:%S')}",
        image=image,
        image_media_type=image_media_type,
        judge=judge,
    )


@router.get("/problems")
async def get_problems_list(
    if_none_match: Annotated[
        str | None,
        Header(alias="If-None-Match"),
    ] = None,
) -> Response:
    """検証済みrepositoryの問題一覧をETag付きResponseとして返す。

    入力のIf-None-Matchが現在のETagと一致する場合は、本文なしの304を返す。
    """
    catalog = get_problem_repository().catalog
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
async def get_problem(problem_id: ProblemId) -> dict[str, str]:
    """入力problem IDの詳細を既存API形式で返し、未登録なら404を送出する。"""
    record = get_problem_repository().get(problem_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Problem not found")
    return record.api_detail()
