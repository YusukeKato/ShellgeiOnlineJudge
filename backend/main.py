from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import api_shellgei

app = FastAPI()

origins = [
    "http://localhost",
    "http://localhost:80",
    "http://localhost:443",
    "http://localhost:8000",
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