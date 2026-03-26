# AgenticEval

A general-purpose evaluation system for any agentic AI system, using LLM-as-a-Judge scoring. Evaluate your AI agents against test datasets with configurable scoring criteria — works with any agent that exposes an HTTP API, runs as a subprocess, or can be imported as a Python module.

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+ (for the web dashboard)

### 1. Start the Backend

```bash
cd backend
cp .env.example .env          # configure your judge LLM (see Environment Variables below)
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

The API server starts at **http://localhost:8000**. API docs are at http://localhost:8000/docs.

### 2. Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

The web dashboard starts at **http://localhost:3000** and proxies API requests to the backend.

### 3. Use the CLI (optional)

```bash
cd backend
pip install -e .
agenticeval --help
```

## Environment Variables

Create a `backend/.env` file (copy from `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./agenticeval.db` | Database connection URL |
| `JUDGE_MODEL` | *(empty)* | Default judge LLM model name (e.g. `gpt-4o`, `claude-3-sonnet`) |
| `JUDGE_API_KEY` | *(empty)* | API key for the judge LLM |
| `JUDGE_BASE_URL` | *(empty)* | Base URL for the judge LLM API (defaults to OpenAI's endpoint) |

The judge LLM uses the OpenAI-compatible `/chat/completions` endpoint, so it works with OpenAI, Azure OpenAI, Ollama, vLLM, or any compatible provider.

## How It Works

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Test Data   │────▶│   Bridge    │────▶│ Your Agent  │
│  (Dataset)   │     │  Adapter    │     │  (Target)   │
└─────────────┘     └──────┬──────┘     └──────┬──────┘
                           │                    │
                           │◀── agent output ───┘
                           ▼
                    ┌─────────────┐
                    │  LLM Judge  │  ← eval_prompt + expected_result + agent_output
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   Score &   │  → stored in SQLite, displayed in dashboard
                    │  Reasoning  │
                    └─────────────┘
```

1. You create a **Dataset** with test cases (input data + expected results)
2. You create a **Scorer** with evaluation criteria (prompts for the judge LLM)
3. You configure a **Bridge Adapter** to connect to your agent
4. You start an **Eval Run** — the system sends each test case to your agent, collects the output, and asks a judge LLM to score it

## Integrating Your Agent

AgenticEval connects to your agent through one of three bridge adapters. Choose the one that fits your agent's architecture.

### Option A: HTTP Adapter (recommended for service-type agents)

