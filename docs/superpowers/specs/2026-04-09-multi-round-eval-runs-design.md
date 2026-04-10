# Multi-Round Eval Runs

**Date:** 2026-04-09
**Status:** Draft

## Problem

Currently, each eval run executes every test case exactly once. This makes it impossible to measure:
- **Agent consistency** — does the agent produce similar quality outputs across multiple runs of the same input?
- **Scorer/judge consistency** — does the judge LLM assign consistent scores to the same agent output?

## Solution

Add multi-round support to eval runs. Users configure how many rounds to run and which mode:

- **Agent mode** (`round_mode="agent"`) — re-run the full agent + judge pipeline each round. Tests agent consistency/robustness.
- **Scorer mode** (`round_mode="scorer"`) — run the agent once, then re-judge the same output N times. Tests scorer/judge consistency.

The final score for each test case is the average across all successful rounds. A test case that fails in one round is excluded from that round's contribution to the average.

## Data Model Changes

### EvalRun — Add two fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `num_rounds` | `Integer` | `1` | Number of rounds to execute |
| `round_mode` | `String(10)` | `"agent"` | `"agent"` (re-run full pipeline) or `"scorer"` (run agent once, re-judge N times) |

### EvalResult — Add one field

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `round_number` | `Integer` | `1` | Which round this result belongs to (1-indexed) |

### DB Migration

No existing users — delete the SQLite DB file and let `create_all` recreate it. Add a note to the changelog about this breaking change.

## Orchestrator Changes

The orchestrator (`run_eval` async generator) has two execution paths based on `round_mode`.

### Agent mode (`round_mode == "agent"`)

```
for round in 1..num_rounds:
    yield {type: "round_started", round, total_rounds}
    for each test_case:
        yield {type: "case_started", round, case_index, case_name, total_cases}
        agent_result = bridge.send_test(test_data)
        if agent failed:
            store EvalResult(round_number=round, passed=False, error=...)
        else:
            judge_response = judge_client.chat(judge_messages)
            parsed = parse_judge_response(judge_response)
            store EvalResult(round_number=round, score=parsed.score, ...)
        yield {type: "case_completed", round, case_name, passed, ...}
    yield {type: "round_completed", round, round_summary}
yield {type: "run_completed", summary}
```

### Scorer mode (`round_mode == "scorer"`)

```
# Phase 1: Run agent once for all test cases
agent_outputs = {}
yield {type: "round_started", round: 0, phase: "agent_run"}
for each test_case:
    yield {type: "case_started", round: 0, case_index, case_name, total_cases}
    agent_result = bridge.send_test(test_data)
    agent_outputs[tc.id] = agent_result
    yield {type: "case_completed", round: 0, case_name, success: agent_result.success}

# Phase 2: Judge N times
for round in 1..num_rounds:
    yield {type: "round_started", round, total_rounds}
    for each test_case:
        if agent_outputs[tc.id] failed:
            store EvalResult(round_number=round, passed=False, error=...)
            continue
        judge_response = judge_client.chat(judge_messages)
        parsed = parse_judge_response(judge_response)
        store EvalResult(round_number=round, score=parsed.score, ...)
        yield {type: "case_completed", round, case_name, passed, ...}
    yield {type: "round_completed", round, round_summary}
yield {type: "run_completed", summary}
```

### Failure handling

If a test case fails in one round (agent error or judge error), that round's result is marked as failed. Other rounds still run. The averaged score only includes successful rounds. If all rounds fail for a test case, it is marked as failed overall.

### SSE events

New event types added:
- `round_started` — `{type, round, total_rounds}`. In scorer mode, `round=0` is used for the initial agent-run phase (not a scoring round).
- `round_completed` — `{type, round, round_summary}`. For `round=0` (scorer mode agent-run phase), `round_summary` is null since no scoring occurred.

Existing events get a `round` field added:
- `case_started` — adds `round` field
- `case_completed` — adds `round` field

## Aggregator Changes

### Per-round summary

Same as today's aggregator, but filtered by `round_number`:
```json
{"round": 1, "total": 24, "passed": 18, "pass_rate": 75.0, "avg_score": 72.5, "min_score": 40, "max_score": 95}
```

### Cross-round averaged summary

For each test case:
1. Collect all successful round scores for that test case
2. Average them → `averaged_score`
3. Determine `passed` by comparing `averaged_score >= pass_threshold`

Then compute overall stats from the averaged scores:
```json
{
  "num_rounds": 3,
  "round_mode": "agent",
  "round_summaries": [
    {"round": 1, "total": 24, "passed": 18, "pass_rate": 75.0, "avg_score": 72.5},
    {"round": 2, "total": 24, "passed": 20, "pass_rate": 83.3, "avg_score": 78.1},
    {"round": 3, "total": 24, "passed": 19, "pass_rate": 79.2, "avg_score": 75.0}
  ],
  "averaged": {"total": 24, "passed": 19, "pass_rate": 79.2, "avg_score": 75.2}
}
```

## API Changes

### Create run — `POST /api/runs`

Request body adds:
- `num_rounds: int = 1` (min 1)
- `round_mode: str = "agent"` (choices: `"agent"`, `"scorer"`)

### Run response — `GET /api/runs/{id}`

Response adds:
- `num_rounds: int`
- `round_mode: str`

### Results — `GET /api/runs/{id}/results`

