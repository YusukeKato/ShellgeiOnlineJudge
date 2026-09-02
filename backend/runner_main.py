from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse

from scripts.admission_control import sandbox_start_rate_limiter
from scripts.container_manager import manager
from scripts.problem_repository import get_problem_repository, load_problem_repository
from scripts.run_shellgei import SandboxBusyError, ShellgeiDockerClient
from scripts.runner_http_security import RunnerRequestSecurityMiddleware
from scripts.runner_protocol import (
    RUNNER_EXECUTE_PATH,
    RUNNER_HEALTH_PATH,
    RUNNER_PROTOCOL_VERSION,
    RUNNER_READINESS_PATH,
    RunnerExecutionRequest,
    RunnerExecutionResponse,
    RunnerReadinessResponse,
    RunnerReadinessStatus,
    get_runner_shared_secret,
)


docker_client = ShellgeiDockerClient()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """runner設定・問題data・Docker poolを準備し、終了時に全資源を破棄する。

    入力はFastAPI application。repository検証またはpool初期化に失敗した場合は
    例外を伝播し、内部実行APIのrequest受付を開始しない。
    """
    get_runner_shared_secret()
    load_problem_repository()
    manager.initialize_pool()
    try:
        yield
    finally:
        manager.begin_shutdown()
        docker_client.close()
        manager.shutdown_pool()


app = FastAPI(
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.add_middleware(RunnerRequestSecurityMiddleware)


@app.get(RUNNER_HEALTH_PATH)
async def health() -> dict[str, str]:
    """runner processのlivenessだけを示す固定statusを返す。"""
    return {"status": "ok"}


@app.get(
    RUNNER_READINESS_PATH,
    response_model=RunnerReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": RunnerReadinessResponse}},
)
async def readiness() -> RunnerReadinessResponse | JSONResponse:
    """problem revisionとsandbox poolが実行受付可能なら200、劣化時は503を返す。"""
    repository = get_problem_repository()
    readiness_status = (
        RunnerReadinessStatus.READY
        if manager.is_ready
        else RunnerReadinessStatus.DEGRADED
    )
    response = RunnerReadinessResponse(
        protocol_version=RUNNER_PROTOCOL_VERSION,
        problem_revision=repository.revision,
        status=readiness_status,
    )
    if readiness_status is RunnerReadinessStatus.DEGRADED:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=response.model_dump(mode="json"),
        )
    return response


@app.post(
    RUNNER_EXECUTE_PATH,
    response_model=RunnerExecutionResponse,
)
async def execute_shellgei(
    shellgei_data: RunnerExecutionRequest,
) -> RunnerExecutionResponse:
    """登録済み問題のcommand実行をsandboxへ委譲し、文字列・画像結果を返す。

    入力は検証済みcommandとproblem ID。未登録問題は404、開始rateまたは実行枠の
    上限到達時は429を送出する。
    """
    repository = get_problem_repository()
    if shellgei_data.problem_revision != repository.revision:
        raise HTTPException(status_code=409, detail="Problem revision mismatch")
    record = repository.get(shellgei_data.problem_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Problem not found")
    if not sandbox_start_rate_limiter.try_acquire():
        raise HTTPException(status_code=429, detail="Runner is busy")

    try:
        result = await docker_client.run_with_timeout(
            shellgei_data.shellgei,
            shellgei_data.problem_id,
        )
    except SandboxBusyError as exc:
        raise HTTPException(status_code=429, detail="Runner is busy") from exc
    return RunnerExecutionResponse(
        protocol_version=RUNNER_PROTOCOL_VERSION,
        problem_revision=repository.revision,
        result=result,
    )
