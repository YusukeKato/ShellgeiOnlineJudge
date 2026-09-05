import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse

from soj_shared.models.execution import ExecutionStatus
from soj_runner.admission_control import sandbox_start_rate_limiter
from soj_runner.container_manager import manager
from soj_shared.problem_repository import (
    get_problem_repository,
    load_problem_repository,
)
from soj_shared.request_context import bind_request_id
from soj_runner.run_shellgei import SandboxBusyError, ShellgeiDockerClient
from soj_runner.runner_http_security import RunnerRequestSecurityMiddleware
from soj_shared.runner_protocol import (
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
from soj_shared.structured_logging import (
    LogComponent,
    LogEvent,
    SAFE_EVENT_LOGGER_NAME,
    log_safe_event,
)


docker_client = ShellgeiDockerClient()
logger = logging.getLogger(SAFE_EVENT_LOGGER_NAME)


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
    with bind_request_id(shellgei_data.request_id):
        try:
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
        except HTTPException as exc:
            _log_runner_completion(shellgei_data, http_status=exc.status_code)
            raise
        except Exception:
            _log_runner_completion(shellgei_data, http_status=500)
            raise

        _log_runner_completion(
            shellgei_data,
            http_status=200,
            execution_status=result.status,
            duration_ms=result.duration_ms,
        )
        return RunnerExecutionResponse(
            protocol_version=RUNNER_PROTOCOL_VERSION,
            request_id=shellgei_data.request_id,
            problem_revision=repository.revision,
            result=result,
        )


def _log_runner_completion(
    request: RunnerExecutionRequest,
    *,
    http_status: int,
    execution_status: ExecutionStatus | None = None,
    duration_ms: int | None = None,
) -> None:
    """runner実行の安全なstatus・時間だけを、入力request IDと構造化記録する。"""
    log_safe_event(
        logger,
        LogEvent.RUNNER_EXECUTION_COMPLETED,
        LogComponent.RUNNER,
        request_id=request.request_id,
        http_status=http_status,
        execution_status=execution_status,
        duration_ms=duration_ms,
        level=logging.INFO if http_status < 500 else logging.ERROR,
    )
