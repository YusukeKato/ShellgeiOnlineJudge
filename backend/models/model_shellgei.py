from pydantic import BaseModel

class ShellgeiData(BaseModel):
    shellgei: str
    problem_id: str

class ShellgeiResultResponse(BaseModel):
    output: str
    image: str
    judge: str