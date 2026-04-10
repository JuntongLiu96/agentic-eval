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
| `POST` | `/api/datasets/{id}/testcases` | `{name, data: {prompt: "..."}, expected_result: {...}, metadata?}` | `{id, name, ...}` |
| `POST` | `/api/datasets/{id}/import` | multipart `file=@data.csv` | `{imported_count}` |
| `GET` | `/api/datasets/{id}/export` | — | CSV file |
| `DELETE` | `/api/testcases/{id}` | — | `204` |

CSV columns: `name,data,expected_result,metadata`
- `data` must be JSON with a `prompt` key: `{"prompt": "user input here"}`
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

## Runs

| Method | Endpoint | Body / Params | Returns |
|--------|----------|---------------|---------|
| `GET` | `/api/runs` | — | `[{id, name, status, dataset_id, scorer_id, adapter_id, created_at}]` |
| `POST` | `/api/runs` | `{dataset_id, scorer_id, adapter_id, name?, num_rounds?, round_mode?}` | `{id, name, status: "pending", num_rounds, round_mode}` |
| `GET` | `/api/runs/{id}` | — | `{id, status, started_at, finished_at, ...}` |
| `POST` | `/api/runs/{id}/start` | — | Synchronous. Returns when complete. `{id, status: "completed"}` |
| `GET` | `/api/runs/{id}/results` | `?round=N` (optional) | `[{testcase_id, round_number, score, passed, judge_reasoning, duration_seconds}]` |
| `GET` | `/api/runs/{id}/summary` | — | `{num_rounds, round_mode, round_summaries: [...], averaged: {...}}` |
| `GET` | `/api/runs/compare` | `?run1_id=X&run2_id=Y` | Per-testcase comparison with deltas |
| `GET` | `/api/runs/{id}/export` | — | CSV file |
| `DELETE` | `/api/runs/{id}` | — | `204` |

Run statuses: `pending` → `running` → `completed` | `failed`

## Result Object

```json
{
  "testcase_id": "...",
  "testcase_name": "...",
  "score": 85,
  "passed": true,
  "judge_reasoning": "Criterion A (30/30): ... Criterion B (25/30): ... Criterion C (30/40): ...",
  "duration_seconds": 12.3
}
```

`passed` = `score >= scorer.pass_threshold`
