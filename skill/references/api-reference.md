# AgenticEval API Reference

Base URL: `http://localhost:9100`
All requests: `Content-Type: application/json`

---

## Datasets

| Method | Endpoint | Body / Params | Returns |
|--------|----------|---------------|---------|
| `GET` | `/api/datasets` | — | `[{id, name, description, target_type, tags, created_at}]` |
| `POST` | `/api/datasets` | `{name, description, target_type, tags}` | `{id, name, ...}` |
| `GET` | `/api/datasets/{id}` | — | `{id, name, description, target_type, tags, testcase_count}` |
| `DELETE` | `/api/datasets/{id}` | — | `204` |

## Test Cases

| Method | Endpoint | Body / Params | Returns |
|--------|----------|---------------|---------|
| `GET` | `/api/datasets/{id}/testcases` | — | `[{id, name, data, expected_result, metadata}]` |
| `POST` | `/api/datasets/{id}/testcases` | `{name, data: {prompt: "..."} or {turns: [...]}, expected_result: {...}, metadata?}` | `{id, name, ...}` |
| `POST` | `/api/datasets/{id}/import` | multipart `file=@data.csv` | `{imported_count}` |
| `GET` | `/api/datasets/{id}/export` | — | CSV file |
| `DELETE` | `/api/testcases/{id}` | — | `204` |

CSV columns: `name,data,expected_result,metadata`
- `data` must be JSON with a `prompt` key: `{"prompt": "user input here"}`
- Multi-turn `data`: `{"turns": [{"prompt": "msg1"}, {"prompt": "msg2", "expected_result": {...}}]}`
- Per-turn `expected_result` is optional; top-level `expected_result` is used for final scoring
- `expected_result` is JSON the judge compares against

## Scorers

| Method | Endpoint | Body / Params | Returns |
|--------|----------|---------------|---------|
| `GET` | `/api/scorers` | — | `[{id, name, eval_prompt, pass_threshold, tags}]` |
| `POST` | `/api/scorers` | `{name, eval_prompt, pass_threshold, tags}` | `{id, name, ...}` |
| `GET` | `/api/scorers/{id}` | — | `{id, name, eval_prompt, pass_threshold, tags}` |
| `PUT` | `/api/scorers/{id}` | `{eval_prompt?, pass_threshold?, tags?}` | `{id, name, ...}` |
| `DELETE` | `/api/scorers/{id}` | — | `204` |

## Adapters

| Method | Endpoint | Body / Params | Returns |
|--------|----------|---------------|---------|
| `GET` | `/api/adapters` | — | `[{id, name, type, config}]` |
| `POST` | `/api/adapters` | `{name, type, config}` | `{id, name, ...}` |
| `DELETE` | `/api/adapters/{id}` | — | `204` |

Adapter types:
- `http`: `config: {base_url: "http://..."}` — agent must serve `/eval/health`, `/eval/run`, `/eval/judge`
- `stdio`: `config: {command: "...", args: [...]}` — agent runs as subprocess

### Multi-turn adapter contract

For multi-turn support, the agent's `/eval/run` endpoint must:
- Accept optional `session_id` in the request body
- When `session_id` is absent: start a new conversation, return `session_id` in `metadata`
- When `session_id` is present: continue the existing conversation
- **Return only NEW messages from the current turn** — not the full conversation history. The orchestrator accumulates messages across turns. If your agent returns full history, messages will be duplicated.

## Runs

| Method | Endpoint | Body / Params | Returns |
|--------|----------|---------------|---------|
| `GET` | `/api/runs` | — | `[{id, name, status, dataset_id, scorer_id, adapter_id, created_at}]` |
| `POST` | `/api/runs` | `{dataset_id, scorer_id, adapter_id, name?, num_rounds?, round_mode?}` | `{id, name, status: "pending", num_rounds, round_mode}` |
| `GET` | `/api/runs/{id}` | — | `{id, status, started_at, finished_at, ...}` |
| `POST` | `/api/runs/{id}/start` | — | Synchronous. Returns when complete. `{id, status: "completed"}` |
| `GET` | `/api/runs/{id}/results` | `?round=N` (optional) | `[{testcase_id, round_number, score, passed, judge_reasoning, duration_seconds}]` |
| `GET` | `/api/runs/{id}/summary` | — | `{num_rounds, round_mode, round_summaries: [...], averaged: {...}, by_quadrant?: {...}}` |
| `GET` | `/api/runs/compare` | `?run1_id=X&run2_id=Y` | Per-testcase comparison with deltas |
| `POST` | `/api/runs/comparison` | `{baseline_run_id, warm_run_id, metrics?}` | **AE-5**: paired cold/warm metric deltas (`n_reduction` etc.) per test case |
| `GET` | `/api/runs/{id}/stream` | — | Server-Sent Events: `run_started`, `round_started`, `phase_started`, `case_started`, `turn_completed`, `case_completed`, `round_completed`, `run_completed`, `error` |
| `GET` | `/api/runs/{id}/export` | — | CSV file |
| `DELETE` | `/api/runs/{id}` | — | `204` |

Run statuses: `pending` → `running` → `completed` | `failed`

**SSE event types** (`/api/runs/{id}/stream`):
- `run_started`, `run_completed` — bracket the whole run.
- `round_started` / `round_completed` — bracket each round (round 0 in scorer mode = agent phase).
- `phase_started` (AE-11) — emitted at scorer-mode phase boundaries: `{phase: "agent_run"}` and `{phase: "judge"}`.
- `case_started`, `case_completed`, `turn_completed` — per-test-case progress.

## Dataset imports

| Method | Endpoint | Body | Returns |
|--------|----------|------|---------|
| `POST` | `/api/datasets/import-yaml` | multipart YAML file | **AE-4**: created dataset |
| `POST` | `/api/datasets/import-json` | multipart JSON file | **AE-4**: created dataset |

Document shape: `{name, description?, target_type?, tags?, rows: [{name, data, expected_result, metadata?}]}`.

## Scorer types

| `scorer_type` | Behavior |
|---|---|
| `llm_judge` | Default — LLM grades the messages against `eval_prompt`. |
| `boolean_rubric` | LLM returns a structured rubric (`items`, `dimensions`, `verdict`). |
| `programmatic` (AE-1) | Deterministic rule eval against `agent_metadata`. `config = {rules: [{path, op, value}], pass_threshold}`. No LLM call. |
| `series` (AE-6) | Cross-round assertions: `monotonic_increasing`, `monotonic_decreasing`, `equals`, `delta_at_least`. |

## Per-quadrant aggregation (AE-7)

`GET /api/runs/{id}/summary` includes `by_quadrant: {<label>: {total, passed, pass_rate, avg_score?}}` when test cases carry a `quadrant` tag in `TestCase.metadata`. Multi-tagged cases (e.g. `["cross-episode", "execution-oriented"]`) contribute to every matching bucket. Cases without a tag fall into `unlabeled`.

## Result Object

```json
{
  "testcase_id": "...",
  "testcase_name": "...",
  "score": 85,
  "passed": true,
  "judge_reasoning": "Criterion A (30/30): ... Criterion B (25/30): ... Criterion C (30/40): ...",
  "duration_seconds": 12.3,
  "turn_results": null
}
```

`turn_results` is `null` for single-turn test cases. Only populated for turns that have per-turn `expected_result`.

`passed` = `score >= scorer.pass_threshold`