Adds optional query param `?round=N` to filter by round number. Without it, returns all results across all rounds. Response adds `round_number` field to each result.

### Summary — `GET /api/runs/{id}/summary`

New endpoint. Returns the multi-round summary with per-round summaries and cross-round averages. For single-round runs, returns the same structure with `round_summaries` containing one entry and `averaged` equal to that entry.

### Existing endpoints

- `POST /runs/{id}/start` — No changes needed (runs all rounds internally).
- `GET /runs/{id}/stream` — Streams the new event types.
- `GET /runs/{id}/export` — Exports all results with a `round_number` column added.
- `GET /runs/compare` — Compares averaged scores when comparing multi-round runs.

## Schema Changes

### EvalRunCreate

Add:
- `num_rounds: int = 1`
- `round_mode: str = "agent"`

### EvalRunResponse

Add:
- `num_rounds: int`
- `round_mode: str`

### EvalResultResponse

Add:
- `round_number: int`

### New: MultiRoundSummary

```python
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

## Frontend Changes

### Create Run Form

- Add **"Rounds"** number input field (default 1, min 1)
- Add **"Round Mode"** dropdown: `"Agent (re-run full pipeline)"` / `"Scorer (re-judge only)"` — only shown when rounds > 1

### Run Detail Page — Tab Bar

Only shown when `num_rounds > 1`.

Tabs: `[Summary] [Round 1] [Round 2] ... [Round N]`

**Summary tab:**
- Header: `"Averaged across N rounds"`
- Per-round summary cards showing pass rate and avg score for each round
- Results table showing averaged scores per test case
- Pass/fail determined by averaged score vs threshold

**Round N tab:**
- Header: `"Round N of M"`
- Results table identical to current single-round layout
- Shows that round's individual results with agent messages, justification, score

### Progress Display (during execution)

When `num_rounds > 1`:
- Shows current round: `"Round 2/3"`
- Case progress within round: `"Case 5/24"`
- Round-level events update round progress

### Backward Compatibility

When `num_rounds == 1`, the page looks exactly like it does today — no tab bar, no round indicator. `round_number=1` is invisible.

### Frontend Types

```typescript
interface EvalRun {
  // existing fields...
  num_rounds: number
  round_mode: string
}

interface EvalRunCreate {
  // existing fields...
  num_rounds?: number
  round_mode?: string
}

interface EvalResult {
  // existing fields...
  round_number: number
}

interface RoundSummary {
  round: number
  total: number
  passed: number
  pass_rate: number
  avg_score?: number
  min_score?: number
  max_score?: number
}

interface MultiRoundSummary {
  num_rounds: number
  round_mode: string
  round_summaries: RoundSummary[]
  averaged: RoundSummary
}
```

### Frontend API additions

- `getRunSummary(runId)` → `GET /runs/{id}/summary`
- `getRunResults(runId, round?)` → `GET /runs/{id}/results?round=N`
- `streamRun` handles new event types: `round_started`, `round_completed`

## CLI Changes

### `runs create`

Add options:
- `--num-rounds` / `-r` (default 1)
- `--round-mode` (default `"agent"`, choices: `agent`, `scorer`)

### Top-level `run` shortcut

Add `--num-rounds` / `-r` option.

### `runs start`

Progress output shows round progression when `num_rounds > 1`:
```
Round 1/3 — Case 5/24: PM-SYS-GROUND-01... score=75, passed=True
Round 1/3 — complete: 18/24 passed (75.0%)
Round 2/3 — Case 1/24: PM-SYS-GROUND-01...
```

### `runs results`

Add `--round` / `-R` filter option:
- Without `--round`: shows all results with a `Round` column
- With `--round N`: filters to that round only, no Round column

## Files Changed

| File | Change |
|------|--------|
| `backend/app/models/eval_run.py` | Add `num_rounds`, `round_mode` columns |
| `backend/app/models/eval_result.py` | Add `round_number` column |
| `backend/app/schemas/eval_run.py` | Add fields to create/response |
| `backend/app/schemas/eval_result.py` | Add `round_number` to response |
| `backend/app/schemas/summary.py` | New file: `RoundSummary`, `MultiRoundSummary` |
| `backend/app/services/orchestrator.py` | Two-mode round loop, new SSE events |
| `backend/app/services/aggregator.py` | Per-round + cross-round aggregation, new `multi_round_summary` function |
| `backend/app/api/runs.py` | New `/summary` endpoint, `?round=` filter on results, export with round column |
| `backend/cli/main.py` | Add `--num-rounds` to top-level `run` |
| `backend/cli/runs.py` | Add `--num-rounds`, `--round-mode` to `create`; `--round` filter to `results` |
| `frontend/src/types/index.ts` | Add multi-round fields and types |
| `frontend/src/api/runs.ts` | New `getRunSummary`, update `getRunResults` with round param, new SSE events |
| `frontend/src/pages/RunDetailPage.tsx` | Tab bar, summary tab, round tabs, progress display |
| `frontend/src/pages/RunDetailPage.module.css` | Tab bar and summary styles |
| `frontend/src/pages/RunsPage.tsx` | Add Rounds + Round Mode fields to create form |

## Not In Scope

- Statistical analysis (variance, confidence intervals across rounds)
- Selective round re-run (re-run only round 2)
- Per-test-case round overrides (different rounds for different cases)
- Alembic migration setup
- Automatic round count recommendation
