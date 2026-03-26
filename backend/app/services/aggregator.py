import json
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.eval_result import EvalResult

async def aggregate_run_results(run_id: int, db: AsyncSession) -> dict[str, Any]:
    result = await db.execute(select(EvalResult).where(EvalResult.run_id == run_id))
    results = result.scalars().all()
    if not results:
        return {"total": 0, "passed": 0, "failed": 0, "pass_rate": 0.0, "avg_duration_ms": 0}

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    avg_duration = sum(r.duration_ms for r in results) / total

    scores = []
    for r in results:
        score_data = json.loads(r.score) if isinstance(r.score, str) else r.score
        if isinstance(score_data, dict):
            if "score" in score_data and isinstance(score_data["score"], (int, float)):
                scores.append(score_data["score"])
            elif "overall_score" in score_data:
                scores.append(score_data["overall_score"])

    summary: dict[str, Any] = {
        "total": total, "passed": passed, "failed": total - passed,
        "pass_rate": round(passed / total * 100, 1), "avg_duration_ms": round(avg_duration),
    }
    if scores:
        summary["avg_score"] = round(sum(scores) / len(scores), 2)
        summary["min_score"] = min(scores)
        summary["max_score"] = max(scores)
    return summary
