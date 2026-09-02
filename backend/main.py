import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import Response

from api import api_shellgei  # type: ignore
from scripts.database import engine
from scripts.database_migrations import migrate_database
from scripts.execution_log_repository import (
    close_execution_log_repository,
    execution_log_repo,
)
from scripts.problem_repository import load_problem_repository
from scripts.runner_client import runner_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """backendの問題data・DBを起動時に準備し、終了時にworker資源を閉じる。

    入力はFastAPI application。contextへ制御を渡す前にrepository検証やDB処理が
    失敗した場合は例外を伝播し、request受付を開始しない。
    """
    runner_client.validate_configuration()
    load_problem_repository()
    migrate_database(engine)
    execution_log_repo.prune()
    try:
        yield
    finally:
        runner_client.close()
        close_execution_log_repository()


app = FastAPI(lifespan=lifespan, redirect_slashes=False)

server_url = os.getenv("SERVER_URL", "https://shellgei-online-judge.com")
origins = [
    server_url,
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["backend", "localhost", "127.0.0.1"],
    www_redirect=False,
)


@app.middleware("http")
async def add_submission_security_headers(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    """提出APIの成功・validation・error responseへ非cache・nosniff headerを付ける。"""
    response = await call_next(request)
    if request.url.path in {"/api/shellgei", "/api/v3/submissions"}:
        for name, value in api_shellgei.SUBMISSION_RESPONSE_HEADERS.items():
            response.headers[name] = value
    return response


app.include_router(api_shellgei.router, prefix="/api")


@app.get("/api")
def read_root():
    """backend APIの到達確認用messageをdictとして返す。"""
    return {"message": "Hello from FastAPI!"}
