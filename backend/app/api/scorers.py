import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.scorer import Scorer
from app.schemas.scorer import ScorerCreate, ScorerResponse, ScorerUpdate

router = APIRouter(prefix="/api", tags=["scorers"])


@router.post("/scorers", response_model=ScorerResponse, status_code=201)
async def create_scorer(payload: ScorerCreate, db: AsyncSession = Depends(get_db)):
    scorer = Scorer(
        name=payload.name,
        description=payload.description,
        eval_prompt=payload.eval_prompt,
        pass_threshold=payload.pass_threshold,
        tags=json.dumps(payload.tags),
    )
    db.add(scorer)
    await db.commit()
    await db.refresh(scorer)
    return scorer


@router.get("/scorers", response_model=list[ScorerResponse])
async def list_scorers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Scorer).order_by(Scorer.created_at.desc()))
    return result.scalars().all()


@router.get("/scorers/{scorer_id}", response_model=ScorerResponse)
async def get_scorer(scorer_id: int, db: AsyncSession = Depends(get_db)):
    scorer = await db.get(Scorer, scorer_id)
    if not scorer:
        raise HTTPException(status_code=404, detail="Scorer not found")
    return scorer


@router.put("/scorers/{scorer_id}", response_model=ScorerResponse)
async def update_scorer(
    scorer_id: int, payload: ScorerUpdate, db: AsyncSession = Depends(get_db)
):
    scorer = await db.get(Scorer, scorer_id)
    if not scorer:
        raise HTTPException(status_code=404, detail="Scorer not found")
    if payload.name is not None:
        scorer.name = payload.name
    if payload.description is not None:
        scorer.description = payload.description
    if payload.eval_prompt is not None:
        scorer.eval_prompt = payload.eval_prompt
    if payload.pass_threshold is not None:
        scorer.pass_threshold = payload.pass_threshold
    if payload.tags is not None:
        scorer.tags = json.dumps(payload.tags)
    await db.commit()
    await db.refresh(scorer)
    return scorer


@router.delete("/scorers/{scorer_id}", status_code=204)
async def delete_scorer(scorer_id: int, db: AsyncSession = Depends(get_db)):
    scorer = await db.get(Scorer, scorer_id)
    if not scorer:
        raise HTTPException(status_code=404, detail="Scorer not found")
    await db.delete(scorer)
    await db.commit()
