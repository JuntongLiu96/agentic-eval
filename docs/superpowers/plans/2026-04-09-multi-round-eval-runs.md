# Multi-Round Eval Runs — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multi-round eval runs with two modes (agent: re-run full pipeline, scorer: re-judge same output) with averaged scores, tab-based frontend UI, CLI support, and documentation updates.

**Architecture:** Add `num_rounds` and `round_mode` columns to `EvalRun`, `round_number` to `EvalResult`. The orchestrator wraps its test-case loop in a round loop. A new aggregator function computes per-round and cross-round summaries. The frontend shows a tab bar (Summary + per-round tabs) for multi-round runs. Since no users exist, the DB is recreated from scratch (delete SQLite file).

**Tech Stack:** Python 3.12+ (FastAPI, SQLAlchemy, Typer), React 18 + TypeScript, pytest

**Important:** Before starting, delete the existing SQLite database files so `create_all` picks up new columns:
```bash
cd f:\AgenticEval\backend
del agenticeval.db 2>nul
del test.db 2>nul
```

---

### Task 1: Data Model + Schema Changes

**Files:**
- Modify: `backend/app/models/eval_run.py`
- Modify: `backend/app/models/eval_result.py`
- Modify: `backend/app/schemas/eval_run.py`
- Modify: `backend/app/schemas/eval_result.py`
- Create: `backend/app/schemas/summary.py`
- Test: `backend/tests/test_runs_api.py`

- [ ] **Step 1: Add `num_rounds` and `round_mode` to EvalRun model**

In `backend/app/models/eval_run.py`, add two columns after `judge_config` (line 20):

Find:
```python
    judge_config: Mapped[str] = mapped_column(Text, default='{"use_target_llm": true}')
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), default=RunStatus.pending)
```

Replace with:
```python
    judge_config: Mapped[str] = mapped_column(Text, default='{"use_target_llm": true}')
    num_rounds: Mapped[int] = mapped_column(Integer, default=1)
    round_mode: Mapped[str] = mapped_column(String(10), default="agent")
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), default=RunStatus.pending)
```

- [ ] **Step 2: Add `round_number` to EvalResult model**

In `backend/app/models/eval_result.py`, add after `test_case_id` (line 9):

Find:
```python
    test_case_id: Mapped[int] = mapped_column(Integer, ForeignKey("test_cases.id"), nullable=False)
    agent_messages: Mapped[str] = mapped_column(Text, default="[]")
```

Replace with:
```python
    test_case_id: Mapped[int] = mapped_column(Integer, ForeignKey("test_cases.id"), nullable=False)
    round_number: Mapped[int] = mapped_column(Integer, default=1)
    agent_messages: Mapped[str] = mapped_column(Text, default="[]")
```

- [ ] **Step 3: Add `num_rounds` and `round_mode` to EvalRunCreate schema**

In `backend/app/schemas/eval_run.py`, update `EvalRunCreate`:

Find:
```python
class EvalRunCreate(BaseModel):
    name: str = ""
    dataset_id: int
    scorer_id: int
    adapter_id: int
    judge_config: dict[str, Any] = {"use_target_llm": True}
```

Replace with:
```python
class EvalRunCreate(BaseModel):
    name: str = ""
    dataset_id: int
    scorer_id: int
    adapter_id: int
    judge_config: dict[str, Any] = {"use_target_llm": True}
    num_rounds: int = 1
    round_mode: str = "agent"
```

- [ ] **Step 4: Add `num_rounds` and `round_mode` to EvalRunResponse schema**

In `backend/app/schemas/eval_run.py`, update `EvalRunResponse`:

Find:
```python
class EvalRunResponse(BaseModel):
    id: int
    name: str
    dataset_id: int
    scorer_id: int
    adapter_id: int
    judge_config: dict[str, Any]
    status: str
```

Replace with:
```python
class EvalRunResponse(BaseModel):
    id: int
    name: str
    dataset_id: int
    scorer_id: int
    adapter_id: int
    judge_config: dict[str, Any]
    num_rounds: int
    round_mode: str
    status: str
```

- [ ] **Step 5: Add `round_number` to EvalResultResponse schema**

In `backend/app/schemas/eval_result.py`, update `EvalResultResponse`:

Find:
```python
class EvalResultResponse(BaseModel):
    id: int
    run_id: int
    test_case_id: int
    test_case_name: str = ""
```

Replace with:
```python
class EvalResultResponse(BaseModel):
    id: int
    run_id: int
    test_case_id: int
    test_case_name: str = ""
    round_number: int = 1
```

- [ ] **Step 6: Create summary schemas**

Create `backend/app/schemas/summary.py`:

```python
from typing import Any
from pydantic import BaseModel


class RoundSummary(BaseModel):
    round: int
    total: int
    passed: int
    pass_rate: float
    avg_score: float | None = None
    min_score: float | None = None
    max_score: float | None = None


class MultiRoundSummary(BaseModel):
    num_rounds: int
    round_mode: str
    round_summaries: list[RoundSummary]
    averaged: RoundSummary
```

- [ ] **Step 7: Update the runs API `create_run` to persist new fields**

In `backend/app/api/runs.py`, update the `create_run` endpoint. Find:

```python
    run = EvalRun(
        name=payload.name, dataset_id=payload.dataset_id,
        scorer_id=payload.scorer_id, adapter_id=payload.adapter_id,
        judge_config=json.dumps(payload.judge_config),
    )
```

Replace with:
```python
    run = EvalRun(
        name=payload.name, dataset_id=payload.dataset_id,
        scorer_id=payload.scorer_id, adapter_id=payload.adapter_id,
        judge_config=json.dumps(payload.judge_config),
        num_rounds=payload.num_rounds,
        round_mode=payload.round_mode,
    )
```

- [ ] **Step 8: Write tests for the new fields**

Add to the end of `backend/tests/test_runs_api.py`:

```python
@pytest.mark.asyncio
async def test_create_run_with_multi_round(client):
    """Creating a run with num_rounds and round_mode should persist them."""
    ds = await client.post("/api/datasets", json={"name": "DS"})
    scorer = await client.post("/api/scorers", json={"name": "S", "eval_prompt": "test"})
    adapter = await client.post("/api/adapters", json={
        "name": "A", "adapter_type": "http", "config": {"base_url": "http://fake:9999"},
    })
    run = await client.post("/api/runs", json={
        "dataset_id": ds.json()["id"], "scorer_id": scorer.json()["id"],
        "adapter_id": adapter.json()["id"], "num_rounds": 3, "round_mode": "scorer",
    })
    assert run.status_code == 201
    data = run.json()
    assert data["num_rounds"] == 3
    assert data["round_mode"] == "scorer"


@pytest.mark.asyncio
async def test_create_run_defaults_single_round(client):
    """Creating a run without num_rounds should default to 1 round, agent mode."""
    ds = await client.post("/api/datasets", json={"name": "DS"})
    scorer = await client.post("/api/scorers", json={"name": "S", "eval_prompt": "test"})
    adapter = await client.post("/api/adapters", json={
        "name": "A", "adapter_type": "http", "config": {"base_url": "http://fake:9999"},
    })
    run = await client.post("/api/runs", json={
        "dataset_id": ds.json()["id"], "scorer_id": scorer.json()["id"],
        "adapter_id": adapter.json()["id"],
    })
    assert run.status_code == 201
    data = run.json()
    assert data["num_rounds"] == 1
    assert data["round_mode"] == "agent"
```

