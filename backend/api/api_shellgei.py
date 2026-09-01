from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Response

from models.model_shellgei import ShellgeiData, ShellgeiResultResponse
from models.submission import SubmissionResult, SubmissionStatus
from scripts.execution_log_repository import (
    async_execution_log_repo,
)
from scripts.input_validation import ProblemId
from scripts.judge import ShellgeiJudge
from scripts.problem_catalog import PROBLEM_LIST_CACHE_CONTROL
from scripts.problem_repository import LoadedProblemRepo, get_problem_repository
from scripts.runner_client import runner_gateway
from scripts.submit_solution import JAPAN_TIMEZONE, SubmitSolutionService

router = APIRouter()
shellgei_judge = ShellgeiJudge()
submit_solution_service = SubmitSolutionService(
    problem_repository=LoadedProblemRepo(),
    runner=runner_gateway,
    judge=shellgei_judge,
    execution_logs=async_execution_log_repo,
)


def _submission_date(result: SubmissionResult) -> str:
    """入力提出結果のtimezone付き時刻を、既存APIの日時文字列へ変換して返す。"""
    return result.submitted_at.astimezone(JAPAN_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")


def _unavailable_response(
    message: str, result: SubmissionResult
) -> ShellgeiResultResponse:
    """入力messageと提出時刻から、既存API互換の実行不能responseを返す。"""
    return ShellgeiResultResponse(
        output=message,
        id="-1",
        date=_submission_date(result),
        image="",
        image_media_type=None,
        judge="4",
    )


def _submission_response(result: SubmissionResult) -> ShellgeiResultResponse:
    """HTTP非依存の提出結果を既存public responseへ変換し、未登録問題は404にする。"""
    if result.status is SubmissionStatus.PROBLEM_NOT_FOUND:
        raise HTTPException(status_code=404, detail="Problem not found")
    if result.status is SubmissionStatus.RUNNER_BUSY:
        return _unavailable_response("Error: server is busy.", result)
    if result.status is SubmissionStatus.RUNNER_UNAVAILABLE:
        return _unavailable_response("Error: runner is unavailable.", result)

    execution = result.execution
    judgment = result.judgment
    if execution is None or judgment is None:
        raise RuntimeError("completed submission result is inconsistent")
    artifact = execution.artifact
    return ShellgeiResultResponse(
        output=execution.legacy_output(),
        id=str(result.log_id if result.log_id is not None else -1),
        date=_submission_date(result),
        image=artifact.data if artifact is not None else "",
        image_media_type=artifact.media_type if artifact is not None else None,
        judge=judgment.legacy_code(),
    )


@router.post("/shellgei")
async def post_shellgei(shellgei_data: ShellgeiData) -> ShellgeiResultResponse:
    """検証済みHTTP requestをuse caseへ渡し、既存形式のresponseへ変換する。

    入力は検証済みのcommandとproblem ID。処理順やinfra例外を扱わず、型付き
    提出結果のstatusとfieldだけをHTTP statusおよびresponse bodyへmappingする。
    """
    result = await submit_solution_service.submit(
        shellgei_data.shellgei,
        shellgei_data.problem_id,
    )
    return _submission_response(result)


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
