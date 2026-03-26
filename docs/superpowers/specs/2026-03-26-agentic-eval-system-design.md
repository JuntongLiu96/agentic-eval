# AgenticEval — System Design Specification

**Date:** 2026-03-26
**Status:** Draft
**Stack:** Python (FastAPI) backend + TypeScript (React) frontend

## 1. Overview

AgenticEval is a general-purpose evaluation system for any agentic AI system. It uses LLM-as-a-Judge to score agent outputs against configurable criteria. The system is designed for local debugging with source access to target agent systems.

### Target Agent Types

- **Service-type agents** — backend (C#/Python/Go) + frontend; the agent loop lives in the backend
- **App-type agents** — Electron/desktop apps (e.g., OpenClaw); the agent loop is in the local process
- **Python agents** — LangChain, custom Python agents; can be called in-process

### Four Subsystems

1. **Dataset Manager** — CRUD for eval datasets and test cases, stored in SQLite
2. **Scorer Registry** — Evaluation criteria definitions with configurable output formats + template gallery
3. **Orchestrator** — Runs evals sequentially, wiring dataset + scorer + bridge adapter together
4. **Bridge Layer** — Multi-adapter integration (HTTP, Python in-process, Stdio) to connect to any agent system

## 2. Dataset Manager

### Data Model

**Dataset:**
| Field | Type | Description |
|-------|------|-------------|
| `id` | int (PK) | Auto-increment |
| `name` | string | Human-readable dataset name |
| `description` | string | What this dataset evaluates |
| `target_type` | enum | `tool`, `e2e_flow`, `custom` |
| `tags` | JSON | List of string tags for categorization |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last modified timestamp |

**TestCase:**
| Field | Type | Description |
|-------|------|-------------|
| `id` | int (PK) | Auto-increment |
| `dataset_id` | int (FK) | References Dataset |
| `name` | string | Human-readable test case name |
| `data` | JSON | Input to send to the agent (flexible structure) |
| `expected_result` | JSON | What the agent should produce (flexible structure) |
| `metadata` | JSON | Optional extra context |

The `data` and `expected_result` fields are JSON blobs so they can hold anything: a simple string prompt, a structured tool call, or a complex multi-turn conversation setup. This keeps the schema generic across eval types.

### CSV Import/Export

**Import:** Upload a `.csv` file where each row becomes a TestCase. Columns map to `name`, `data`, `expected_result`, and optionally `metadata`. The `data`, `expected_result`, and `metadata` columns contain JSON-encoded strings (e.g., a cell might contain `{"prompt": "What is 2+2?"}`). Available via:
- Web dashboard: file upload UI
- CLI: `agenticeval datasets import --file data.csv --dataset <id>`

**Export:** Download all test cases in a dataset as a `.csv` file with the same column mapping. Available via:
- Web dashboard: download button on dataset detail page
- CLI: `agenticeval datasets export --dataset <id> --output results.csv`

### API Operations

Standard CRUD for datasets and test cases:
- `GET/POST /api/datasets` — list and create datasets
- `GET/PUT/DELETE /api/datasets/{id}` — read, update, delete a dataset
- `GET/POST /api/datasets/{id}/testcases` — list and create test cases
- `GET/PUT/DELETE /api/testcases/{id}` — read, update, delete a test case
- `POST /api/datasets/{id}/import` — import from CSV
- `GET /api/datasets/{id}/export` — export to CSV

## 3. Scorer Registry

### Data Model

**Scorer:**
| Field | Type | Description |
|-------|------|-------------|
| `id` | int (PK) | Auto-increment |
| `name` | string | Human-readable scorer name |
| `description` | string | What this scorer evaluates |
| `output_format` | enum | `binary`, `numeric`, `rubric` |
| `eval_prompt` | text | The LLM judge instruction prompt |
| `criteria` | JSON | Evaluation dimensions (see Criteria Schema below) |
| `score_range` | JSON | For numeric: `{min, max}`. For rubric: per-dimension ranges |
| `tags` | JSON | List of string tags |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last modified timestamp |

### Criteria Schema (per output_format)

**Binary criteria:**
```json
{
  "conditions": [
    {"name": "correct_tool_called", "description": "Agent called the expected tool"},
    {"name": "params_match", "description": "Tool parameters match expected values"}
  ],
  "pass_rule": "all"  // "all" = all conditions must pass, "any" = at least one
}
```

**Numeric criteria:**
```json
{
  "dimension": "overall_quality",
  "description": "Rate the overall quality of the agent's response",
  "scale": {"min": 0, "max": 100, "labels": {"0": "Completely wrong", "50": "Partially correct", "100": "Perfect"}}
}
```

**Rubric criteria:**
```json
{
  "dimensions": [
    {"name": "correctness", "description": "Is the answer factually correct?", "scale": {"min": 1, "max": 5}},
    {"name": "completeness", "description": "Did the agent address all parts?", "scale": {"min": 1, "max": 5}}
  ],
  "aggregation": "average"  // how to compute overall_score: "average", "min", "weighted"
}
```

### Deriving `passed` for Non-Binary Scorers

- **Binary:** `passed` is directly from the judge response
- **Numeric:** `passed = score >= score_range.min + (score_range.max - score_range.min) * 0.6` (i.e., 60% threshold by default). Configurable via an optional `pass_threshold` field on the scorer.
- **Rubric:** `passed = overall_score >= pass_threshold` (same 60% default on the overall aggregated score)

### Output Formats

**Binary:**
```json
{"passed": true, "reasoning": "The agent correctly..."}
```

**Numeric:**
```json
{"score": 85, "reasoning": "The agent mostly..."}
```

**Rubric (multi-dimensional):**
```json
{
  "dimensions": [
    {"name": "correctness", "score": 4, "reasoning": "..."},
    {"name": "completeness", "score": 3, "reasoning": "..."}
  ],
  "overall_score": 3.5,
  "reasoning": "Overall the agent..."
}
```

### Prompt Assembly

The orchestrator assembles the final judge prompt by concatenating:
1. **System eval prompt** — fixed preamble instructing the LLM to act as a judge and output structured JSON
2. **Scorer's eval_prompt** — scorer-specific criteria and instructions
3. **Test case expected_result** — what the correct answer should be
4. **Agent's message_list** — the actual output from the agent run

This simple concatenation approach keeps the judging process transparent and debuggable.

### Scorer Template Gallery

**ScorerTemplate:**
| Field | Type | Description |
|-------|------|-------------|
| `id` | int (PK) | Auto-increment |
| `name` | string | Template name |
| `description` | string | When to use this template |
| `category` | string | e.g., "tool-correctness", "e2e-flow", "safety" |
| `template_prompt` | text | Ready-to-copy prompt for a coding agent to generate a scorer |
| `output_format` | enum | Which format this template targets |
| `example_scorer` | JSON | Complete working scorer JSON showing the expected output |
| `usage_instructions` | text | Guidance for using the template |

**UX:** A "Templates" tab in the Scorer section showing all templates as cards. Each card has a prominent "Copy Prompt" button. Users paste the prompt into their coding agent (Claude, Copilot, etc.) to generate a scorer matching our system's format.

**Built-in templates:**
- Tool Call Correctness — did the agent call the right tool with right params?
- E2E Flow Completion — did the agent complete a multi-step workflow?
- Response Quality — general quality rubric (accuracy, completeness, helpfulness)
- Safety & Guardrails — did the agent stay within bounds?

### API Operations

- `GET/POST /api/scorers` — list and create scorers
- `GET/PUT/DELETE /api/scorers/{id}` — read, update, delete a scorer
- `GET /api/scorer-templates` — list all templates
- `GET /api/scorer-templates/{id}` — get template detail

## 4. Orchestrator

### Eval Run Configuration

**EvalRun:**
| Field | Type | Description |
|-------|------|-------------|
| `id` | int (PK) | Auto-increment |
| `name` | string | Optional human label for this run |
| `dataset_id` | int (FK) | Which dataset to use |
| `scorer_id` | int (FK) | Which scorer to judge with |
| `adapter_id` | int (FK) | Which bridge adapter to use |
| `judge_config` | JSON | See Judge LLM Resolution below |
| `status` | enum | `pending`, `running`, `completed`, `failed` |
| `started_at` | datetime | Run start time |
| `finished_at` | datetime | Run end time |

**EvalResult:**
| Field | Type | Description |
|-------|------|-------------|
| `id` | int (PK) | Auto-increment |
| `run_id` | int (FK) | References EvalRun |
| `test_case_id` | int (FK) | References TestCase |
| `agent_messages` | JSON | Full message list from the agent |
| `score` | JSON | Flexible format per scorer output_format |
| `judge_reasoning` | text | The LLM judge's explanation |
| `passed` | boolean | Overall pass/fail |
| `duration_ms` | int | How long this test case took |

### Judge LLM Resolution

The `judge_config` on EvalRun controls which LLM performs the judging:

```json
{
  "use_target_llm": true,
  "override_model": null,
  "override_api_key": null,
  "override_base_url": null
}
```

**Resolution order:**
1. If `override_model` is set, use it (with `override_api_key` and `override_base_url`)
2. If `use_target_llm` is true, call the adapter's `get_judge_llm()`. If it returns a client, use it.
3. Fall back to the **system default judge** configured via environment variables: `JUDGE_MODEL`, `JUDGE_API_KEY`, `JUDGE_BASE_URL` (e.g., `JUDGE_MODEL=gpt-4o`)
4. If none of the above resolve, the run **fails at startup** with a clear error: "No judge LLM configured. Set JUDGE_MODEL/JUDGE_API_KEY env vars or configure an override."

The system default judge env vars are documented in a `.env.example` file at the project root.

### Execution Loop (Sequential)

1. Load dataset and get all test cases
2. Initialize bridge adapter and connect to target agent system
3. For each test case:
   a. Send `test_case.data` to target agent via bridge adapter
   b. Wait for agent to complete, receive `message_list` back
   c. Assemble judge prompt: `system_eval_prompt + scorer.eval_prompt + test_case.expected_result + message_list`
   d. Call judge LLM, parse structured JSON response
   e. Store `EvalResult` to SQLite
   f. Emit SSE progress event to UI
4. Aggregate results: compute pass rate, average scores, per-dimension breakdowns
5. Mark run as complete

### Progress Tracking

Server-Sent Events (SSE) stream from the backend so the web dashboard can show:
- Which test case is currently running
- Results as they come in
- Overall progress bar

### CLI Interface

```
agenticeval run --dataset <id> --scorer <id> --adapter <id>
agenticeval run --config <run-config.json>
agenticeval datasets list / create / import / export
agenticeval scorers list / create / import
agenticeval adapters list / check
agenticeval results show <run-id>
agenticeval results compare <run-id-1> <run-id-2>
```

### Web Dashboard Pages

- **New Run** — select dataset, scorer, adapter from dropdowns; configure judge; start button
- **Run Monitor** — live progress view with SSE streaming
- **Run History** — list of all past runs with status, scores, timestamps
- **Run Detail** — per-case result table with expandable judge reasoning
- **Compare** — side-by-side two runs, highlighting score differences

### API Operations

- `GET/POST /api/runs` — list and create eval runs
- `GET /api/runs/{id}` — get run detail with results
- `POST /api/runs/{id}/start` — start an eval run
- `GET /api/runs/{id}/stream` — SSE endpoint for live progress
- `GET /api/runs/{id}/results` — get all results for a run
- `GET /api/runs/compare?run1={id}&run2={id}` — compare two runs
- `GET /api/runs/{id}/export` — export results as JSON/CSV

## 5. Bridge Layer

### BridgeAdapter Abstract Base Class

```python
class BridgeAdapter(ABC):
    """Contract that every target agent system must satisfy."""

    # Lifecycle
    async def connect(self, config: dict) -> None: ...
    async def disconnect(self) -> None: ...
    async def health_check(self) -> bool: ...

    # Core eval interface
    async def send_test(self, test_data: dict) -> AgentResult: ...

    # LLM access (for judging via target's LLM)
    async def get_judge_llm(self) -> LLMClient | None: ...

    # Metadata
    def adapter_type(self) -> str: ...        # "http", "python", "stdio"
    def target_description(self) -> str: ...  # human-readable
```

### AgentResult

```python
@dataclass
class AgentResult:
    messages: list[dict]      # the agent's full message list
    metadata: dict            # adapter-specific extras (timing, tool calls, etc.)
    success: bool             # did the agent complete without crashing?
    error: str | None         # error message if success=False
```

### Adapter Implementations

**HTTPAdapter** — for service-type agents (C#/Go/TS backends):
- Config: `{base_url, endpoints: {send_test, health, judge}}`
- Target system exposes: `POST /eval/run` (accepts test data, returns message list), `GET /eval/health`, and optionally `POST /eval/judge`
- Any language can implement these endpoints

**PythonAdapter** — for in-process Python agents:
- Config: `{module, class}` (e.g., `myagent.eval_bridge.MyAgentBridge`)
- Eval system imports and calls the target's bridge class directly
- Fastest option, no network overhead

**StdioAdapter** — for app-type agents (Electron/OpenClaw/CLI tools):
- Config: `{command, args, cwd, timeout_seconds}` (default timeout: 300s)
- Launches target as a subprocess, communicates via JSON over stdin/stdout

**Stdio Protocol (JSON Lines):**
- **Framing:** One JSON object per line (newline-delimited JSON / JSON Lines). Each message is a single line terminated by `\n`.
- **Request (eval system → target):** `{"type": "run_test", "id": "<uuid>", "data": {...}}\n`
- **Success response (target → eval system):** `{"type": "result", "id": "<uuid>", "messages": [...]}\n`
- **Error response (target → eval system):** `{"type": "error", "id": "<uuid>", "message": "description of what went wrong"}\n`
- **Health check:** `{"type": "health_check"}\n` → `{"type": "health_ok"}\n`
- **Timeout:** If no response within `timeout_seconds`, the subprocess is killed and the test case is marked as failed with error "Adapter timeout."
- **Crash handling:** If the subprocess exits unexpectedly (non-zero exit code or EOF on stdout), the current test case is marked as failed and the run is aborted.
- **Stderr:** Logged for debugging but not parsed as protocol messages.

### Adapter Registry

**Adapter (stored in SQLite):**
| Field | Type | Description |
|-------|------|-------------|
| `id` | int (PK) | Auto-increment |
| `name` | string | Human-readable adapter name |
| `adapter_type` | enum | `http`, `python`, `stdio` |
| `config` | JSON | Type-specific configuration |
| `description` | string | What target system this connects to |
| `created_at` | datetime | Creation timestamp |

### API Operations

- `GET/POST /api/adapters` — list and create adapters
- `GET/PUT/DELETE /api/adapters/{id}` — read, update, delete an adapter
- `POST /api/adapters/{id}/health` — run health check

## 6. Project Structure

```
AgenticEval/
├── backend/                        # Python (FastAPI)
│   ├── app/
│   │   ├── main.py                 # FastAPI app entry point
│   │   ├── api/                    # REST API routes
│   │   │   ├── datasets.py
│   │   │   ├── scorers.py
│   │   │   ├── adapters.py
│   │   │   ├── runs.py
│   │   │   └── templates.py        # Scorer template gallery
│   │   ├── models/                 # SQLAlchemy models
│   │   │   ├── dataset.py
│   │   │   ├── scorer.py
│   │   │   ├── adapter.py
│   │   │   ├── eval_run.py
│   │   │   └── eval_result.py
│   │   ├── services/               # Business logic
│   │   │   ├── orchestrator.py     # The core eval loop
│   │   │   ├── judge.py            # LLM judge prompt assembly & calling
│   │   │   └── aggregator.py       # Result aggregation
│   │   ├── bridge/                 # Bridge layer
│   │   │   ├── base.py             # BridgeAdapter ABC + AgentResult
│   │   │   ├── http_adapter.py
│   │   │   ├── python_adapter.py
│   │   │   ├── stdio_adapter.py
│   │   │   └── registry.py         # Adapter registration & lookup
│   │   ├── db/
│   │   │   ├── database.py         # SQLite connection & session
│   │   │   └── migrations/         # Alembic migrations
│   │   └── templates/              # Built-in scorer templates (YAML)
│   ├── cli/
│   │   └── main.py                 # typer CLI entry point
│   ├── pyproject.toml
│   └── requirements.txt
├── frontend/                       # TypeScript (React)
│   ├── src/
│   │   ├── pages/                  # Dashboard, Runs, Datasets, Scorers, etc.
│   │   ├── components/             # Shared UI components
│   │   └── api/                    # API client
│   ├── package.json
│   └── tsconfig.json
└── docs/
```

## 7. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Storage | SQLite via SQLAlchemy | No external dependencies, good for local debugging, structured queries |
| Backend framework | FastAPI | Async, auto-generates OpenAPI docs, good Python ecosystem for LLM calls |
| Frontend framework | React | Widely supported, good charting libraries (Recharts/D3) |
| CLI framework | typer | Clean Python CLI with auto-generated help |
| Bridge pattern | Multi-adapter ABC | Each target system type gets the integration style that fits |
| Execution | Sequential | Simpler, easier to debug; parallel can be added later |
| Judge LLM | Target's LLM default, configurable override | Practical default with flexibility |
| Scorer output | Configurable per scorer | Supports binary, numeric, and rubric formats |
| Progress streaming | Server-Sent Events (SSE) | Simple, unidirectional, no WebSocket complexity |
| Prompt assembly | Simple concatenation | Transparent, debuggable, users can see exactly what the judge receives |
