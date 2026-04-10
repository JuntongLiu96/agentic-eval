import csv
import io
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.db.database import get_db, async_session
from app.models.adapter import Adapter
from app.models.dataset import Dataset, TestCase
from app.models.eval_result import EvalResult
from app.models.eval_run import EvalRun, RunStatus
from app.models.scorer import Scorer
from app.schemas.eval_result import EvalResultResponse
from app.schemas.eval_run import EvalRunCreate, EvalRunResponse
from app.services.aggregator import aggregate_run_results, multi_round_summary
from app.services.orchestrator import run_eval

router = APIRouter(prefix="/api", tags=["runs"])


@router.post("/runs", response_model=EvalRunResponse, status_code=201)
async def create_run(payload: EvalRunCreate, db: AsyncSession = Depends(get_db)):
    # Validate IDs are positive
    for field_name, field_val in [
        ("dataset_id", payload.dataset_id),
        ("scorer_id", payload.scorer_id),
        ("adapter_id", payload.adapter_id),
    ]:
        if field_val is None or field_val <= 0:
            raise HTTPException(status_code=422, detail=f"{field_name} must be a positive integer")

    # Validate referenced records exist
    if not await db.get(Dataset, payload.dataset_id):
        raise HTTPException(status_code=404, detail="Dataset not found")
    if not await db.get(Scorer, payload.scorer_id):
        raise HTTPException(status_code=404, detail="Scorer not found")
    if not await db.get(Adapter, payload.adapter_id):
        raise HTTPException(status_code=404, detail="Adapter not found")

    run = EvalRun(
        name=payload.name, dataset_id=payload.dataset_id,
        scorer_id=payload.scorer_id, adapter_id=payload.adapter_id,
        judge_config=json.dumps(payload.judge_config),
        num_rounds=payload.num_rounds,
        round_mode=payload.round_mode,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


@router.get("/runs", response_model=list[EvalRunResponse])
async def list_runs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EvalRun).order_by(EvalRun.created_at.desc()))
    return result.scalars().all()


# IMPORTANT: /runs/compare MUST come before /runs/{run_id}
@router.get("/runs/compare")
async def compare_runs(run1: int, run2: int, db: AsyncSession = Depends(get_db)):
    summary1 = await aggregate_run_results(run1, db)
    summary2 = await aggregate_run_results(run2, db)
    r1 = await db.execute(select(EvalResult).where(EvalResult.run_id == run1))
    r2 = await db.execute(select(EvalResult).where(EvalResult.run_id == run2))
    results1 = {r.test_case_id: r for r in r1.scalars().all()}
    results2 = {r.test_case_id: r for r in r2.scalars().all()}
    common_ids = set(results1.keys()) & set(results2.keys())

    def extract_score(s: Any):
        if isinstance(s, str):
            try:
                s = json.loads(s)
            except Exception:
                return None
        if isinstance(s, (int, float)):
            return s
        if isinstance(s, dict) and "score" in s:
            v = s["score"]
            return v if isinstance(v, (int, float)) else None
        return None

    comparisons = []
    for tc_id in common_ids:
        comparisons.append({
            "test_case_id": tc_id,
            "run1_passed": results1[tc_id].passed,
            "run2_passed": results2[tc_id].passed,
            "run1_score": extract_score(results1[tc_id].score),
            "run2_score": extract_score(results2[tc_id].score),
            "changed": results1[tc_id].passed != results2[tc_id].passed,
        })
    return {
        "run1": {"id": run1, "summary": summary1},
        "run2": {"id": run2, "summary": summary2},
        "comparisons": comparisons,
    }


@router.get("/runs/{run_id}", response_model=EvalRunResponse)
async def get_run(run_id: int, db: AsyncSession = Depends(get_db)):
    run = await db.get(EvalRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.delete("/runs/{run_id}", status_code=204)
async def delete_run(run_id: int, db: AsyncSession = Depends(get_db)):
    run = await db.get(EvalRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    await db.delete(run)
    await db.commit()


@router.post("/runs/{run_id}/start")
async def start_run(run_id: int, db: AsyncSession = Depends(get_db)):
    run = await db.get(EvalRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status != RunStatus.pending:
        raise HTTPException(status_code=400, detail=f"Run is {run.status}, not pending")
    events = []
    async for event in run_eval(run_id, db):
        events.append(event)
    last_event = events[-1] if events else {}
    return {"status": "completed", "events": events, "summary": last_event.get("summary", {})}


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: int):
    async def event_generator():
        async with async_session() as db:
            run = await db.get(EvalRun, run_id)
            if not run:
                yield {"event": "error", "data": json.dumps({"message": "Run not found"})}
                return
            if run.status != RunStatus.pending:
                yield {"event": "error", "data": json.dumps({"message": f"Run is {run.status}"})}
                return
            async for event in run_eval(run_id, db):
                yield {"event": event["type"], "data": json.dumps(event)}
    return EventSourceResponse(event_generator())


@router.get("/runs/{run_id}/summary")
async def get_run_summary(run_id: int, db: AsyncSession = Depends(get_db)):
    run = await db.get(EvalRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.num_rounds <= 1:
        summary = await aggregate_run_results(run_id, db)
        return {"num_rounds": 1, "round_mode": run.round_mode,
                "round_summaries": [{"round": 1, **summary}],
                "averaged": {"round": 0, **summary}}
    scorer = await db.get(Scorer, run.scorer_id)
    pass_threshold = scorer.pass_threshold if scorer and scorer.pass_threshold is not None else 60.0
    return await multi_round_summary(run_id, run.num_rounds, run.round_mode, pass_threshold, db)


@router.get("/runs/{run_id}/results", response_model=list[EvalResultResponse])
async def get_run_results(run_id: int, round: int | None = None, db: AsyncSession = Depends(get_db)):
    run = await db.get(EvalRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    query = select(EvalResult).where(EvalResult.run_id == run_id)
    if round is not None:
        query = query.where(EvalResult.round_number == round)
    result = await db.execute(query)
    results = result.scalars().all()
    # Look up test case names so the frontend can display them instead of raw DB IDs
    tc_ids = list({r.test_case_id for r in results})
    tc_map: dict[int, str] = {}
    if tc_ids:
        tc_result = await db.execute(select(TestCase).where(TestCase.id.in_(tc_ids)))
        tc_map = {tc.id: tc.name for tc in tc_result.scalars().all()}
    # Build response with test_case_name attached
    response = []
    for r in results:
        data = EvalResultResponse.model_validate(r)
        data.test_case_name = tc_map.get(r.test_case_id, "")
        response.append(data)
    return response


@router.get("/runs/{run_id}/export")
async def export_run(run_id: int, db: AsyncSession = Depends(get_db)):
    run = await db.get(EvalRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    result = await db.execute(select(EvalResult).where(EvalResult.run_id == run_id))
    results = result.scalars().all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["test_case_id", "round_number", "passed", "score", "judge_reasoning", "duration_ms"])
    for r in results:
        writer.writerow([r.test_case_id, r.round_number, r.passed, r.score, r.judge_reasoning, r.duration_ms])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=run_{run_id}_results.csv"},
    )
