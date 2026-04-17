"""Shared helpers for API route handlers."""

from __future__ import annotations

from typing import Type, TypeVar

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


async def db_get_or_404(
    model: Type[T],
    obj_id: int,
    db: AsyncSession,
    *,
    detail: str | None = None,
) -> T:
    """Fetch ``model`` by primary key or raise 404 with a friendly detail.

    The detail message defaults to ``f"{model.__name__} not found"`` which
    matches the ad-hoc strings used across the routers (e.g. ``"Dataset not
    found"``, ``"TestCase not found"``).  Override *detail* when the route
    uses a different label (e.g. ``"Run not found"`` for ``EvalRun``).
    """
    obj = await db.get(model, obj_id)
    if not obj:
        raise HTTPException(
            status_code=404,
            detail=detail or f"{model.__name__} not found",
        )
    return obj
