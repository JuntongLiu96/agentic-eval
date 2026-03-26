from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Scorer(Base):
    __tablename__ = "scorers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Stub — will be fully implemented in a later task
