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
2. You create a **Scorer** with an eval prompt (scoring criteria, score range, and rules — all in one prompt)
3. You configure a **Bridge Adapter** to connect to your agent
4. You start an **Eval Run** — the system sends each test case to your agent, collects the output, and asks a judge LLM to score it

## Integrating Your Agent

AgenticEval connects to your agent through one of three bridge adapters. Choose the one that fits your agent's architecture.

### Option A: HTTP Adapter (recommended for most agents)

Best for agents with a backend server (C#, Python, Go, Node.js, etc.) **and** desktop/Electron apps running in eval mode.

**How it works:** Your agent exposes three HTTP endpoints. You start your agent yourself, then point AgenticEval at it. This works for any agent that can serve HTTP — backend services, Electron apps with a local eval server, CLI tools with an embedded HTTP server, etc.

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
  "sub_agent_messages": [
    {"role": "system", "content": "You are a flight search agent..."},
    {"role": "user", "content": "Search flights SEA to TYO on 2026-04-04"},
    {"role": "assistant", "content": "Found 3 flights: ANA $850, JAL $920, United $780"},
    {"role": "tool", "content": "{\"api\": \"flights_api\", \"results\": 3}"}
  ],
  "metadata": {}
}
```

- `messages` — **(required)** the main agent's full conversation history
- `sub_agent_messages` — **(optional)** message lists from sub-agents (tool agents, planning agents, etc.) that ran as part of this workflow. The judge LLM will see these as additional context for evaluation.
- `metadata` — optional pass-through data

Return the **full message list** including all intermediate steps (tool calls, reasoning, etc.) — this is what the judge LLM will evaluate. If your agent delegates to sub-agents, include their conversations in `sub_agent_messages` so the judge can evaluate the complete workflow.

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

#### For Electron / Desktop Apps

Electron and desktop apps work great with the HTTP adapter. Add a small eval HTTP server that starts when your app launches in eval mode:

1. Add eval mode to your app: `npx electron . --eval-mode --eval-port 9200`
2. In eval mode, start a local HTTP server (e.g., Express) on the specified port exposing `/eval/health`, `/eval/run`, `/eval/judge`
3. The `/eval/run` handler triggers your app's agent flow programmatically and returns the message list
4. Start your app first, then configure the AgenticEval adapter:

```bash
agenticeval adapters create --name "my-electron-app" --type http \
  --config '{"base_url": "http://localhost:9200"}'
```

This is better than the Stdio adapter for desktop apps because: the app initializes fully before eval starts, no stdout pollution from GUI logs, and you control the app lifecycle.

#### Register the adapter

```bash
agenticeval adapters create \
  --name "my-api-agent" \
  --type http \
  --config '{"base_url": "http://localhost:5000"}'