- [ ] **Step 9: Delete old DB files and run tests**

Run:
```bash
cd f:\AgenticEval\backend
del agenticeval.db 2>nul
del test.db 2>nul
python -m pytest tests/test_runs_api.py -v
```

Expected: All tests PASS (including the 2 new ones).

- [ ] **Step 10: Commit**

```bash
cd f:\AgenticEval
git add backend/app/models/eval_run.py backend/app/models/eval_result.py backend/app/schemas/eval_run.py backend/app/schemas/eval_result.py backend/app/schemas/summary.py backend/app/api/runs.py backend/tests/test_runs_api.py
git commit -m "feat: add multi-round data model (num_rounds, round_mode, round_number)"
```

---

### Task 2: Multi-Round Aggregator

**Files:**
- Modify: `backend/app/services/aggregator.py`
- Create: `backend/tests/test_aggregator.py`

- [ ] **Step 1: Write failing tests for multi-round aggregation**

Create `backend/tests/test_aggregator.py`:

```python
import json
import pytest
from app.models.dataset import Dataset, TestCase
from app.models.eval_result import EvalResult
from app.models.eval_run import EvalRun
from app.models.scorer import Scorer
from app.models.adapter import Adapter
from app.services.aggregator import aggregate_run_results, multi_round_summary


@pytest.fixture
async def multi_round_run(db_session):
    """Create a run with 2 rounds, 2 test cases, results for each."""
    ds = Dataset(name="DS")
    db_session.add(ds)
    await db_session.flush()

    tc1 = TestCase(dataset_id=ds.id, name="TC1", data='{"prompt":"a"}', expected_result='{}')
    tc2 = TestCase(dataset_id=ds.id, name="TC2", data='{"prompt":"b"}', expected_result='{}')
    db_session.add_all([tc1, tc2])
    await db_session.flush()

    scorer = Scorer(name="S", eval_prompt="test", pass_threshold=60)
    adapter = Adapter(name="A", adapter_type="http", config='{"base_url":"http://fake:9999"}')
    db_session.add_all([scorer, adapter])
    await db_session.flush()

    run = EvalRun(name="multi", dataset_id=ds.id, scorer_id=scorer.id,
                  adapter_id=adapter.id, num_rounds=2, round_mode="agent")
    db_session.add(run)
    await db_session.flush()

    # Round 1: TC1=80 pass, TC2=50 fail
    db_session.add(EvalResult(run_id=run.id, test_case_id=tc1.id, round_number=1,
                              score=json.dumps(80), passed=True, duration_ms=100))
    db_session.add(EvalResult(run_id=run.id, test_case_id=tc2.id, round_number=1,
                              score=json.dumps(50), passed=False, duration_ms=200))
    # Round 2: TC1=90 pass, TC2=70 pass
    db_session.add(EvalResult(run_id=run.id, test_case_id=tc1.id, round_number=2,
                              score=json.dumps(90), passed=True, duration_ms=150))
    db_session.add(EvalResult(run_id=run.id, test_case_id=tc2.id, round_number=2,
                              score=json.dumps(70), passed=True, duration_ms=250))
    await db_session.commit()
    return run


@pytest.mark.asyncio
async def test_aggregate_still_works_single_round(db_session):
    """Existing aggregator should still work for single-round runs."""
    ds = Dataset(name="DS")
    db_session.add(ds)
    await db_session.flush()
    tc = TestCase(dataset_id=ds.id, name="TC1", data='{"prompt":"a"}', expected_result='{}')
    db_session.add(tc)
    await db_session.flush()
    scorer = Scorer(name="S", eval_prompt="test")
    adapter = Adapter(name="A", adapter_type="http", config='{"base_url":"http://fake:9999"}')
    db_session.add_all([scorer, adapter])
    await db_session.flush()
    run = EvalRun(name="single", dataset_id=ds.id, scorer_id=scorer.id, adapter_id=adapter.id)
    db_session.add(run)
    await db_session.flush()
    db_session.add(EvalResult(run_id=run.id, test_case_id=tc.id, round_number=1,
                              score=json.dumps(85), passed=True, duration_ms=100))
    await db_session.commit()

    summary = await aggregate_run_results(run.id, db_session)
    assert summary["total"] == 1
    assert summary["passed"] == 1


@pytest.mark.asyncio
async def test_multi_round_summary_per_round(multi_round_run, db_session):
    """multi_round_summary should return per-round summaries."""
    result = await multi_round_summary(multi_round_run.id, multi_round_run.num_rounds,
                                        multi_round_run.round_mode, 60.0, db_session)
    assert result["num_rounds"] == 2
    assert result["round_mode"] == "agent"
    assert len(result["round_summaries"]) == 2
    # Round 1: 1 passed out of 2
    r1 = result["round_summaries"][0]
    assert r1["round"] == 1
    assert r1["total"] == 2
    assert r1["passed"] == 1
    # Round 2: 2 passed out of 2
    r2 = result["round_summaries"][1]
    assert r2["round"] == 2
    assert r2["total"] == 2
    assert r2["passed"] == 2


@pytest.mark.asyncio
async def test_multi_round_summary_averaged(multi_round_run, db_session):
    """multi_round_summary averaged should compute cross-round averages."""
    result = await multi_round_summary(multi_round_run.id, multi_round_run.num_rounds,
                                        multi_round_run.round_mode, 60.0, db_session)
    avg = result["averaged"]
    assert avg["total"] == 2
    # TC1 avg = (80+90)/2 = 85 → pass. TC2 avg = (50+70)/2 = 60 → pass (>=60).
    assert avg["passed"] == 2
    assert avg["avg_score"] == 72.5  # (85 + 60) / 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd f:\AgenticEval\backend && python -m pytest tests/test_aggregator.py -v`

Expected: FAIL — `multi_round_summary` does not exist.

- [ ] **Step 3: Implement `multi_round_summary` in aggregator**

Replace the full content of `backend/app/services/aggregator.py` with:

```python
import json
from typing import Any
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
    from collections import defaultdict
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd f:\AgenticEval\backend && python -m pytest tests/test_aggregator.py -v`

Expected: All 3 tests PASS.

- [ ] **Step 5: Run existing aggregator-dependent tests for regressions**

