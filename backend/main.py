from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import api_shellgei  # type: ignore
from contextlib import asynccontextmanager
from scripts.container_manager import manager
from scripts.database import engine, Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    # テーブルが存在しない場合は作成する
    Base.metadata.create_all(bind=engine)
    # アプリ起動時にプールを作る
    manager.initialize_pool()
    yield


app = FastAPI(lifespan=lifespan)

# server_url = "http://localhost"
server_url = "https://shellgei-online-judge.com"
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
