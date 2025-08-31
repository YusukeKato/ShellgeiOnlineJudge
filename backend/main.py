from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import api_shellgei

app = FastAPI()

server_url = "http://localhost"
# server_url = "https://shellgei-online-judge.com"
origins = [
    f"{server_url}",
    f"{server_url}:80",
    f"{server_url}:443",
    f"{server_url}:8000",
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