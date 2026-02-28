from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from scripts.database import Base

class ExecutionLog(Base):
    __tablename__ = "execution_logs"

    id = Column(Integer, primary_key=True, index=True)
    problem_id = Column(String, index=True)
    shellgei = Column(Text)
    output = Column(Text)
    judge = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)