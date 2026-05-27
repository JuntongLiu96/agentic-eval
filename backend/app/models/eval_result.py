from sqlalchemy import Boolean, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base

class EvalResult(Base):
    __tablename__ = "eval_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("eval_runs.id"), nullable=False)
    test_case_id: Mapped[int] = mapped_column(Integer, ForeignKey("test_cases.id"), nullable=False)
    # AE-13: records which scorer produced this result. Nullable for backward
    # compatibility with pre-AE-13 rows; new rows always populate it.
    scorer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("scorers.id"), nullable=True, default=None)
    round_number: Mapped[int] = mapped_column(Integer, default=1)
    agent_messages: Mapped[str] = mapped_column(Text, default="[]")
    score: Mapped[str] = mapped_column(Text, default="{}")
    judge_reasoning: Mapped[str] = mapped_column(Text, default="")
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    turn_results: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    run: Mapped["EvalRun"] = relationship(back_populates="results")