Run: `cd f:\AgenticEval\backend && python -m pytest tests/test_runs_api.py -v`

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
cd f:\AgenticEval
git add backend/app/services/aggregator.py backend/tests/test_aggregator.py
git commit -m "feat: add multi-round aggregator with per-round and averaged summaries"
```

---

### Task 3: Multi-Round Orchestrator

**Files:**
- Modify: `backend/app/services/orchestrator.py`

- [ ] **Step 1: Rewrite the orchestrator to support multi-round execution**

Replace the full content of `backend/app/services/orchestrator.py` with:

```python
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, AsyncGenerator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.bridge.registry import create_adapter
from app.models.adapter import Adapter
from app.models.dataset import TestCase
from app.models.eval_result import EvalResult
from app.models.eval_run import EvalRun, RunStatus
from app.models.scorer import Scorer
from app.services.aggregator import aggregate_run_results, multi_round_summary
from app.services.judge import assemble_judge_prompt, parse_judge_response, resolve_judge_llm

logger = logging.getLogger(__name__)


async def _run_judge(
    judge_client: Any, scorer: Scorer, expected: Any,
    agent_messages: list, sub_agent_messages: list | None,
) -> dict[str, Any]:
    """Assemble judge prompt, call LLM, parse response."""
    judge_messages = assemble_judge_prompt(
        eval_prompt=scorer.eval_prompt, expected_result=expected,
        agent_messages=agent_messages,
        sub_agent_messages=sub_agent_messages or None,
    )
    judge_response = await judge_client.chat(judge_messages)
    return parse_judge_response(judge_response, scorer.pass_threshold)


def _build_all_messages(agent_result: Any) -> Any:
    """Build the stored messages object from agent result."""
    if agent_result.sub_agent_messages:
        return {"main": agent_result.messages, "sub_agents": agent_result.sub_agent_messages}
    return agent_result.messages


async def run_eval(run_id: int, db: AsyncSession) -> AsyncGenerator[dict[str, Any], None]:
    run = await db.get(EvalRun, run_id)
    if not run:
        yield {"type": "error", "message": "Run not found"}; return
    scorer = await db.get(Scorer, run.scorer_id)
    if not scorer:
        yield {"type": "error", "message": "Scorer not found"}; return
    adapter_row = await db.get(Adapter, run.adapter_id)
    if not adapter_row:
        yield {"type": "error", "message": "Adapter not found"}; return
    result = await db.execute(select(TestCase).where(TestCase.dataset_id == run.dataset_id))
    test_cases = result.scalars().all()
    if not test_cases:
        yield {"type": "error", "message": "Dataset has no test cases"}; return

    judge_config = json.loads(run.judge_config) if isinstance(run.judge_config, str) else run.judge_config
    adapter_config = json.loads(adapter_row.config) if isinstance(adapter_row.config, str) else adapter_row.config
    num_rounds = run.num_rounds
    round_mode = run.round_mode

    bridge = create_adapter(adapter_row.adapter_type)
    try:
        await bridge.connect(adapter_config)
    except Exception as e:
        run.status = RunStatus.failed; await db.commit()
        yield {"type": "error", "message": f"Failed to connect adapter: {e}"}; return

    try:
        adapter_llm = await bridge.get_judge_llm()
        judge_client = resolve_judge_llm(judge_config, adapter_llm)
    except ValueError as e:
        run.status = RunStatus.failed; await db.commit(); await bridge.disconnect()
        yield {"type": "error", "message": str(e)}; return

    run.status = RunStatus.running
    run.started_at = datetime.now(timezone.utc)
    await db.commit()
    total_cases = len(test_cases)
    logger.info(f"Run #{run_id} started: {total_cases} cases × {num_rounds} rounds ({round_mode} mode)")
    yield {"type": "run_started", "run_id": run_id, "total_cases": total_cases,
           "num_rounds": num_rounds, "round_mode": round_mode}

    if round_mode == "scorer":
        # Scorer mode: run agent once, then judge N times
        async for event in _run_scorer_mode(run, scorer, bridge, judge_client, test_cases, num_rounds, db):
            yield event
    else:
        # Agent mode: re-run agent + judge each round
        async for event in _run_agent_mode(run, scorer, bridge, judge_client, test_cases, num_rounds, db):
            yield event

    await bridge.disconnect()
    run.status = RunStatus.completed
    run.finished_at = datetime.now(timezone.utc)
    await db.commit()

    if num_rounds > 1:
        pass_threshold = scorer.pass_threshold if scorer.pass_threshold is not None else 60.0
        summary = await multi_round_summary(run_id, num_rounds, round_mode, pass_threshold, db)
    else:
        summary = await aggregate_run_results(run_id, db)
    yield {"type": "run_completed", "run_id": run_id, "summary": summary}


async def _run_agent_mode(
    run: EvalRun, scorer: Scorer, bridge: Any, judge_client: Any,
    test_cases: list, num_rounds: int, db: AsyncSession,
) -> AsyncGenerator[dict[str, Any], None]:
    """Agent mode: re-run full agent + judge pipeline each round."""
    for rnd in range(1, num_rounds + 1):
        yield {"type": "round_started", "round": rnd, "total_rounds": num_rounds}
        for i, tc in enumerate(test_cases):
            async for event in _eval_single_case(
                run, scorer, bridge, judge_client, tc, i, rnd, num_rounds,
                run_agent=True, cached_agent_result=None, db=db,
            ):
                yield event
        yield {"type": "round_completed", "round": rnd}


async def _run_scorer_mode(
    run: EvalRun, scorer: Scorer, bridge: Any, judge_client: Any,
    test_cases: list, num_rounds: int, db: AsyncSession,
) -> AsyncGenerator[dict[str, Any], None]:
    """Scorer mode: run agent once (round 0), then judge N times."""
    # Phase 1: Run agent for all test cases
    yield {"type": "round_started", "round": 0, "total_rounds": num_rounds, "phase": "agent_run"}
    cached_results: dict[int, Any] = {}
    for i, tc in enumerate(test_cases):
        test_data = json.loads(tc.data) if isinstance(tc.data, str) else tc.data
        yield {"type": "case_started", "round": 0, "case_index": i, "case_name": tc.name,
               "total_cases": len(test_cases)}
        start_time = time.monotonic()
        agent_result = await bridge.send_test(test_data)
        duration = int((time.monotonic() - start_time) * 1000)
        cached_results[tc.id] = {"result": agent_result, "duration_ms": duration}
        yield {"type": "case_completed", "round": 0, "case_index": i, "case_name": tc.name,
               "success": agent_result.success}
    yield {"type": "round_completed", "round": 0}

    # Phase 2: Judge N times
    for rnd in range(1, num_rounds + 1):
        yield {"type": "round_started", "round": rnd, "total_rounds": num_rounds}
        for i, tc in enumerate(test_cases):
            cached = cached_results.get(tc.id)
            async for event in _eval_single_case(
                run, scorer, bridge, judge_client, tc, i, rnd, num_rounds,
                run_agent=False, cached_agent_result=cached, db=db,
            ):
                yield event
        yield {"type": "round_completed", "round": rnd}


