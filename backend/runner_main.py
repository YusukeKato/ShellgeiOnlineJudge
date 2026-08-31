import secrets
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException

from scripts.admission_control import sandbox_start_rate_limiter
from scripts.container_manager import manager
from scripts.problem_repository import get_problem_repository, load_problem_repository
from scripts.run_shellgei import SandboxBusyError, ShellgeiDockerClient
from scripts.runner_protocol import (
    RUNNER_EXECUTE_PATH,
    RUNNER_HEALTH_PATH,
    RUNNER_PROTOCOL_VERSION,
    RunnerExecutionRequest,
    RunnerExecutionResponse,
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


def require_runner_authentication(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """入力Authorization headerを共有secretと定数時間比較し、不一致なら401を送出する。"""
    expected = f"Bearer {get_runner_shared_secret()}"
    if authorization is None or not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get(RUNNER_HEALTH_PATH)
async def health() -> dict[str, str]:
    """runner processが応答可能であることを示す固定statusを返す。"""
    return {"status": "ok"}


@app.post(
    RUNNER_EXECUTE_PATH,
    response_model=RunnerExecutionResponse,
    dependencies=[Depends(require_runner_authentication)],
)
async def execute_shellgei(
    shellgei_data: RunnerExecutionRequest,
) -> RunnerExecutionResponse:
    """登録済み問題のcommand実行をsandboxへ委譲し、文字列・画像結果を返す。

    入力は検証済みcommandとproblem ID。未登録問題は404、開始rateまたは実行枠の
    上限到達時は429を送出する。
    """
    record = get_problem_repository().get(shellgei_data.problem_id)
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
        result=result,
    )
