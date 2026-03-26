from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class ScorerTemplate(Base):
    __tablename__ = "scorer_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Stub — will be fully implemented in a later task