async def _eval_single_case(
    run: EvalRun, scorer: Scorer, bridge: Any, judge_client: Any,
    tc: Any, case_index: int, round_number: int, total_rounds: int,
    run_agent: bool, cached_agent_result: dict | None, db: AsyncSession,
) -> AsyncGenerator[dict[str, Any], None]:
    """Evaluate a single test case for a single round."""
    total_cases = 1  # placeholder, caller knows total
    test_data = json.loads(tc.data) if isinstance(tc.data, str) else tc.data
    expected = json.loads(tc.expected_result) if isinstance(tc.expected_result, str) else tc.expected_result

    logger.info(f"Run #{run.id} round {round_number} case {case_index + 1}: {tc.name}")
    yield {"type": "case_started", "round": round_number, "case_index": case_index,
           "case_name": tc.name, "total_cases": total_cases}

    start_time = time.monotonic()

    if run_agent:
        # Agent mode: run the agent
        agent_result = await bridge.send_test(test_data)
        agent_duration = int((time.monotonic() - start_time) * 1000)
    else:
        # Scorer mode: use cached agent result
        if cached_agent_result is None:
            eval_result = EvalResult(
                run_id=run.id, test_case_id=tc.id, round_number=round_number,
                agent_messages=json.dumps([]), score=json.dumps({}),
                judge_reasoning="No cached agent result", passed=False, duration_ms=0,
            )
            db.add(eval_result); await db.commit()
            yield {"type": "case_completed", "round": round_number, "case_name": tc.name,
                   "passed": False, "error": "No cached agent result"}
            return
        agent_result = cached_agent_result["result"]
        agent_duration = cached_agent_result["duration_ms"]

    if not agent_result.success:
        logger.warning(f"Run #{run.id} round {round_number} case {tc.name}: agent failed — {agent_result.error}")
        eval_result = EvalResult(
            run_id=run.id, test_case_id=tc.id, round_number=round_number,
            agent_messages=json.dumps(agent_result.messages), score=json.dumps({}),
            judge_reasoning=f"Agent error: {agent_result.error}", passed=False,
            duration_ms=agent_duration,
        )
        db.add(eval_result); await db.commit()
        yield {"type": "case_completed", "round": round_number, "case_name": tc.name,
               "passed": False, "error": agent_result.error}
        return

    try:
        parsed = await _run_judge(judge_client, scorer, expected,
                                   agent_result.messages, agent_result.sub_agent_messages)
        logger.info(f"Run #{run.id} round {round_number} case {tc.name}: "
                     f"score={parsed['score']}, passed={parsed['passed']}")
        all_messages = _build_all_messages(agent_result)
        total_duration = int((time.monotonic() - start_time) * 1000) if run_agent else agent_duration
        eval_result = EvalResult(
            run_id=run.id, test_case_id=tc.id, round_number=round_number,
            agent_messages=json.dumps(all_messages), score=json.dumps(parsed["score"]),
            judge_reasoning=parsed["justification"], passed=parsed["passed"],
            duration_ms=total_duration,
        )
    except Exception as e:
        logger.error(f"Run #{run.id} round {round_number} case {tc.name}: judge error — {e}")
        eval_result = EvalResult(
            run_id=run.id, test_case_id=tc.id, round_number=round_number,
            agent_messages=json.dumps(agent_result.messages), score=json.dumps({}),
            judge_reasoning=f"Judge error: {e}", passed=False,
            duration_ms=int((time.monotonic() - start_time) * 1000),
        )

    db.add(eval_result); await db.commit()
    yield {"type": "case_completed", "round": round_number, "case_index": case_index,
           "case_name": tc.name, "passed": eval_result.passed,
           "justification": eval_result.judge_reasoning}
```

- [ ] **Step 2: Run existing integration test to verify backwards compatibility**

Run: `cd f:\AgenticEval\backend && python -m pytest tests/test_runs_api.py::test_start_run_with_mock -v`

Expected: PASS — single-round runs work exactly as before.

- [ ] **Step 3: Run all backend tests**

Run: `cd f:\AgenticEval\backend && python -m pytest -v`

Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
cd f:\AgenticEval
git add backend/app/services/orchestrator.py
git commit -m "feat: multi-round orchestrator with agent and scorer modes"
```

---

### Task 4: API — Summary Endpoint + Results Round Filter + Export

**Files:**
- Modify: `backend/app/api/runs.py`

- [ ] **Step 1: Add the summary endpoint and round filter to results**

In `backend/app/api/runs.py`, add the import for the new summary types and aggregator at the top. Find:

```python
from app.services.aggregator import aggregate_run_results
```

Replace with:
```python
from app.services.aggregator import aggregate_run_results, multi_round_summary
```

Then add the summary endpoint. Find the `get_run_results` function and add this new endpoint **before** it:

```python
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
```

Next, update `get_run_results` to support `?round=N` filtering. Replace the existing function:

```python
@router.get("/runs/{run_id}/results", response_model=list[EvalResultResponse])
async def get_run_results(run_id: int, db: AsyncSession = Depends(get_db)):
    run = await db.get(EvalRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    result = await db.execute(select(EvalResult).where(EvalResult.run_id == run_id))
    results = result.scalars().all()
    # Look up test case names so the frontend can display them instead of raw DB IDs
    tc_ids = [r.test_case_id for r in results]
    tc_result = await db.execute(select(TestCase).where(TestCase.id.in_(tc_ids)))
    tc_map = {tc.id: tc.name for tc in tc_result.scalars().all()}
    # Build response with test_case_name attached
    response = []
    for r in results:
        data = EvalResultResponse.model_validate(r)
        data.test_case_name = tc_map.get(r.test_case_id, "")
        response.append(data)
    return response
```

With:

```python
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
```

Also update the export endpoint to include `round_number`. Find:

```python
    writer.writerow(["test_case_id", "passed", "score", "judge_reasoning", "duration_ms"])
    for r in results:
        writer.writerow([r.test_case_id, r.passed, r.score, r.judge_reasoning, r.duration_ms])
```

Replace with:
```python
    writer.writerow(["test_case_id", "round_number", "passed", "score", "judge_reasoning", "duration_ms"])
    for r in results:
        writer.writerow([r.test_case_id, r.round_number, r.passed, r.score, r.judge_reasoning, r.duration_ms])
```

- [ ] **Step 2: Run all tests**

Run: `cd f:\AgenticEval\backend && python -m pytest -v`

Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
cd f:\AgenticEval
git add backend/app/api/runs.py
git commit -m "feat: add /summary endpoint and ?round= filter on results"
```

---

### Task 5: Frontend — Types, API, and Multi-Round RunDetailPage

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/api/runs.ts`
- Modify: `frontend/src/pages/RunDetailPage.tsx`
- Modify: `frontend/src/pages/RunDetailPage.module.css`
- Modify: `frontend/src/pages/RunsPage.tsx`

- [ ] **Step 1: Update frontend types**

In `frontend/src/types/index.ts`, update the types:

Find:
```typescript
export interface EvalRun {
  id: number
  name: string
  dataset_id: number
  scorer_id: number
  adapter_id: number
  judge_config: Record<string, unknown>
  status: string
  started_at: string | null
  finished_at: string | null
  created_at: string
}

export interface EvalRunCreate {
  name?: string
  dataset_id: number
  scorer_id: number
  adapter_id: number
  judge_config?: Record<string, unknown>
}
```

