from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from soj_backend.database import Base


class ExecutionLog(Base):
    """legacy互換列と最小限の構造化実行・判定fieldを保持するDB model。"""

    __tablename__ = "execution_logs"

    # legacy列のNULL許容と既存のSQL型・indexを、typed mappingでも維持する。
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    problem_id: Mapped[str | None] = mapped_column(String, index=True)
    shellgei: Mapped[str | None] = mapped_column(Text)
    output: Mapped[str | None] = mapped_column(Text)
    judge: Mapped[str | None] = mapped_column(String)
    execution_status: Mapped[str] = mapped_column(String(32), nullable=False)
    stdout: Mapped[str] = mapped_column(Text, nullable=False)
    stderr: Mapped[str] = mapped_column(Text, nullable=False)
    exit_code: Mapped[int | None] = mapped_column(Integer)
    timed_out: Mapped[bool] = mapped_column(Boolean, nullable=False)
    truncated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    verdict: Mapped[str] = mapped_column(String(32), nullable=False)
    judge_reason: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
