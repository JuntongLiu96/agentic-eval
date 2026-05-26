import csv
import io
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api._helpers import db_get_or_404
from app.db.database import get_db, async_session
from app.models.adapter import Adapter
from app.models.dataset import Dataset, TestCase
from app.models.eval_result import EvalResult
from app.models.eval_run import EvalRun, RunStatus
from app.models.scorer import Scorer
from app.schemas.eval_result import EvalResultResponse
from app.schemas.eval_run import EvalRunCreate, EvalRunResponse
from app.services.aggregator import aggregate_run_results, extract_score, multi_round_summary, multi_round_per_tc_summary, per_quadrant_summary
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
    await db_get_or_404(Dataset, payload.dataset_id, db, detail="Dataset not found")
    await db_get_or_404(Scorer, payload.scorer_id, db, detail="Scorer not found")
    await db_get_or_404(Adapter, payload.adapter_id, db, detail="Adapter not found")

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


@router.post("/runs/comparison")
async def comparison_run(payload: dict, db: AsyncSession = Depends(get_db)):
    """AE-5: pair a cold-baseline run with a warm run and emit delta metrics.

    Body: ``{"baseline_run_id": int, "warm_run_id": int, "metrics": ["n_reduction", ...]?}``.

    For each test case present in both runs (round 1), compute per-metric deltas
    pulled from ``EvalResult.score`` (which carries ``agent_metadata`` for
    programmatic scorers) and a headline ``n_reduction = 1 - warm_N / baseline_N``
    where ``N`` is the trajectory-step count.
    """
    baseline = int(payload.get("baseline_run_id", 0))
    warm = int(payload.get("warm_run_id", 0))
    if baseline <= 0 or warm <= 0:
        raise HTTPException(status_code=422, detail="baseline_run_id and warm_run_id required")
    await db_get_or_404(EvalRun, baseline, db, detail="baseline run not found")
    await db_get_or_404(EvalRun, warm, db, detail="warm run not found")
    metrics: list[str] = payload.get("metrics") or ["n_reduction"]

    def _load_meta(r: EvalResult) -> dict[str, Any]:
        try:
            parsed = json.loads(r.score) if r.score else {}
        except (json.JSONDecodeError, TypeError):
            parsed = {}
        if isinstance(parsed, dict):
            md = parsed.get("agent_metadata") or parsed.get("metadata") or {}
            return md if isinstance(md, dict) else {}
        return {}

    b_rows = (await db.execute(
        select(EvalResult).where(EvalResult.run_id == baseline, EvalResult.round_number == 1)
    )).scalars().all()
    w_rows = (await db.execute(
        select(EvalResult).where(EvalResult.run_id == warm, EvalResult.round_number == 1)
    )).scalars().all()
    b_by_tc = {r.test_case_id: r for r in b_rows}
    w_by_tc = {r.test_case_id: r for r in w_rows}

    pairs = []
    for tc_id in sorted(set(b_by_tc) & set(w_by_tc)):
        b_md = _load_meta(b_by_tc[tc_id])
        w_md = _load_meta(w_by_tc[tc_id])
        deltas: dict[str, Any] = {}
        for m in metrics:
            if m == "n_reduction":
                b_n = b_md.get("trajectory_steps") or b_md.get("N")
                w_n = w_md.get("trajectory_steps") or w_md.get("N")
                if isinstance(b_n, (int, float)) and b_n > 0 and isinstance(w_n, (int, float)):
                    deltas["n_reduction"] = 1.0 - (w_n / b_n)
                else:
                    deltas["n_reduction"] = None
            else:
                bv, wv = b_md.get(m), w_md.get(m)
                if isinstance(bv, (int, float)) and isinstance(wv, (int, float)):
                    deltas[m] = wv - bv
                else:
                    deltas[m] = None
        pairs.append({
            "test_case_id": tc_id,
            "baseline_metadata": b_md,
            "warm_metadata": w_md,
            "deltas": deltas,
        })

    return {
        "baseline_run_id": baseline,
        "warm_run_id": warm,
        "metrics": metrics,
        "pairs": pairs,
    }


# IMPORTANT: /runs/compare MUST come before /runs/{run_id}
@router.get("/runs/compare")
async def compare_runs(run1: int, run2: int, db: AsyncSession = Depends(get_db)):
    summary1 = await aggregate_run_results(run1, db)
    summary2 = await aggregate_run_results(run2, db)
    # Multi-round runs have multiple rows per test_case_id. To make comparison
    # deterministic, restrict to round 1 (the first round). Callers that want a
    # multi-round aggregate should use /runs/{id}/summary instead.
    r1 = await db.execute(
        select(EvalResult)
        .where(EvalResult.run_id == run1, EvalResult.round_number == 1)
        .order_by(EvalResult.round_number)
    )
    r2 = await db.execute(
        select(EvalResult)
        .where(EvalResult.run_id == run2, EvalResult.round_number == 1)
        .order_by(EvalResult.round_number)
    )
    results1 = {r.test_case_id: r for r in r1.scalars().all()}
    results2 = {r.test_case_id: r for r in r2.scalars().all()}
    common_ids = set(results1.keys()) & set(results2.keys())

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
    return await db_get_or_404(EvalRun, run_id, db, detail="Run not found")


@router.delete("/runs/{run_id}", status_code=204)
async def delete_run(run_id: int, db: AsyncSession = Depends(get_db)):
    run = await db_get_or_404(EvalRun, run_id, db, detail="Run not found")
    await db.delete(run)
    await db.commit()


@router.post("/runs/{run_id}/start")
async def start_run(run_id: int, db: AsyncSession = Depends(get_db)):
    run = await db_get_or_404(EvalRun, run_id, db, detail="Run not found")
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
    run = await db_get_or_404(EvalRun, run_id, db, detail="Run not found")
    scorer = await db.get(Scorer, run.scorer_id)
    pass_threshold = scorer.pass_threshold if scorer and scorer.pass_threshold is not None else 60.0
    by_quadrant = await per_quadrant_summary(run_id, pass_threshold, db)
    if run.num_rounds <= 1:
        summary = await aggregate_run_results(run_id, db)
        return {"num_rounds": 1, "round_mode": run.round_mode,
                "round_summaries": [{"round": 1, **summary}],
                "averaged": {"round": 0, **summary},
                "tc_averaged": [],
                "by_quadrant": by_quadrant}
    result = await multi_round_summary(run_id, run.num_rounds, run.round_mode, pass_threshold, db)
    tc_averaged = await multi_round_per_tc_summary(run_id, run.num_rounds, pass_threshold, db)
    result["tc_averaged"] = tc_averaged
    result["by_quadrant"] = by_quadrant
    return result


@router.get("/runs/{run_id}/results", response_model=list[EvalResultResponse])
async def get_run_results(run_id: int, round: int | None = None, db: AsyncSession = Depends(get_db)):
    await db_get_or_404(EvalRun, run_id, db, detail="Run not found")
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
    await db_get_or_404(EvalRun, run_id, db, detail="Run not found")
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
