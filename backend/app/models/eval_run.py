import enum
from datetime import datetime, timezone
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base

class RunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"

class EvalRun(Base):
    __tablename__ = "eval_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    dataset_id: Mapped[int] = mapped_column(Integer, ForeignKey("datasets.id"), nullable=False)
    scorer_id: Mapped[int] = mapped_column(Integer, ForeignKey("scorers.id"), nullable=False)
    adapter_id: Mapped[int] = mapped_column(Integer, ForeignKey("adapters.id"), nullable=False)
    judge_config: Mapped[str] = mapped_column(Text, default='{"use_target_llm": true}')
    num_rounds: Mapped[int] = mapped_column(Integer, default=1)
    round_mode: Mapped[str] = mapped_column(String(10), default="agent")
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), default=RunStatus.pending)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    results: Mapped[list["EvalResult"]] = relationship(back_populates="run", cascade="all, delete-orphan")