```

> **PowerShell users:** PowerShell strips inner quotes from JSON arguments. The CLI automatically repairs this, so just use single quotes:
> ```powershell
> agenticeval adapters create --name "my-api-agent" --type http --config '{"base_url": "http://localhost:5000"}'
> ```

Or via the web dashboard: go to **Adapters → + New Adapter**.

The full config object:
```json
{
  "base_url": "http://localhost:5000",
  "auth_token": "Bearer eyJ...your-token-here...",
  "endpoints": {
    "send_test": "/eval/run",
    "health": "/eval/health",
    "judge": "/eval/judge"
  }
}
```

- `base_url` — **(required)** target agent's server URL
- `auth_token` — **(optional)** sent as `Authorization` header on every request. Supports both `"Bearer eyJ..."` and raw `"eyJ..."` formats (auto-prefixes `Bearer ` if missing). Use this for agents behind auth (e.g., Azure AD tokens).
- `endpoints` — **(optional)** custom endpoint paths (defaults shown above)

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
4. Collect ALL messages from the main agent conversation into a list
5. If the agent delegates to sub-agents (tool agents, planning agents, etc.), collect their message lists too
6. Return: {"messages": [...], "sub_agent_messages": [...], "metadata": {}}

The messages array should include the full conversation history in order:
- {"role": "user", "content": "the prompt"}
- {"role": "assistant", "content": "agent's response"}
- {"role": "tool", "content": "tool results"} (if applicable)
- ... any additional turns

The sub_agent_messages array is OPTIONAL — include it only if your agent uses sub-agents.
Each entry is a message from a sub-agent's conversation (same role/content format).

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
  "sub_agent_messages": [
    {"role": "system", "content": "You are a weather lookup agent."},
    {"role": "user", "content": "Get weather for Seattle, WA"},
    {"role": "assistant", "content": "Temperature: 55°F, Condition: cloudy"}
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
| Output | Full message list + sub-agent messages | Raw LLM response text |

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

### Option B: Stdio Adapter (for headless CLI tools)

Best for **headless command-line agents** that have no GUI and can communicate purely via stdin/stdout. AgenticEval spawns the process and manages its lifecycle.

> **Not recommended for Electron/desktop apps** — use Option A (HTTP adapter) instead. Desktop apps have GUI initialization, stdout noise from Chromium/GPU logs, and lifecycle complexities that make stdio unreliable. See the "For Electron / Desktop Apps" section under Option A.

**What you need to implement:** A process that reads JSON from stdin and writes JSON to stdout (one JSON object per line). The process handles three message types: health check, run test (full e2e agent flow), and judge (direct LLM call).

**Protocol (newline-delimited JSON):**

Health check:
```
→ stdin:  {"type": "health_check"}\n
← stdout: {"type": "health_ok"}\n
```

Run a test — starts the agent's **complete e2e workflow**, treating the prompt as a real user message:
```
→ stdin:  {"type": "run_test", "id": "abc-123", "data": {"prompt": "What is 2+2?"}}\n
← stdout: {"messages": [...], "sub_agent_messages": [...], "metadata": {}}\n
```

- `messages` — **(required)** main agent's full conversation history
- `sub_agent_messages` — **(optional)** message lists from sub-agents that ran during the workflow
- Use the agent's own system prompt, tools, and full agent loop — identical to a real user interaction

Judge — forwards messages **directly to the LLM**, no agent system prompt, no e2e flow:
```
→ stdin:  {"type": "judge", "messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]}\n
← stdout: {"type": "judge_result", "content": "...the LLM response..."}\n
```

- Do NOT add the agent's system prompt — the eval system provides its own judge prompt
- Do NOT run the agent loop, tools, or any agent logic — just call the LLM and return the raw response

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
  "timeout_seconds": 3600
}
```

- `command` — **(required)** executable to run
- `args` — **(optional)** command-line arguments
- `cwd` — **(optional)** working directory
- `timeout_seconds` — **(optional)** max seconds to wait for a response (default: 3600)

#### Integration Prompt for Your Coding Agent

Copy the prompt below and paste it into your coding agent to generate the stdio eval handler for your project:

<details>
<summary><strong>Click to expand the Stdio integration prompt</strong></summary>

````
I need to add a stdin/stdout JSON Lines protocol handler to my project for integration
with AgenticEval, an external evaluation system that tests my AI agent.

My agent process should read JSON messages from stdin (one per line) and write
JSON responses to stdout (one per line).

## Message types to handle

### 1. Health check
Request:  {"type": "health_check"}
Response: {"type": "health_ok"}

Just return health_ok if the agent is ready.

### 2. Run test (full e2e agent flow)
Request:  {"type": "run_test", "id": "<uuid>", "data": {"prompt": "...", "metadata": {}}}
Response: {"messages": [...], "sub_agent_messages": [...], "metadata": {}}

This must:
1. Treat data.prompt as a REAL user message — as if a user typed it
2. Run my agent's COMPLETE standard workflow:
   - Use the agent's normal system prompt
   - Execute the full agent loop (tool calls, reasoning, memory, etc.)
   - Do NOT skip any steps — identical to a real user interaction
3. Collect ALL messages from the main agent conversation
4. If the agent delegates to sub-agents, collect their message lists in sub_agent_messages (optional)
5. Return the messages and sub_agent_messages as JSON

The messages array should include the full conversation history:
- {"role": "user", "content": "the prompt"}
- {"role": "assistant", "content": "agent's response"}
- {"role": "tool", "content": "tool results"} (if applicable)

### 3. Judge (direct LLM call)
Request:  {"type": "judge", "messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]}
Response: {"type": "judge_result", "content": "...the LLM response text..."}

This must:
1. Forward the messages DIRECTLY to my agent's LLM (same model, same API key)
2. Do NOT add my agent's system prompt — the eval system provides its own
3. Do NOT run the agent loop, tools, or any agent logic
4. Just call the LLM's chat completion and return the raw text

### 4. Error
If anything fails, return: {"type": "error", "message": "description of what went wrong"}

## Important distinctions

| Aspect | run_test | judge |
|--------|----------|-------|
| Purpose | Test the agent's real behavior | Score the agent's output |
| System prompt | USE agent's own system prompt | Do NOT add agent's system prompt |
| Agent loop | YES — full e2e workflow | NO — just a raw LLM call |
| Tools | YES — agent uses tools normally | NO — no tools, no agent logic |
| Input | data.prompt (user message string) | messages array (chat messages) |
| Output | Full message list + sub-agent messages | Raw LLM response text |

## Requirements
- Read from stdin, write to stdout, one JSON object per line (newline-delimited)
- The process should stay alive between messages (long-running)
- Stderr can be used for logging (not parsed as protocol messages)
- Reuse the existing agent infrastructure (same LLM client, same tools, same config)
````

</details>

---

### Option C: Python Adapter (for in-process Python agents)

Best for Python agents (LangChain, custom agents, etc.) where you want zero network overhead.

**What you need to implement:** A Python class with an async `send_test` method (full e2e flow) and optionally `get_judge_llm` (direct LLM access for judging).

```python
# my_agents/eval_bridge.py
from dataclasses import dataclass, field
from typing import Any

@dataclass
class AgentResult:
    messages: list[dict[str, Any]]          # main agent conversation
    sub_agent_messages: list[dict[str, Any]] = field(default_factory=list)  # sub-agent conversations
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
        """Required: run full agent e2e flow, treat prompt as real user input.

        This must behave identically to a real user interaction:
        - Use the agent's own system prompt
        - Execute the full agent loop (tool calls, reasoning, memory, etc.)
        - Do NOT skip any steps
        """
        prompt = test_data["prompt"]
        # Run your agent's complete workflow — same as a real user interaction
        result = await my_agent.run_full_flow(user_message=prompt)
        return AgentResult(
            messages=result.main_messages,
            sub_agent_messages=result.sub_agent_messages,  # optional
        )

    async def get_judge_llm(self):
        """Optional: return an LLM client for judging.

        This is used for DIRECT LLM calls — no agent system prompt, no tools.
        The eval system sends its own judge prompt and expects a raw LLM response.
        """
        return MyLLMClient()


class MyLLMClient:
    """Implements the LLMClient protocol — just calls your LLM directly.

    Do NOT add agent system prompts. Do NOT run agent logic.
    Just forward messages to the LLM and return the response.
    """
    async def chat(self, messages: list[dict[str, str]]) -> str:
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

#### Integration Prompt for Your Coding Agent

Copy the prompt below and paste it into your coding agent to generate the Python eval bridge class for your project:

<details>
<summary><strong>Click to expand the Python integration prompt</strong></summary>

````
I need to create a Python eval bridge class for integration with AgenticEval,
an external evaluation system that tests my AI agent. AgenticEval will import
this class and call it directly (in-process, no HTTP).

## What to implement

Create a bridge class with these methods:

### 1. send_test(test_data: dict) -> AgentResult (REQUIRED)
This is the core eval method. It should:
1. Read test_data["prompt"] as a user message
2. Run my agent's COMPLETE standard workflow:
   - Use the agent's normal system prompt
   - Execute the full agent loop (tool calls, reasoning, memory, etc.)
   - Do NOT skip any steps — identical to a real user interaction
3. Collect ALL messages from the main agent conversation
4. If the agent delegates to sub-agents, collect their message lists too
5. Return an AgentResult with messages, sub_agent_messages, and success status

### 2. get_judge_llm() -> LLMClient (OPTIONAL but recommended)
Return an object with an async chat(messages) -> str method that:
1. Forwards messages DIRECTLY to my agent's LLM (same model, same API key)
2. Does NOT add my agent's system prompt — AgenticEval provides its own
3. Does NOT run the agent loop, tools, or any agent logic
4. Just calls the LLM's chat completion and returns the raw text

### 3. connect(config: dict), disconnect(), health_check() -> bool (OPTIONAL)
Lifecycle methods for setup/teardown.

## The class structure

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass
class AgentResult:
    messages: list[dict[str, Any]]          # main agent conversation
    sub_agent_messages: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: str | None = None

class MyEvalBridge:
    async def connect(self, config: dict) -> None:
        # Initialize your agent here
        pass

    async def disconnect(self) -> None:
        # Cleanup
        pass

    async def health_check(self) -> bool:
        return True

    async def send_test(self, test_data: dict) -> AgentResult:
        prompt = test_data["prompt"]
        # TODO: Run your agent's full e2e flow with this prompt
        # Return AgentResult with all messages
        pass

    async def get_judge_llm(self):
        # TODO: Return an LLMClient that calls your LLM directly
        # (no agent system prompt, no tools — just raw LLM call)
        pass
```

## Important distinctions

| Aspect | send_test | get_judge_llm().chat() |
|--------|-----------|----------------------|
| Purpose | Test the agent's real behavior | Score the agent's output |
| System prompt | USE agent's own system prompt | Do NOT add agent's system prompt |
| Agent loop | YES — full e2e workflow | NO — just a raw LLM call |
| Tools | YES — agent uses tools normally | NO — no tools, no agent logic |
| Input | test_data["prompt"] (user message) | messages array (chat messages) |
| Output | AgentResult with full message list | Raw LLM response string |

## Requirements
- The class must be importable as a Python module (e.g., my_agents.eval_bridge.MyEvalBridge)
- All methods must be async
- send_test must produce identical behavior to a real user interaction
- get_judge_llm must return a minimal LLM proxy with no agent logic
- Reuse the existing agent infrastructure (same LLM client, same tools, same config)
````

</details>

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

A scorer defines how the judge LLM evaluates your agent's output. The `eval_prompt` is the single source of truth — it contains everything: what to evaluate, scoring criteria, score range, and scoring rules.

The judge LLM always returns:
```json
{"score": <number>, "justification": "<detailed explanation referencing the scoring criteria>"}
```

The system computes `passed = score >= pass_threshold` (default threshold: 60).

### Example Scorer

```json
{
  "name": "Booking Flow Correctness",
  "eval_prompt": "Evaluate whether the agent completed the booking flow correctly.\n\nScoring criteria:\n- Found correct flight (30 points)\n- Called booking API with right params (40 points)\n- Confirmed booking to user (30 points)\n\nScore range: 0-100.\nReturn {\"score\": <0-100>, \"justification\": \"<explain which criteria were met/missed>\"}.",
  "pass_threshold": 60,
  "tags": ["e2e", "booking"]
}
```

### Via CLI

```bash
agenticeval scorers create \
  --name "answer-correctness" \
  --eval-prompt "Compare the agent's answer to the expected answer. Score 0-100: 100 if semantically correct, 0 if wrong. Return {\"score\": <0-100>, \"justification\": \"<explain>\"}." \
  --threshold 60
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

## Agent Skill

If you're an AI agent and want to autonomously run evaluations, load the bundled skill:

```
skill/
├── SKILL.md              # Full eval lifecycle guide (setup → run → iterate)
└── references/
    ├── api-reference.md  # API endpoint quick reference
    └── scorer-guide.md   # How to write effective scorer prompts
```

The skill covers:
1. **First-time setup** — creating datasets, scorers, and adapters
2. **Running evals** — triggering runs, viewing results, comparing runs
3. **Iterating** — analyzing judge reasoning, updating datasets/scorers, re-running

To use: read `skill/SKILL.md` and follow the three-phase workflow. Reference files are loaded on demand.

## Changelog

### 2026-03-27 — SSE streaming fix

**Bug:** The web dashboard showed no progress or results after starting an eval run. The run completed successfully in the backend, but the frontend never received the events.

**Root cause:** SSE event name mismatch between backend and frontend:
- Backend emitted: `run_started`, `case_started`, `case_completed`, `run_completed`
- Frontend listened for: `progress`, `result`, `complete`

Since no events matched, the frontend's 3-second fallback fired and called `POST /api/runs/{id}/start`, which returned `400` because the SSE stream had already started the run.

**Fix:**
- `frontend/src/api/runs.ts` — Updated `streamRun()` to listen for the correct event names (`run_started`, `case_started`, `case_completed`, `run_completed`)
- `frontend/src/pages/RunDetailPage.tsx` — Fixed the fallback timeout race condition (used a local `receivedEvents` flag instead of stale React state, increased timeout to 5s, added try/catch around fallback `startRun`)
