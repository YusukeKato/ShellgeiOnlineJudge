import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from api import api_shellgei  # type: ignore
from contextlib import asynccontextmanager
from scripts.database import Base, SessionLocal, engine
from scripts.execution_log_retention import prune_execution_logs
from scripts.execution_log_persistence import close_execution_log_persistence
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
    # テーブルが存在しない場合は作成する
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        prune_execution_logs(db)
        db.commit()
    try:
        yield
    finally:
        runner_client.close()
        close_execution_log_persistence()


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

app.include_router(api_shellgei.router, prefix="/api")


@app.get("/api")
def read_root():
    """backend APIの到達確認用messageをdictとして返す。"""
    return {"message": "Hello from FastAPI!"}
