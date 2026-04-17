from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api._helpers import db_get_or_404
from app.db.database import get_db
from app.models.scorer_template import ScorerTemplate
from app.schemas.scorer_template import ScorerTemplateResponse

router = APIRouter(prefix="/api", tags=["scorer-templates"])


@router.get("/scorer-templates", response_model=list[ScorerTemplateResponse])
async def list_templates(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ScorerTemplate).order_by(ScorerTemplate.id))
    return result.scalars().all()


@router.get("/scorer-templates/{template_id}", response_model=ScorerTemplateResponse)
async def get_template(template_id: int, db: AsyncSession = Depends(get_db)):
    return await db_get_or_404(
        ScorerTemplate, template_id, db, detail="ScorerTemplate not found"
    )
