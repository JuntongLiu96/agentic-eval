import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session


async def _migrate_add_column(conn, table: str, column: str, col_type: str, default: str | None = None) -> None:
    """Add a column to an existing table if it doesn't exist (SQLite ALTER TABLE)."""
    result = conn.execute(text(f"PRAGMA table_info({table})"))
    columns = [row[1] for row in result.fetchall()]
    if column not in columns:
        default_clause = f" DEFAULT {default}" if default is not None else ""
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}{default_clause}"))
        logger.info(f"Migration: added column {table}.{column}")


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Migrations for columns added after initial schema
        await conn.run_sync(
            lambda sync_conn: _migrate_add_column(sync_conn, "eval_results", "turn_results", "TEXT", "NULL")
        )
