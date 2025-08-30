from fastapi import FastAPI
from api import api_shellgei

app = FastAPI()

app.include_router(api_shellgei.router, prefix="/api")

@app.get("/api")
def read_root():
    return {"message": "Hello from FastAPI!"}