Replace with:
```typescript
export interface EvalRun {
  id: number
  name: string
  dataset_id: number
  scorer_id: number
  adapter_id: number
  judge_config: Record<string, unknown>
  num_rounds: number
  round_mode: string
  status: string
  started_at: string | null
  finished_at: string | null
  created_at: string
}

export interface EvalRunCreate {
  name?: string
  dataset_id: number
  scorer_id: number
  adapter_id: number
  judge_config?: Record<string, unknown>
  num_rounds?: number
  round_mode?: string
}
```

Find:
```typescript
export interface EvalResult {
  id: number
  run_id: number
  test_case_id: number
  test_case_name: string
  agent_messages: Record<string, unknown>[] | { main: Record<string, unknown>[]; sub_agents: Record<string, unknown>[] }
  score: Record<string, unknown>
  judge_reasoning: string
  passed: boolean
  duration_ms: number
}
```

Replace with:
```typescript
export interface EvalResult {
  id: number
  run_id: number
  test_case_id: number
  test_case_name: string
  round_number: number
  agent_messages: Record<string, unknown>[] | { main: Record<string, unknown>[]; sub_agents: Record<string, unknown>[] }
  score: Record<string, unknown>
  judge_reasoning: string
  passed: boolean
  duration_ms: number
}
```

Add new types at the end of the file, before the closing:

```typescript
// --- Multi-Round Summary ---
export interface RoundSummary {
  round: number
  total: number
  passed: number
  pass_rate: number
  avg_score?: number
  min_score?: number
  max_score?: number
}

export interface MultiRoundSummary {
  num_rounds: number
  round_mode: string
  round_summaries: RoundSummary[]
  averaged: RoundSummary
}
```

- [ ] **Step 2: Update frontend API**

In `frontend/src/api/runs.ts`, update to add summary endpoint and round filter:

Find:
```typescript
import { apiGet, apiPost, apiDelete, apiDownloadUrl } from './client'
import type { EvalRun, EvalRunCreate, EvalResult, RunComparison } from '../types'
```

Replace with:
```typescript
import { apiGet, apiPost, apiDelete, apiDownloadUrl } from './client'
import type { EvalRun, EvalRunCreate, EvalResult, RunComparison, MultiRoundSummary } from '../types'
```

Find:
```typescript
export const getRunResults = (id: number) => apiGet<EvalResult[]>(`/runs/${id}/results`)
```

Replace with:
```typescript
export const getRunResults = (id: number, round?: number) =>
  apiGet<EvalResult[]>(`/runs/${id}/results`, round !== undefined ? { round: String(round) } : undefined)
export const getRunSummary = (id: number) => apiGet<MultiRoundSummary>(`/runs/${id}/summary`)
```

Add new SSE event listeners. Find:
```typescript
  source.addEventListener('case_completed', (e) => onEvent(JSON.parse((e as MessageEvent).data)))
  source.addEventListener('run_completed', (e) => { onEvent(JSON.parse((e as MessageEvent).data)); source.close(); onDone() })
```

Replace with:
```typescript
  source.addEventListener('round_started', (e) => onEvent(JSON.parse((e as MessageEvent).data)))
  source.addEventListener('case_completed', (e) => onEvent(JSON.parse((e as MessageEvent).data)))
  source.addEventListener('round_completed', (e) => onEvent(JSON.parse((e as MessageEvent).data)))
  source.addEventListener('run_completed', (e) => { onEvent(JSON.parse((e as MessageEvent).data)); source.close(); onDone() })
```

- [ ] **Step 3: Update RunsPage create form with num_rounds and round_mode**

In `frontend/src/pages/RunsPage.tsx`, update the form state initial value:

Find:
```typescript
  const [form, setForm] = useState<EvalRunCreate>({
    name: '', dataset_id: 0, scorer_id: 0, adapter_id: 0,
  })
```

Replace with:
```typescript
  const [form, setForm] = useState<EvalRunCreate>({
    name: '', dataset_id: 0, scorer_id: 0, adapter_id: 0, num_rounds: 1, round_mode: 'agent',
  })
```

In the form JSX, add inputs after the adapter selector and before the Create button. Find:

```tsx
          <button type="submit" className={styles.btn} disabled={createMut.isPending || form.dataset_id === 0 || form.scorer_id === 0 || form.adapter_id === 0}>Create Run</button>
```

Replace with:
```tsx
          <input type="number" min={1} max={20} placeholder="Rounds" value={form.num_rounds ?? 1}
            onChange={e => setForm({ ...form, num_rounds: Number(e.target.value) })}
            style={{ width: 70 }} title="Number of rounds" />
          {(form.num_rounds ?? 1) > 1 && (
            <select value={form.round_mode ?? 'agent'} onChange={e => setForm({ ...form, round_mode: e.target.value })}>
              <option value="agent">Agent (re-run full pipeline)</option>
              <option value="scorer">Scorer (re-judge only)</option>
            </select>
          )}
          <button type="submit" className={styles.btn} disabled={createMut.isPending || form.dataset_id === 0 || form.scorer_id === 0 || form.adapter_id === 0}>Create Run</button>
```

- [ ] **Step 4: Rewrite RunDetailPage for multi-round support**

Replace the full content of `frontend/src/pages/RunDetailPage.tsx` with the multi-round version. This is a significant rewrite — the key changes are: tab bar for multi-round runs, per-round data fetching, summary view, and round-aware progress display.

Replace the entire file `frontend/src/pages/RunDetailPage.tsx` with:

