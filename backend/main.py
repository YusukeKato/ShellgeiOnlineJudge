import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import api_shellgei  # type: ignore
from contextlib import asynccontextmanager
from scripts.database import Base, SessionLocal, engine
from scripts.execution_log_retention import prune_execution_logs
from scripts.runner_client import runner_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    runner_client.validate_configuration()
    # テーブルが存在しない場合は作成する
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        prune_execution_logs(db)
        db.commit()
    try:
        yield
    finally:
        runner_client.close()


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
