from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


# AE-1: scorer dispatch tag. Stored as a plain string column for portability
# (SQLite enum handling is awkward; we validate at the API layer instead).
SCORER_TYPE_LLM_JUDGE = "llm_judge"
SCORER_TYPE_BOOLEAN_RUBRIC = "boolean_rubric"
SCORER_TYPE_PROGRAMMATIC = "programmatic"
SCORER_TYPE_SERIES = "series"  # AE-6
VALID_SCORER_TYPES = {
    SCORER_TYPE_LLM_JUDGE,
    SCORER_TYPE_BOOLEAN_RUBRIC,
    SCORER_TYPE_PROGRAMMATIC,
    SCORER_TYPE_SERIES,
}


class Scorer(Base):
    __tablename__ = "scorers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    # AE-1: dispatch tag — "llm_judge" (default), "boolean_rubric",
    # "programmatic" (deterministic agent_metadata rules), or "series" (AE-6,
    # cross-round assertions).
    scorer_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default=SCORER_TYPE_LLM_JUDGE
    )
    eval_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    pass_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    tags: Mapped[str] = mapped_column(Text, default="[]")  # JSON string
    # AE-1: programmatic-scorer config (rules list) and AE-6 series-scorer config
    # are JSON-serialised here. For LLM scorers this field is unused.
    config: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
