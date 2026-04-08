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
agenticeval datasets add-case {dataset_id} --name "basic-task" --prompt "What is 2+2?" --expected '{"answer": "4"}'
```

Or bulk import via CSV:

```bash
agenticeval datasets import-csv {dataset_id} --file testcases.csv
```

CSV format: `name,data,expected_result,metadata`
- `data` column must contain `{"prompt": "..."}` — this is the user input sent to the agent
- `expected_result` is what the judge compares the agent output against

### 1.2 Create a Scorer

The scorer defines how the judge evaluates agent responses. The `eval_prompt` is the core — it tells the judge what dimensions to score and how.

```bash
agenticeval scorers create --name "quality-scorer" \
  --eval-prompt "You are evaluating an AI agent...\n\nScore range: 0-100.\nReturn {\"score\": <0-100>, \"justification\": \"...\"}" \
  --threshold 70 --tags "v1"
```

Key facts:
- Judge always returns: `{"score": <number>, "justification": "..."}`
- `passed` = score >= `pass_threshold`
- See [references/scorer-guide.md](references/scorer-guide.md) for how to write effective eval prompts

### 1.3 Configure an Adapter

The adapter tells AgenticEval how to communicate with the agent under test.

**HTTP adapter** (recommended):

```bash
agenticeval adapters create --name "my-agent" --type http --config '{"base_url": "http://localhost:8080"}'
```

The agent must expose these endpoints:
- `GET /eval/health` — health check
- `POST /eval/run` — receives `{prompt, context?}`, returns agent response
- `POST /eval/judge` — receives `{prompt, response, expected_result, eval_prompt}`, returns `{score, justification}`

**Stdio adapter** (for CLI agents):

```bash
agenticeval adapters create --name "cli-agent" --type stdio --config '{"command": "python", "args": ["agent.py"]}'
```

---

## Phase 2: Run Evaluation

### 2.1 Create and Start a Run

```bash
# One-step create + start (recommended)
agenticeval run --dataset {dataset_id} --scorer {scorer_id} --adapter {adapter_id} --name "run-v1"

# Alternative: separate create + start
agenticeval runs create --dataset {dataset_id} --scorer {scorer_id} --adapter {adapter_id} --name "run-v1"
agenticeval runs start {run_id}
```

### 2.2 Analyze Results

```bash
agenticeval runs results {run_id}
```

Each result contains:
- `score` — numeric score from the judge
- `passed` — boolean (score >= pass_threshold)
- `judge_reasoning` — detailed justification per criteria
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