```tsx
import React, { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getRun, getRunResults, getRunSummary, startRun, streamRun, exportRunUrl } from '../api/runs'
import { listTestCases, listDatasets } from '../api/datasets'
import { listScorers } from '../api/scorers'
import { listAdapters } from '../api/adapters'
import StatusBadge from '../components/StatusBadge'
import PassFailIcon from '../components/PassFailIcon'
import type { EvalResult } from '../types'
import styles from './RunDetailPage.module.css'

function formatScore(score: any): string {
  if (typeof score === 'number') return String(score)
  const val = score?.score
  if (typeof val === 'number') return String(val)
  return '—'
}

export default function RunDetailPage() {
  const { id } = useParams<{ id: string }>()
  const runId = Number(id)
  const queryClient = useQueryClient()

  const { data: run, refetch: refetchRun } = useQuery({
    queryKey: ['run', runId],
    queryFn: () => getRun(runId),
    refetchInterval: (query) => query.state.data?.status === 'running' ? 5000 : false,
  })

  const isMultiRound = (run?.num_rounds ?? 1) > 1
  const [activeTab, setActiveTab] = useState<'summary' | number>('summary')

  // For single-round: fetch all results. For multi-round: fetch by round or all.
  const roundToFetch = isMultiRound && typeof activeTab === 'number' ? activeTab : undefined
  const { data: results } = useQuery({
    queryKey: ['results', runId, roundToFetch ?? 'all'],
    queryFn: () => getRunResults(runId, roundToFetch),
    enabled: run?.status === 'completed' || run?.status === 'failed' || run?.status === 'running',
    refetchInterval: () => run?.status === 'running' ? 5000 : false,
  })

  const { data: summary } = useQuery({
    queryKey: ['summary', runId],
    queryFn: () => getRunSummary(runId),
    enabled: isMultiRound && (run?.status === 'completed' || run?.status === 'failed'),
  })

  const { data: testCases } = useQuery({
    queryKey: ['testCases', run?.dataset_id],
    queryFn: () => listTestCases(run!.dataset_id),
    enabled: !!run?.dataset_id,
  })
  const { data: datasets } = useQuery({ queryKey: ['datasets'], queryFn: listDatasets })
  const { data: scorers } = useQuery({ queryKey: ['scorers'], queryFn: listScorers })
  const { data: adapters } = useQuery({ queryKey: ['adapters'], queryFn: listAdapters })

  const datasetName = datasets?.find(d => d.id === run?.dataset_id)?.name
  const scorerName = scorers?.find(s => s.id === run?.scorer_id)?.name
  const adapterName = adapters?.find(a => a.id === run?.adapter_id)?.name

  const [isRunning, setIsRunning] = useState(false)
  const [progress, setProgress] = useState<string[]>([])
  const [expandedRow, setExpandedRow] = useState<number | null>(null)

  async function handleStart() {
    setIsRunning(true)
    setProgress([])
    try {
      let receivedEvents = false
      const cleanup = streamRun(
        runId,
        (event) => {
          receivedEvents = true
          const type = (event as any).type
          const round = (event as any).round
          if (type === 'round_started' && round > 0) {
            setProgress(prev => [...prev, `--- Round ${round}/${(event as any).total_rounds} ---`])
          } else if (type === 'case_completed' && round > 0) {
            const name = (event as any).case_name || ''
            const passed = (event as any).passed ? '✓' : '✗'
            setProgress(prev => [...prev, `R${round} ${name}: ${passed}`])
          }
        },
        () => {
          setIsRunning(false)
          refetchRun()
          queryClient.invalidateQueries({ queryKey: ['results', runId] })
          queryClient.invalidateQueries({ queryKey: ['summary', runId] })
        },
      )
      setTimeout(async () => {
        if (!receivedEvents) {
          cleanup()
          try { await startRun(runId) } catch { /* run may already be started */ }
          setIsRunning(false)
          refetchRun()
          queryClient.invalidateQueries({ queryKey: ['results', runId] })
          queryClient.invalidateQueries({ queryKey: ['summary', runId] })
        }
      }, 5000)
    } catch {
      try { await startRun(runId) } catch { /* ignore */ }
      setIsRunning(false)
      refetchRun()
      queryClient.invalidateQueries({ queryKey: ['results', runId] })
      queryClient.invalidateQueries({ queryKey: ['summary', runId] })
    }
  }

  const displayResults = results ?? []
  const passedCount = displayResults.filter(r => r.passed).length
  const totalCount = displayResults.length

  return (
    <div>
      <Link to="/" className={styles.backLink}>← Back to Runs</Link>
      <div className={styles.header}>
        <h1>Run #{runId}: {run?.name || '(unnamed)'}</h1>
        <StatusBadge status={run?.status || 'pending'} />
      </div>

      <div className={styles.meta}>
        <span>Dataset: {datasetName ?? run?.dataset_id}</span>
        <span>Scorer: {scorerName ?? run?.scorer_id}</span>
        <span>Adapter: {adapterName ?? run?.adapter_id}</span>
        {isMultiRound && <span>Rounds: {run?.num_rounds} ({run?.round_mode} mode)</span>}
        {run?.started_at && <span>Started: {run.started_at}</span>}
        {run?.finished_at && <span>Finished: {run.finished_at}</span>}
      </div>

      {run?.status === 'pending' && (
        <button className={styles.startBtn} onClick={handleStart} disabled={isRunning}>
          {isRunning ? 'Running...' : `Start Run${isMultiRound ? ` (${run.num_rounds} rounds)` : ''}`}
        </button>
      )}

      {run?.status === 'running' && (
        <div className={styles.progressInfo}>
          {results ? results.length : 0}/{testCases ? testCases.length * (run?.num_rounds ?? 1) : '?'} results completed
        </div>
      )}

      {isRunning && progress.length > 0 && (
        <div className={styles.progressLog}>
          <h3>Progress</h3>
          {progress.map((p, i) => <div key={i} className={styles.logLine}>{p}</div>)}
        </div>
      )}

      {/* Tab bar for multi-round runs */}
      {isMultiRound && (run?.status === 'completed' || run?.status === 'failed') && (
        <div className={styles.tabBar}>
          <button
            className={`${styles.tab} ${activeTab === 'summary' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('summary')}
          >Summary</button>
          {Array.from({ length: run?.num_rounds ?? 1 }, (_, i) => i + 1).map(rnd => (
            <button
              key={rnd}
              className={`${styles.tab} ${activeTab === rnd ? styles.tabActive : ''}`}
              onClick={() => setActiveTab(rnd)}
            >Round {rnd}</button>
          ))}
        </div>
      )}

      {/* Summary tab for multi-round */}
      {isMultiRound && activeTab === 'summary' && summary && (
        <div className={styles.summaryCards}>
          <div className={styles.summaryCard}>
            <h3>Averaged</h3>
            <div>{summary.averaged.passed}/{summary.averaged.total} passed ({summary.averaged.pass_rate}%)</div>
            {summary.averaged.avg_score !== undefined && <div>Avg score: {summary.averaged.avg_score}</div>}
          </div>
          {summary.round_summaries.map(rs => (
            <div key={rs.round} className={styles.summaryCard}>
              <h3>Round {rs.round}</h3>
              <div>{rs.passed}/{rs.total} passed ({rs.pass_rate}%)</div>
              {rs.avg_score !== undefined && <div>Avg: {rs.avg_score}</div>}
            </div>
          ))}
        </div>
      )}

      {/* Results table */}
      {displayResults.length > 0 && (
        <>
          <div className={styles.summary}>
            <h2>
              {isMultiRound && typeof activeTab === 'number'
                ? `Round ${activeTab}: ${passedCount}/${totalCount} passed`
                : `Results: ${passedCount}/${totalCount} passed`}
              {' '}({totalCount > 0 ? ((passedCount / totalCount) * 100).toFixed(1) : 0}%)
            </h2>
            <a href={exportRunUrl(runId)} download className={styles.exportBtn}>Export CSV</a>
          </div>

          <ResultsTable
            results={displayResults}
            expandedRow={expandedRow}
            onToggleRow={(id) => setExpandedRow(expandedRow === id ? null : id)}
            showRoundColumn={isMultiRound && activeTab === 'summary'}
          />
        </>
      )}
    </div>
  )
}

