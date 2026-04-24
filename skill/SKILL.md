---
name: agentic-eval
description: Run evaluations against AI agents using the AgenticEval system. Use when asked to "run eval", "evaluate an agent", "create a dataset", "create a scorer", "set up eval", "compare eval runs", "update test cases", or "iterate on scoring criteria". Covers the full eval lifecycle: dataset creation, scorer creation, adapter setup, running evals, analyzing results, and iterating on datasets/scorers based on findings.
---

# AgenticEval — Agent Operation Guide

All operations use the `agenticeval` CLI.

Full API reference: [references/api-reference.md](references/api-reference.md)
Scorer prompt writing guide: [references/scorer-guide.md](references/scorer-guide.md)

---

## Phase 1: First-Time Setup

Complete these three steps before running any eval.

### 1.1 Create a Dataset

A dataset holds test cases — each is a prompt sent to the agent plus the expected result for the judge to compare against.

```bash
# Create dataset
agenticeval datasets create --name "my-eval" --description "Eval for X capability" --target-type agent --tags "v1"
# → returns {id, name, ...}
```

Add test cases one by one:

```bash
# Single-turn test case (standard)
agenticeval datasets add-case {dataset_id} --name "basic-task" --prompt "What is 2+2?" --expected '{"answer": "4"}'
```

Multi-turn test cases use the `turns` format in the data field. Create via API or CSV import:

```bash
# Multi-turn via API
curl -X POST http://localhost:9100/api/datasets/{dataset_id}/testcases \
  -H "Content-Type: application/json" \
  -d '{
    "name": "multi-step-booking",
    "data": {
      "turns": [
        {"prompt": "Create a meeting tomorrow at 3pm"},
        {"prompt": "Change it to 4pm", "expected_result": {"criteria": "Agent confirms time change"}},
        {"prompt": "Add Bob to the invite"}
      ]
    },
    "expected_result": {"criteria": "Meeting at 4pm with Bob invited"}
  }'
```

Or bulk import via CSV:

```bash
agenticeval datasets import-csv {dataset_id} --file testcases.csv
```

CSV format: `name,data,expected_result,metadata`
- Single-turn: `data` column contains `{"prompt": "..."}`
- Multi-turn: `data` column contains `{"turns": [{"prompt": "..."}, ...]}`
- Each turn can optionally include `expected_result` for per-turn judging
- The top-level `expected_result` column is always used for final whole-conversation judging

### 1.2 Create a Scorer

The scorer defines how the judge evaluates agent responses. The `eval_prompt` is the core — it tells the judge what dimensions to score and how.

```bash
agenticeval scorers create --name "quality-scorer" \
  --eval-prompt "You are evaluating an AI agent...\n\nScore range: 0-100.\nReturn {\"score\": <0-100>, \"justification\": \"...\"}" \
  --threshold 70 --tags "v1"
```

Key facts:
- **Standard format:** Judge returns `{"score": <number>, "justification": "..."}`. `passed` = score >= `pass_threshold`.
- **Boolean rubric format:** Judge returns `{"items": {...}, "dimensions": {...}, "overall_pass_rate": 0.77, "verdict": "pass"}`. `passed` = `verdict == "pass"` AND `overall_pass_rate >= pass_threshold`. Both the scorer's verdict rules and the system threshold must agree — this lets scorers encode cascade logic (e.g., "fabrication in sub-item X force-fails downstream items Y and Z") while the system still enforces a minimum pass rate.
- Set `pass_threshold` in the 0–1 range for boolean rubrics (e.g., `0.6`), or 0–100 for standard scorers.
- See [references/scorer-guide.md](references/scorer-guide.md) for how to write effective eval prompts

### 1.3 Configure an Adapter

The adapter tells AgenticEval how to communicate with the agent under test.

**HTTP adapter** (recommended):

```bash
agenticeval adapters create --name "my-agent" --type http --config '{"base_url": "http://localhost:8080"}'
```

The agent must expose these endpoints:
- `GET /eval/health` — health check
- `POST /eval/run` — receives `{prompt, session_id?}`, returns agent response
- `POST /eval/judge` — receives `{prompt, response, expected_result, eval_prompt}`, returns `{score, justification}`

**Stdio adapter** (for CLI agents):

```bash
agenticeval adapters create --name "cli-agent" --type stdio --config '{"command": "python", "args": ["agent.py"]}'
```

**Multi-turn support:**

