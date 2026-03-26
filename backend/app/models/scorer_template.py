from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class ScorerTemplate(Base):
    __tablename__ = "scorer_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    template_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    output_format: Mapped[str] = mapped_column(String(50), nullable=False)
    example_scorer: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string
    usage_instructions: Mapped[str] = mapped_column(Text, default="")
