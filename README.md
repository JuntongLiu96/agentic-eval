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
uvicorn app.main:app --reload --port 9100
```

The API server starts at **http://localhost:9100**. API docs are at http://localhost:9100/docs.

### 2. Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

The web dashboard starts at **http://localhost:9101** and proxies API requests to the backend.

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

**What you need to implement:** Three HTTP endpoints in your agent's server.

```
GET  /eval/health        → 200 OK (any response body)
POST /eval/run           → run full agent e2e flow, treat input as user message
POST /eval/judge         → forward messages directly to LLM (no agent flow)
```

#### `POST /eval/run` — Run Agent Flow

This endpoint receives a user prompt and runs your agent's **complete end-to-end workflow** — exactly as if a real user sent that message. The agent should use its own system prompt, tools, memory, and any other internal logic. Return the full conversation message list.

**Request body:**
```json
{
  "prompt": "Book a flight from Seattle to Tokyo for next Friday",
  "metadata": {}
}
```

- `prompt` — treat this as a normal user input message to your agent
- `metadata` — reserved for future use (pass-through context)

**Response body:**
```json
{
  "messages": [
    {"role": "user", "content": "Book a flight from Seattle to Tokyo for next Friday"},
    {"role": "assistant", "content": "I'll search for flights from Seattle to Tokyo..."},
    {"role": "tool", "content": "{\"flights\": [{\"airline\": \"ANA\", \"price\": 850}]}"},
    {"role": "assistant", "content": "I found a flight on ANA for $850. Would you like to book it?"}
  ],
  "metadata": {}
}
```

Return the **full message list** including all intermediate steps (tool calls, reasoning, etc.) — this is what the judge LLM will evaluate.

#### `POST /eval/judge` — Direct LLM Call

This endpoint forwards chat messages **directly to your agent's LLM** — no agent system prompt, no e2e flow, no tools. Just a raw LLM completion call using the same model and API key your agent uses internally.

**Request body:**
```json
{
  "messages": [
    {"role": "system", "content": "You are an expert evaluation judge..."},
    {"role": "user", "content": "## Scoring Criteria\n..."}
  ]
}
```

**Response body:**
```json
{
  "content": "{\"score\": 1, \"justification\": \"The agent correctly identified the flight, called the booking tool with the right parameters, and confirmed the booking to the user.\"}"
}
```

> **Important:** Do NOT inject your agent's system prompt here. The eval system provides its own judge system prompt. Just forward the messages to the LLM and return the raw response.

#### Register the adapter

```bash
agenticeval adapters create \
  --name "my-api-agent" \
  --type http \
  --config '{"base_url": "http://localhost:5000"}'