function ResultsTable({ results, expandedRow, onToggleRow, showRoundColumn }: {
  results: EvalResult[]
  expandedRow: number | null
  onToggleRow: (id: number) => void
  showRoundColumn: boolean
}) {
  const colSpan = showRoundColumn ? 6 : 5
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th className={styles.colTc}>TC</th>
            {showRoundColumn && <th style={{ width: 60 }}>Round</th>}
            <th className={styles.colPass}>Pass</th>
            <th className={styles.colScore}>Score</th>
            <th className={styles.colDur}>Time</th>
            <th className={styles.colReason}>Justification</th>
          </tr>
        </thead>
        <tbody>
          {results.map(r => (
            <React.Fragment key={r.id}>
              <tr className={styles.resultRow} onClick={() => onToggleRow(r.id)}>
                <td>{r.test_case_name || r.test_case_id}</td>
                {showRoundColumn && <td>{r.round_number}</td>}
                <td><PassFailIcon passed={r.passed} /></td>
                <td>{formatScore(r.score)}</td>
                <td>{(r.duration_ms / 1000).toFixed(1)}s</td>
                <td className={styles.reasoning}>{r.judge_reasoning}</td>
              </tr>
              {expandedRow === r.id && (
                <tr className={styles.expandedRow}>
                  <td colSpan={colSpan}>
                    <div className={styles.detail}>
                      <h4>Justification</h4>
                      <p>{r.judge_reasoning}</p>
                      <h4>Score</h4>
                      <pre>{JSON.stringify(r.score, null, 2)}</pre>
                      {Array.isArray(r.agent_messages) ? (
                        <>
                          <h4>Agent Messages ({r.agent_messages.length})</h4>
                          <pre>{JSON.stringify(r.agent_messages, null, 2)}</pre>
                        </>
                      ) : (
                        <>
                          <h4>Main Agent Messages ({(r.agent_messages as any)?.main?.length ?? 0})</h4>
                          <pre>{JSON.stringify((r.agent_messages as any)?.main, null, 2)}</pre>
                          {(r.agent_messages as any)?.sub_agents?.length > 0 && (
                            <>
                              <h4>Sub-Agent Messages ({(r.agent_messages as any).sub_agents.length})</h4>
                              <pre>{JSON.stringify((r.agent_messages as any).sub_agents, null, 2)}</pre>
                            </>
                          )}
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              )}
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  )
}
```

- [ ] **Step 5: Add tab bar and summary card CSS**

Add to the end of `frontend/src/pages/RunDetailPage.module.css`:

```css
.tabBar { display: flex; gap: 0; margin: 1rem 0 0.5rem; border-bottom: 2px solid #334155; }
.tab { background: transparent; color: #94a3b8; border: none; padding: 0.5rem 1rem; cursor: pointer; font-size: 0.85rem; border-bottom: 2px solid transparent; margin-bottom: -2px; }
.tab:hover { color: #e2e8f0; }
.tabActive { color: #818cf8; border-bottom-color: #818cf8; }
.summaryCards { display: flex; gap: 1rem; margin: 1rem 0; flex-wrap: wrap; }
.summaryCard { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 0.75rem 1rem; min-width: 140px; }
.summaryCard h3 { margin: 0 0 0.3rem; color: #e2e8f0; font-size: 0.85rem; }
.summaryCard div { color: #94a3b8; font-size: 0.8rem; }
```

- [ ] **Step 6: Verify frontend compiles**

Run: `cd f:\AgenticEval\frontend && npx tsc --noEmit`

Expected: No errors.

- [ ] **Step 7: Commit**

```bash
cd f:\AgenticEval
git add frontend/src/types/index.ts frontend/src/api/runs.ts frontend/src/pages/RunDetailPage.tsx frontend/src/pages/RunDetailPage.module.css frontend/src/pages/RunsPage.tsx
git commit -m "feat: multi-round frontend with tab bar, summary view, and round selector"
```

---

### Task 6: CLI Updates

**Files:**
- Modify: `backend/cli/runs.py`
- Modify: `backend/cli/main.py`

- [ ] **Step 1: Update `runs create` with `--num-rounds` and `--round-mode`**

In `backend/cli/runs.py`, update the `create_run` command:

Find:
```python
@runs_app.command("create")
def create_run(
    dataset: int = typer.Option(..., "--dataset", "-d", help="Dataset ID"),
    scorer: int = typer.Option(..., "--scorer", "-s", help="Scorer ID"),
    adapter: int = typer.Option(..., "--adapter", "-a", help="Adapter ID"),
    name: str = typer.Option("", "--name", "-n", help="Optional run name"),
    judge_config_json: str = typer.Option("{}", "--judge-config",
                                          help="Judge config as JSON string"),
):
    """Create a new eval run (does not start it)."""
    judge_config = parse_json_arg(judge_config_json, "--judge-config")
    payload = {"dataset_id": dataset, "scorer_id": scorer, "adapter_id": adapter,
               "name": name, "judge_config": judge_config}
    r = _client().post("/api/runs", json=payload)
    console.print(f"[green]Created run #{r['id']}: {r.get('name', '')} (status: {r.get('status', 'pending')})[/green]")
```

Replace with:
```python
@runs_app.command("create")
def create_run(
    dataset: int = typer.Option(..., "--dataset", "-d", help="Dataset ID"),
    scorer: int = typer.Option(..., "--scorer", "-s", help="Scorer ID"),
    adapter: int = typer.Option(..., "--adapter", "-a", help="Adapter ID"),
    name: str = typer.Option("", "--name", "-n", help="Optional run name"),
    judge_config_json: str = typer.Option("{}", "--judge-config",
                                          help="Judge config as JSON string"),
    num_rounds: int = typer.Option(1, "--num-rounds", "-r", help="Number of rounds (default: 1)"),
    round_mode: str = typer.Option("agent", "--round-mode", help="Round mode: agent or scorer"),
):
    """Create a new eval run (does not start it)."""
    judge_config = parse_json_arg(judge_config_json, "--judge-config")
    payload = {"dataset_id": dataset, "scorer_id": scorer, "adapter_id": adapter,
               "name": name, "judge_config": judge_config,
               "num_rounds": num_rounds, "round_mode": round_mode}
    r = _client().post("/api/runs", json=payload)
    rounds_info = f", {r.get('num_rounds', 1)} rounds ({r.get('round_mode', 'agent')})" if r.get('num_rounds', 1) > 1 else ""
    console.print(f"[green]Created run #{r['id']}: {r.get('name', '')} (status: {r.get('status', 'pending')}{rounds_info})[/green]")
```

- [ ] **Step 2: Update `runs results` with `--round` filter**

Find:
```python
@runs_app.command("results")
def show_results(run_id: int = typer.Argument(..., help="Run ID")):
    """Show detailed results for a run."""
    data = _client().get(f"/api/runs/{run_id}/results")
```

Replace with:
```python
@runs_app.command("results")
def show_results(
    run_id: int = typer.Argument(..., help="Run ID"),
    round_num: int = typer.Option(None, "--round", "-R", help="Filter by round number"),
):
    """Show detailed results for a run."""
    params = {}
    if round_num is not None:
        params["round"] = round_num
    data = _client().get(f"/api/runs/{run_id}/results", params=params)
```

- [ ] **Step 3: Update top-level `run` shortcut with `--num-rounds`**

In `backend/cli/main.py`, update the `run_eval` command:

Find:
```python
@app.command("run")
def run_eval(
    dataset: int = typer.Option(..., "--dataset", "-d", help="Dataset ID"),
    scorer: int = typer.Option(..., "--scorer", "-s", help="Scorer ID"),
    adapter: int = typer.Option(..., "--adapter", "-a", help="Adapter ID"),
    name: str = typer.Option("", "--name", "-n", help="Optional run name"),
    judge_config_json: str = typer.Option("{}", "--judge-config",
                                          help="Judge config as JSON string"),
):
    """Create and immediately start an eval run (shortcut)."""
    client = ApiClient(base_url=state["base_url"])
    judge_config = parse_json_arg(judge_config_json, "--judge-config")
    payload = {"dataset_id": dataset, "scorer_id": scorer, "adapter_id": adapter,
               "name": name, "judge_config": judge_config}
```

Replace with:
```python
@app.command("run")
def run_eval(
    dataset: int = typer.Option(..., "--dataset", "-d", help="Dataset ID"),
    scorer: int = typer.Option(..., "--scorer", "-s", help="Scorer ID"),
    adapter: int = typer.Option(..., "--adapter", "-a", help="Adapter ID"),
    name: str = typer.Option("", "--name", "-n", help="Optional run name"),
    judge_config_json: str = typer.Option("{}", "--judge-config",
                                          help="Judge config as JSON string"),
    num_rounds: int = typer.Option(1, "--num-rounds", "-r", help="Number of rounds (default: 1)"),
    round_mode: str = typer.Option("agent", "--round-mode", help="Round mode: agent or scorer"),
):
    """Create and immediately start an eval run (shortcut)."""
    client = ApiClient(base_url=state["base_url"])
    judge_config = parse_json_arg(judge_config_json, "--judge-config")
    payload = {"dataset_id": dataset, "scorer_id": scorer, "adapter_id": adapter,
               "name": name, "judge_config": judge_config,
               "num_rounds": num_rounds, "round_mode": round_mode}
```

- [ ] **Step 4: Run CLI tests**

Run: `cd f:\AgenticEval\backend && python -m pytest tests/test_cli_runs.py -v`

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
cd f:\AgenticEval
git add backend/cli/runs.py backend/cli/main.py
git commit -m "feat: CLI multi-round support (--num-rounds, --round-mode, --round)"
```

---

### Task 7: Documentation Updates (README, Skill, API Reference)

**Files:**
- Modify: `README.md`
- Modify: `skill/SKILL.md`
- Modify: `skill/references/api-reference.md`

- [ ] **Step 1: Update README — Running Evaluations section**

In `README.md`, find the "Running Evaluations" section CLI examples:

Find:
```bash
# One-shot: create and immediately run
agenticeval run --dataset 1 --scorer 1 --adapter 1 --name "my-eval"

# Or step by step
agenticeval runs create --dataset 1 --scorer 1 --adapter 1 --name "my-eval"
agenticeval runs start 1
```

Replace with:
```bash
# One-shot: create and immediately run
agenticeval run --dataset 1 --scorer 1 --adapter 1 --name "my-eval"

# Multi-round: test agent consistency (re-run agent + judge 3 times)
agenticeval run --dataset 1 --scorer 1 --adapter 1 --name "consistency-test" --num-rounds 3

# Multi-round scorer mode: test judge consistency (run agent once, re-judge 3 times)
agenticeval run --dataset 1 --scorer 1 --adapter 1 --name "judge-test" --num-rounds 3 --round-mode scorer

# Or step by step
agenticeval runs create --dataset 1 --scorer 1 --adapter 1 --name "my-eval"
agenticeval runs start 1
```

- [ ] **Step 2: Update Skill SKILL.md — Phase 2 section**

In `skill/SKILL.md`, find the run creation section in Phase 2:

Find:
```bash
# One-step create + start (recommended)
agenticeval run --dataset {dataset_id} --scorer {scorer_id} --adapter {adapter_id} --name "run-v1"

# Alternative: separate create + start
agenticeval runs create --dataset {dataset_id} --scorer {scorer_id} --adapter {adapter_id} --name "run-v1"
agenticeval runs start {run_id}
```

Replace with:
```bash
# One-step create + start (recommended)
agenticeval run --dataset {dataset_id} --scorer {scorer_id} --adapter {adapter_id} --name "run-v1"

# Multi-round: test agent consistency across multiple runs
agenticeval run --dataset {dataset_id} --scorer {scorer_id} --adapter {adapter_id} --name "consistency-v1" --num-rounds 3

# Multi-round scorer mode: test judge/scorer consistency (run agent once, re-judge N times)
agenticeval run --dataset {dataset_id} --scorer {scorer_id} --adapter {adapter_id} --name "scorer-test" --num-rounds 3 --round-mode scorer

# Alternative: separate create + start
agenticeval runs create --dataset {dataset_id} --scorer {scorer_id} --adapter {adapter_id} --name "run-v1"
agenticeval runs start {run_id}
```

- [ ] **Step 3: Update API reference**

In `skill/references/api-reference.md`, update the Runs section:

Find:
```markdown
| `POST` | `/api/runs` | `{dataset_id, scorer_id, adapter_id, name?}` | `{id, name, status: "pending"}` |
```

Replace with:
```markdown
| `POST` | `/api/runs` | `{dataset_id, scorer_id, adapter_id, name?, num_rounds?, round_mode?}` | `{id, name, status: "pending", num_rounds, round_mode}` |
```

Find:
```markdown
| `GET` | `/api/runs/{id}/results` | — | `[{testcase_id, score, passed, judge_reasoning, duration_seconds}]` |
```

Replace with:
```markdown
| `GET` | `/api/runs/{id}/results` | `?round=N` (optional) | `[{testcase_id, round_number, score, passed, judge_reasoning, duration_seconds}]` |
| `GET` | `/api/runs/{id}/summary` | — | `{num_rounds, round_mode, round_summaries: [...], averaged: {...}}` |
```

- [ ] **Step 4: Commit**

```bash
cd f:\AgenticEval
git add README.md skill/SKILL.md skill/references/api-reference.md
git commit -m "docs: update README, skill, and API reference for multi-round eval runs"
```

---

### Task 8: Full Regression Test

**Files:** None (verification only)

- [ ] **Step 1: Run all backend tests**

Run: `cd f:\AgenticEval\backend && python -m pytest -v`

Expected: All tests PASS.

- [ ] **Step 2: Run frontend type check**

Run: `cd f:\AgenticEval\frontend && npx tsc --noEmit`

Expected: No errors.

- [ ] **Step 3: Commit if any fixes needed**

If any test failures were found and fixed, commit those fixes.