Best for agents with a backend server (C#, Python, Go, Node.js, etc.).

**What you need to implement:** Two HTTP endpoints in your agent's server.

```
GET  /eval/health        → 200 OK (any response body)
POST /eval/run           → accepts JSON test data, returns agent output
```

**`POST /eval/run` request body:**
```json
{
  "prompt": "What is 2+2?",
  "context": "math test"
}
```
*(The structure matches whatever you put in your test case's `data` field.)*

**`POST /eval/run` response body:**
```json
{
  "messages": [
    {"role": "assistant", "content": "The answer is 4."}
  ],
  "metadata": {}
}
```

**Register the adapter in AgenticEval:**

```bash
agenticeval adapters create \
  --name "my-api-agent" \
  --type http \
  --config '{"base_url": "http://localhost:5000"}'
```

Or via the web dashboard: go to **Adapters → + New Adapter**.

The full config object supports custom endpoint paths:
```json
{
  "base_url": "http://localhost:5000",
  "endpoints": {
    "send_test": "/eval/run",
    "health": "/eval/health"
  }
}
```

---

### Option B: Stdio Adapter (for desktop/Electron apps and CLI tools)

Best for agents that run as a local process (Electron apps, CLI tools, etc.).

**What you need to implement:** A process that reads JSON from stdin and writes JSON to stdout (one JSON object per line).

**Protocol (newline-delimited JSON):**

Health check:
```
→ stdin:  {"type": "health_check"}\n
← stdout: {"type": "health_ok"}\n
```

Run a test:
```
→ stdin:  {"type": "run_test", "id": "abc-123", "data": {"prompt": "What is 2+2?"}}\n
← stdout: {"messages": [{"role": "assistant", "content": "4"}], "metadata": {}}\n
```

Error:
```
← stdout: {"type": "error", "message": "something went wrong"}\n
```

**Register the adapter:**

```bash
agenticeval adapters create \
  --name "my-cli-agent" \
  --type stdio \
  --config '{"command": "python", "args": ["my_agent.py"], "cwd": "/path/to/agent"}'
```

Config options:
```json
{
  "command": "python",
  "args": ["my_agent.py"],
  "cwd": "/path/to/agent",
  "timeout_seconds": 300
}
```

---

### Option C: Python Adapter (for in-process Python agents)

Best for Python agents (LangChain, custom agents, etc.) where you want zero network overhead.

**What you need to implement:** A Python class with an async `send_test` method.

```python
# my_agents/eval_bridge.py
from dataclasses import dataclass, field
from typing import Any

@dataclass
class AgentResult:
    messages: list[dict[str, Any]]
    metadata: dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: str | None = None

class MyAgentBridge:
    async def connect(self, config: dict) -> None:
        """Optional: initialize your agent."""
        pass

    async def disconnect(self) -> None:
        """Optional: cleanup."""
        pass

    async def health_check(self) -> bool:
        """Optional: return True if agent is ready."""
        return True

    async def send_test(self, test_data: dict) -> AgentResult:
        """Required: run a test and return the agent's output."""
        # Call your agent here
        result = await my_agent.run(test_data["prompt"])
        return AgentResult(
            messages=[{"role": "assistant", "content": result}]
        )

    async def get_judge_llm(self):
        """Optional: return an LLM client for judging (uses your agent's LLM)."""
        return None
```

**Register the adapter:**

```bash
agenticeval adapters create \
  --name "my-python-agent" \
  --type python \
  --config '{"module": "my_agents.eval_bridge", "class": "MyAgentBridge"}'
```

> **Note:** The module must be importable from the backend's working directory. Add your agent's path to `PYTHONPATH` if needed.

---

## Creating Datasets

### Via CLI

```bash
# Create a dataset
agenticeval datasets create --name "Math QA" --target-type tool

# Import test cases from CSV
agenticeval datasets import-csv 1 --file test_cases.csv

# Export test cases
agenticeval datasets export-csv 1 --output exported.csv
```

### CSV Format

```csv
name,data,expected_result,metadata
"addition","{"prompt": "What is 2+2?"}","{"answer": "4"}","{}"
"subtraction","{"prompt": "What is 10-3?"}","{"answer": "7"}","{}"
```

The `data`, `expected_result`, and `metadata` columns contain JSON-encoded strings.

### Via Web Dashboard

Go to **Datasets → + New Dataset**, then click into the dataset to import CSV files.

## Creating Scorers

Scorers define how the judge LLM evaluates your agent's output. Three output formats are supported:

| Format | What the judge returns | Pass logic |
|--------|----------------------|------------|
| **binary** | `{"passed": true/false, "reasoning": "..."}` | Direct pass/fail |
| **numeric** | `{"score": 85, "reasoning": "..."}` | Pass if score ≥ threshold (default 60%) |
| **rubric** | `{"dimensions": [...], "overall_score": 3.5}` | Pass if overall score ≥ threshold |

### Via CLI

```bash
agenticeval scorers create \
  --name "answer-correctness" \
  --output-format binary \
  --eval-prompt "Compare the agent's answer to the expected answer. Return {\"passed\": true} if they match semantically."
```

### Using Scorer Templates

Browse built-in templates via the dashboard (**Templates** tab) or CLI:

```bash
agenticeval templates list
agenticeval templates get 1    # shows the copy-paste prompt
```

Copy the template prompt, paste it into your coding agent (Claude, Copilot, etc.), and ask it to generate a scorer for your specific use case.

## Running Evaluations

### Via CLI (quickest)

```bash
# One-shot: create and immediately run
agenticeval run --dataset 1 --scorer 1 --adapter 1 --name "my-eval"

# Or step by step
agenticeval runs create --dataset 1 --scorer 1 --adapter 1 --name "my-eval"
agenticeval runs start 1

# View results
agenticeval runs results 1

# Compare two runs
agenticeval runs compare 1 2

# Export to CSV
agenticeval runs export 1 --output results.csv
```

### Via Web Dashboard

1. Go to **Runs → + New Run**
2. Select your dataset, scorer, and adapter from the dropdowns
3. Click **Create Run**, then click into the run and press **Start Run**
4. Watch live progress via SSE streaming
5. Review results with expandable judge reasoning

### Judge LLM Configuration

By default, the system uses the env var defaults (`JUDGE_MODEL`, `JUDGE_API_KEY`). You can override per-run:

```bash
agenticeval run --dataset 1 --scorer 1 --adapter 1 \
  --judge-config '{"override_model": "gpt-4o", "override_api_key": "sk-...", "override_base_url": "https://api.openai.com/v1"}'
```

**Resolution order:**
1. Per-run override (`judge_config.override_model`)
2. Target agent's LLM (if adapter implements `get_judge_llm()`)
3. System defaults (`JUDGE_MODEL` / `JUDGE_API_KEY` env vars)
4. Error (if nothing is configured)

## Project Structure

```
AgenticEval/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── config.py            # Settings (env vars)
│   │   ├── api/                 # REST API routes
│   │   │   ├── datasets.py      #   Dataset + TestCase CRUD + CSV
│   │   │   ├── scorers.py       #   Scorer CRUD
│   │   │   ├── templates.py     #   Scorer template gallery
│   │   │   ├── adapters.py      #   Adapter CRUD + health check
│   │   │   └── runs.py          #   Eval run CRUD + start + SSE + compare
│   │   ├── models/              # SQLAlchemy ORM models
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   ├── services/            # Business logic
│   │   │   ├── orchestrator.py  #   Core eval loop
│   │   │   ├── judge.py         #   LLM judge (prompt assembly + API call)
│   │   │   └── aggregator.py    #   Result aggregation
│   │   ├── bridge/              # Bridge adapters
│   │   │   ├── base.py          #   BridgeAdapter ABC + AgentResult
│   │   │   ├── http_adapter.py  #   HTTP adapter
│   │   │   ├── stdio_adapter.py #   Stdio subprocess adapter
│   │   │   ├── python_adapter.py#   In-process Python adapter
│   │   │   └── registry.py      #   Adapter factory
│   │   └── templates/           # Built-in scorer templates (YAML)
│   ├── cli/                     # Typer CLI
│   └── tests/                   # 105 pytest tests
├── frontend/
│   ├── src/
│   │   ├── pages/               # React page components
│   │   ├── components/          # Shared UI components
│   │   ├── api/                 # API client modules
│   │   └── types/               # TypeScript interfaces
│   └── package.json
└── docs/
    └── superpowers/
        ├── specs/               # System design spec
        └── plans/               # Implementation plans
```

## Running Tests

```bash
# Backend (105 tests)
cd backend
pip install -e ".[dev]"
pytest -v

# Frontend (TypeScript check)
cd frontend
npx tsc --noEmit
```

## API Documentation

With the backend running, visit **http://localhost:8000/docs** for the auto-generated OpenAPI (Swagger) documentation.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12+, FastAPI, SQLAlchemy 2.0 (async), SQLite |
| Frontend | React 18, TypeScript, Vite, React Router, TanStack React Query |
| CLI | Typer, Rich, httpx |
| Testing | pytest, pytest-asyncio, httpx (test client) |
| Judge LLM | OpenAI-compatible `/chat/completions` API |
