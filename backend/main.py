import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import api_shellgei  # type: ignore
from contextlib import asynccontextmanager
from scripts.container_manager import manager
from scripts.database import Base, SessionLocal, engine
from scripts.execution_log_retention import prune_execution_logs


@asynccontextmanager
async def lifespan(app: FastAPI):
    # テーブルが存在しない場合は作成する
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        prune_execution_logs(db)
        db.commit()
    # アプリ起動時にプールを作る
    manager.initialize_pool()
    try:
        yield
    finally:
        manager.shutdown_pool()
        api_shellgei.docker_client.close()


app = FastAPI(lifespan=lifespan)

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

app.include_router(api_shellgei.router, prefix="/api")


@app.get("/api")
def read_root():
    return {"message": "Hello from FastAPI!"}
