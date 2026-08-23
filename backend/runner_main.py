import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException

from models.model_shellgei import ShellgeiData
from scripts.admission_control import sandbox_start_rate_limiter
from scripts.container_manager import manager
from scripts.run_shellgei import SandboxBusyError, ShellgeiDockerClient
from scripts.runner_protocol import (
    RUNNER_EXECUTE_PATH,
    RUNNER_HEALTH_PATH,
    RunnerExecutionResponse,
    get_runner_shared_secret,
)


docker_client = ShellgeiDockerClient()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_runner_shared_secret()
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
    expected = f"Bearer {get_runner_shared_secret()}"
    if authorization is None or not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get(RUNNER_HEALTH_PATH)
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    RUNNER_EXECUTE_PATH,
    response_model=RunnerExecutionResponse,
    dependencies=[Depends(require_runner_authentication)],
)
async def execute_shellgei(shellgei_data: ShellgeiData) -> RunnerExecutionResponse:
    problem_path = (
        Path(__file__).resolve().parent
        / "problems"
        / "yaml_data"
        / f"{shellgei_data.problem_id}.yaml"
    )
    if not problem_path.is_file():
        raise HTTPException(status_code=404, detail="Problem not found")
    if not sandbox_start_rate_limiter.try_acquire():
        raise HTTPException(status_code=429, detail="Runner is busy")

    try:
        output, image = await docker_client.run_with_timeout(
            shellgei_data.shellgei,
            shellgei_data.problem_id,
        )
    except SandboxBusyError as exc:
        raise HTTPException(status_code=429, detail="Runner is busy") from exc
    return RunnerExecutionResponse(output=output, image=image)