```

> **PowerShell users:** Single quotes don't preserve JSON in PowerShell. Use escaped double quotes instead:
> ```powershell
> agenticeval adapters create --name "my-api-agent" --type http --config "{`"base_url`": `"http://localhost:5000`"}"
> ```

Or via the web dashboard: go to **Adapters → + New Adapter**.

The full config object supports custom endpoint paths:
```json
{
  "base_url": "http://localhost:5000",
  "endpoints": {
    "send_test": "/eval/run",
    "health": "/eval/health",
    "judge": "/eval/judge"
  }
}
```

#### Integration Prompt for Your Coding Agent

Copy the prompt below and paste it into your coding agent (Claude, Copilot, GitHub Copilot Workspace, etc.) to generate the three eval endpoints for your project:

<details>
<summary><strong>Click to expand the full integration prompt</strong></summary>

````
I need to add three HTTP endpoints to my project for integration with AgenticEval,
an external evaluation system that tests my AI agent. These endpoints let AgenticEval
send test inputs to my agent and use my agent's LLM for scoring.

## What to implement

Add these three endpoints to my existing server:

### 1. GET /eval/health
Simple health check. Return 200 OK if the agent is ready.

### 2. POST /eval/run
This is the core eval endpoint. It should:
1. Accept a JSON body: {"prompt": "...", "metadata": {}}
2. Treat the "prompt" as a REAL user message — as if a user typed it
3. Run my agent's COMPLETE standard workflow:
   - Use the agent's normal system prompt
   - Execute the full agent loop (tool calls, reasoning, memory, etc.)
   - Do NOT skip any steps — this must behave identically to a real user interaction
4. Collect ALL messages from the conversation into a list
5. Return: {"messages": [...], "metadata": {}}

The messages array should include the full conversation history in order:
- {"role": "user", "content": "the prompt"}
- {"role": "assistant", "content": "agent's response"}
- {"role": "tool", "content": "tool results"} (if applicable)
- ... any additional turns

Example request:
```json
{"prompt": "What is the weather in Seattle?", "metadata": {}}
```

Example response:
```json
{
  "messages": [
    {"role": "user", "content": "What is the weather in Seattle?"},
    {"role": "assistant", "content": "Let me check the weather for you."},
    {"role": "tool", "content": "{\"temp\": 55, \"condition\": \"cloudy\"}"},
    {"role": "assistant", "content": "It's currently 55°F and cloudy in Seattle."}
  ],
  "metadata": {}
}
```

### 3. POST /eval/judge
This endpoint is for LLM-based scoring. It should:
1. Accept a JSON body: {"messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]}
2. Forward these messages DIRECTLY to my agent's LLM (same model, same API key)
3. Do NOT add my agent's system prompt — the eval system provides its own judge prompt
4. Do NOT run the agent loop, tools, or any agent logic
5. Just call the LLM's chat completion API and return the raw text response
6. Return: {"content": "...the LLM response text..."}

This is essentially a thin proxy to my LLM. The eval system uses it to judge
the agent's output using the same model the agent uses internally.

Example request:
```json
{
  "messages": [
    {"role": "system", "content": "You are an expert evaluation judge..."},
    {"role": "user", "content": "## Scoring Criteria\nDid the agent answer correctly?\n\n## Expected Result\n{\"answer\": \"55°F and cloudy\"}\n\n## Agent Output\n[{\"role\": \"assistant\", \"content\": \"It's 55°F and cloudy.\"}]\n\n## Scoring Instructions\nScore range: 0 (fail) or 1 (pass).\n\nRespond with a JSON object containing:\n- \"score\": a numeric score value\n- \"justification\": a detailed explanation of why you assigned this score"}
  ]
}
```

Example response:
```json
{"content": "{\"score\": 1, \"justification\": \"The agent correctly reported the weather as 55°F and cloudy, matching the expected result exactly.\"}"}
```

## Important distinctions

| Aspect | /eval/run | /eval/judge |
|--------|-----------|-------------|
| Purpose | Test the agent's real behavior | Score the agent's output |
| System prompt | USE agent's own system prompt | Do NOT add agent's system prompt |
| Agent loop | YES — full e2e agent workflow | NO — just a raw LLM call |
| Tools | YES — agent uses its tools normally | NO — no tools, no agent logic |
| Input | User prompt string | Chat messages array |
| Output | Full message list from agent run | Raw LLM response text |

## Requirements
- These endpoints should be added alongside the existing server routes
- They should reuse the existing agent infrastructure (same LLM client, same tools, same config)
- The /eval/run endpoint must produce identical behavior to a real user interaction
- The /eval/judge endpoint must be a minimal LLM proxy with no agent logic
- Error handling: return appropriate HTTP error codes (500 for internal errors, 400 for bad input)
- The endpoints should be under the /eval path prefix to avoid conflicts with existing routes
````

</details>

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

Run a test (starts full agent e2e flow):
```
→ stdin:  {"type": "run_test", "id": "abc-123", "data": {"prompt": "What is 2+2?"}}\n
← stdout: {"messages": [{"role": "user", "content": "What is 2+2?"}, {"role": "assistant", "content": "4"}], "metadata": {}}\n
```

Judge (direct LLM call — no agent system prompt, no e2e flow):
```
→ stdin:  {"type": "judge", "messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]}\n
← stdout: {"type": "judge_result", "content": "...the LLM response..."}\n
```

Error:
```
← stdout: {"type": "error", "message": "something went wrong"}\n
```

For `run_test`: treat `data.prompt` as a normal user message, run your agent's full workflow, and return all messages. For `judge`: forward messages directly to your LLM without adding agent system prompts.

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
        """Required: run full agent e2e flow, treat prompt as real user input."""
        prompt = test_data["prompt"]
        # Run your agent's complete workflow — same as a real user interaction
        messages = await my_agent.run_full_flow(user_message=prompt)
        return AgentResult(messages=messages)

    async def get_judge_llm(self):
        """Optional: return an LLM client for judging (direct LLM call, no agent flow)."""
        return MyLLMClient()  # thin wrapper around your LLM API


class MyLLMClient:
    """Implements the LLMClient protocol — just calls your LLM directly."""
    async def chat(self, messages: list[dict[str, str]]) -> str:
        # Forward messages to your LLM — NO agent system prompt, NO tools
        response = await my_llm.chat_completion(messages=messages)
        return response.content
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
"book-flight","{""prompt"": ""Book a flight from Seattle to Tokyo for next Friday""}","{""booked"": true, ""destination"": ""Tokyo""}","{}"
"weather-check","{""prompt"": ""What is the weather in Seattle?""}","{""answer"": ""55°F and cloudy""}","{}"
```

The `data` column should contain a JSON object with a `prompt` field — this is what gets sent to your agent as user input. The `expected_result` column defines what the judge LLM compares against. Both columns contain JSON-encoded strings.

### Via Web Dashboard

Go to **Datasets → + New Dataset**, then click into the dataset to import CSV files.

## Creating Scorers

Scorers define how the judge LLM evaluates your agent's output. Three output formats are supported:

| Format | What the judge returns | Pass logic |
|--------|----------------------|------------|
| **binary** | `{"score": 0 or 1, "justification": "..."}` | Pass if score >= 1 |
| **numeric** | `{"score": 85, "justification": "..."}` | Pass if score ≥ threshold (default 60%) |
| **rubric** | `{"score": 4.5, "overall_score": 4.5, "justification": "..."}` | Pass if overall_score ≥ threshold |

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

With the backend running, visit **http://localhost:9100/docs** for the auto-generated OpenAPI (Swagger) documentation.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12+, FastAPI, SQLAlchemy 2.0 (async), SQLite |
| Frontend | React 18, TypeScript, Vite, React Router, TanStack React Query |
| CLI | Typer, Rich, httpx |
| Testing | pytest, pytest-asyncio, httpx (test client) |
| Judge LLM | OpenAI-compatible `/chat/completions` API |
