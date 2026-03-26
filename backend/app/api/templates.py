from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    template = await db.get(ScorerTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="ScorerTemplate not found")
    return template
