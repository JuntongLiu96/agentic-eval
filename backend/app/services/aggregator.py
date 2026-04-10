import json
from typing import Any
from collections import defaultdict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.eval_result import EvalResult


def _extract_score(score_data: Any) -> float | None:
    """Extract a numeric score from various score formats."""
    if isinstance(score_data, str):
        try:
            score_data = json.loads(score_data)
        except (json.JSONDecodeError, ValueError):
            return None
    if isinstance(score_data, (int, float)):
        return float(score_data)
    if isinstance(score_data, dict):
        if "score" in score_data and isinstance(score_data["score"], (int, float)):
            return float(score_data["score"])
        if "overall_score" in score_data and isinstance(score_data["overall_score"], (int, float)):
            return float(score_data["overall_score"])
    return None


async def aggregate_run_results(run_id: int, db: AsyncSession) -> dict[str, Any]:
    """Aggregate results for a run (all rounds combined, backwards-compatible)."""
    result = await db.execute(select(EvalResult).where(EvalResult.run_id == run_id))
    results = result.scalars().all()
    if not results:
        return {"total": 0, "passed": 0, "failed": 0, "pass_rate": 0.0, "avg_duration_ms": 0}

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    avg_duration = sum(r.duration_ms for r in results) / total

    scores = []
    for r in results:
        s = _extract_score(r.score)
        if s is not None:
            scores.append(s)

    summary: dict[str, Any] = {
        "total": total, "passed": passed, "failed": total - passed,
        "pass_rate": round(passed / total * 100, 1), "avg_duration_ms": round(avg_duration),
    }
    if scores:
        summary["avg_score"] = round(sum(scores) / len(scores), 2)
        summary["min_score"] = min(scores)
        summary["max_score"] = max(scores)
    return summary


def _summarize_results(results: list[EvalResult], round_num: int) -> dict[str, Any]:
    """Build a summary dict for a set of results."""
    total = len(results)
    if total == 0:
        return {"round": round_num, "total": 0, "passed": 0, "pass_rate": 0.0}
    passed = sum(1 for r in results if r.passed)
    scores = [s for r in results if (s := _extract_score(r.score)) is not None]
    summary: dict[str, Any] = {
        "round": round_num, "total": total, "passed": passed,
        "pass_rate": round(passed / total * 100, 1),
    }
    if scores:
        summary["avg_score"] = round(sum(scores) / len(scores), 2)
        summary["min_score"] = min(scores)
        summary["max_score"] = max(scores)
    return summary


async def multi_round_summary(
    run_id: int, num_rounds: int, round_mode: str,
    pass_threshold: float, db: AsyncSession,
) -> dict[str, Any]:
    """Compute per-round summaries and cross-round averaged summary."""
    result = await db.execute(select(EvalResult).where(EvalResult.run_id == run_id))
    all_results = result.scalars().all()

    # Per-round summaries
    round_summaries = []
    for rnd in range(1, num_rounds + 1):
        round_results = [r for r in all_results if r.round_number == rnd]
        round_summaries.append(_summarize_results(round_results, rnd))

    # Cross-round averaged: for each test_case, average its scores across rounds
    tc_scores: dict[int, list[float]] = defaultdict(list)
    for r in all_results:
        s = _extract_score(r.score)
        if s is not None:
            tc_scores[r.test_case_id].append(s)

    # Compute averaged score per test case, determine pass/fail
    averaged_scores = []
    passed_count = 0
    for tc_id, scores in tc_scores.items():
        avg = sum(scores) / len(scores)
        averaged_scores.append(avg)
        if avg >= pass_threshold:
            passed_count += 1

    total_cases = len(tc_scores) if tc_scores else 0
    averaged: dict[str, Any] = {
        "round": 0, "total": total_cases, "passed": passed_count,
        "pass_rate": round(passed_count / total_cases * 100, 1) if total_cases > 0 else 0.0,
    }
    if averaged_scores:
        averaged["avg_score"] = round(sum(averaged_scores) / len(averaged_scores), 2)
        averaged["min_score"] = round(min(averaged_scores), 2)
        averaged["max_score"] = round(max(averaged_scores), 2)

    return {
        "num_rounds": num_rounds,
        "round_mode": round_mode,
        "round_summaries": round_summaries,
        "averaged": averaged,
    }