For agents that support multi-turn conversations (where the agent pauses waiting for user input):
- The adapter sends `session_id` in the request payload to continue an existing conversation
- First request: no `session_id` — agent starts a new session and returns `session_id` in response metadata
- Subsequent requests: `session_id` is included — agent continues the existing conversation
- HTTP adapter: `session_id` is a field in the JSON POST body
- Stdio adapter: `session_id` is a field in the JSON message on stdin

**Implementing multi-turn in your agent (important):**

When building the `/eval/run` endpoint to support multi-turn:

1. **Session management:** Keep the agent/conversation instance alive between requests. Use a `Map<session_id, agent_instance>` with idle timeout cleanup (e.g., 15 min).
2. **Return only NEW messages per turn:** This is the most common pitfall. If your agent internally maintains a full conversation history, each `/eval/run` response must return **only the messages produced by the current turn**, not the full history. The orchestrator accumulates messages across turns itself — if your agent returns the full history, messages will be duplicated.
   - Track the message count before each `streamMessage()` / `chat()` call
   - Slice the result to only return `messages[countBefore:]`
3. **First turn response:** Return `session_id` in the `metadata` field: `{"metadata": {"session_id": "..."}}`
4. **Subsequent turn responses:** Return the same `session_id` in metadata for consistency.
5. **Error handling:** If a session is not found (expired/evicted), return a clear error message so the orchestrator can report it.

---

## Phase 2: Run Evaluation

### 2.1 Create and Start a Run

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

### 2.2 Analyze Results

```bash
agenticeval runs results {run_id}
```

Each result contains:
- `score` — numeric score from the judge (0-100 for standard, 0-1 for boolean rubric)
- `passed` — boolean. Standard: `score >= pass_threshold`. Boolean rubric: `verdict == "pass" AND overall_pass_rate >= pass_threshold`.
- `judge_reasoning` — detailed justification (plain text for standard, structured JSON for boolean rubric)
- `duration_seconds` — how long the agent took

### 2.3 Compare Runs

```bash
agenticeval runs compare {run1_id} {run2_id}
```

### 2.4 Export Results

```bash
agenticeval runs export {run_id} --output results.csv
```

---

## Phase 3: Iterate

The eval→analyze→fix→re-eval loop is where the real value is.

### 3.1 Analyze Judge Reasoning

Read `judge_reasoning` from failed/low-scoring results. Classify each issue:

| Issue Type | Action |
|---|---|
| **Agent problem** | Fix agent code/skills. Don't change dataset or scorer. |
| **Scorer too strict/lenient** | Adjust `eval_prompt` weights or criteria wording. |
| **Bad test case** | Fix `expected_result`, or remove the case. |
| **Missing coverage** | Add new test cases for untested scenarios. |

### 3.2 Update Dataset

Add cases:
```bash
agenticeval datasets add-case {dataset_id} --name "edge-case-1" --prompt "..." --expected '{...}'
```

Delete cases:
```bash
agenticeval datasets delete-case {testcase_id} --yes
```

Bulk update workflow:
1. Export: `agenticeval datasets export-csv {dataset_id} --output cases.csv`
2. Edit the CSV
3. Re-import: `agenticeval datasets import-csv {dataset_id} --file cases.csv`

### 3.3 Update Scorer

```bash
agenticeval scorers update {scorer_id} --eval-prompt "updated prompt..." --threshold 75
```

### 3.4 Re-run and Compare

```bash
# Run with updated dataset/scorer
agenticeval run --dataset {dataset_id} --scorer {scorer_id} --adapter {adapter_id} --name "run-v2"

# Compare with previous run
agenticeval runs compare {old_run_id} {new_run_id}
```

### Iteration Loop

```
run eval → analyze reasoning → classify issues → fix dataset/scorer/agent → re-run → compare
     ↑                                                                              |
     └──────────────────────── repeat until satisfied ──────────────────────────────┘
```

---

## Quick Reference: Common Workflows

**"I want to eval an agent from scratch"**
→ Phase 1 (all three steps) → Phase 2

**"Scores are too low but agent seems fine"**
→ Phase 3.1 (analyze reasoning) → likely scorer issue → Phase 3.3

**"I need to add more test cases"**
→ Phase 3.2 (add/import cases) → Phase 2 (re-run)

**"I want to compare before/after a change"**
→ Phase 2.1 (new run) → Phase 2.3 (compare)

**"I want to see what's failing"**
→ Phase 2.2 (get results, filter passed=false) → Phase 3.1 (read reasoning)
