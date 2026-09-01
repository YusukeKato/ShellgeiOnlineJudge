from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from scripts.database import Base


class ExecutionLog(Base):
    """legacy互換列と最小限の構造化実行・判定fieldを保持するDB model。"""

    __tablename__ = "execution_logs"

    id = Column(Integer, primary_key=True, index=True)
    problem_id = Column(String, index=True)
    shellgei = Column(Text)
    output = Column(Text)
    judge = Column(String)
    execution_status = Column(String(32), nullable=False)
    stdout = Column(Text, nullable=False)
    stderr = Column(Text, nullable=False)
    exit_code = Column(Integer)
    timed_out = Column(Boolean, nullable=False)
    truncated = Column(Boolean, nullable=False)
    duration_ms = Column(Integer)
    verdict = Column(String(32), nullable=False)
    judge_reason = Column(String(64))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
