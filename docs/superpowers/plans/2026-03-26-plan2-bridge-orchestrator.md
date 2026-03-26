# Plan 2: Bridge Layer + Orchestrator

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the bridge layer (adapter ABC + 3 adapter implementations + adapter registry) and the orchestrator (eval run models, judge service, eval loop, SSE progress, run API endpoints) — the eval execution engine.

**Architecture:** Bridge adapters implement a common ABC. The orchestrator loads a dataset, connects via an adapter, runs test cases sequentially, calls the LLM judge, stores results, and streams progress via SSE. All new code lives in `app/bridge/`, `app/services/`, `app/models/`, `app/schemas/`, and `app/api/`.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.0 (async), httpx (HTTP adapter + LLM calls), asyncio.subprocess (stdio adapter), sse-starlette (SSE streaming), pytest

**Spec:** `docs/superpowers/specs/2026-03-26-agentic-eval-system-design.md`

**Depends on:** Plan 1 (Foundation + Data Layer) — complete, 22 tests passing.

---

## File Structure (new files only)

```
backend/
├── app/
│   ├── bridge/
│   │   ├── __init__.py
│   │   ├── base.py              # BridgeAdapter ABC + AgentResult dataclass
│   │   ├── http_adapter.py      # HTTPAdapter implementation
│   │   ├── python_adapter.py    # PythonAdapter implementation
│   │   ├── stdio_adapter.py     # StdioAdapter implementation
│   │   └── registry.py          # Instantiate adapter from DB config
│   ├── services/
│   │   ├── __init__.py
│   │   ├── judge.py             # LLM judge: prompt assembly + API call
│   │   ├── orchestrator.py      # Core eval loop
│   │   └── aggregator.py        # Result aggregation (pass rate, averages)
│   ├── models/
│   │   ├── adapter.py           # Adapter SQLAlchemy model
│   │   ├── eval_run.py          # EvalRun SQLAlchemy model
│   │   └── eval_result.py       # EvalResult SQLAlchemy model
│   ├── schemas/
│   │   ├── adapter.py           # Adapter Pydantic schemas
│   │   ├── eval_run.py          # EvalRun Pydantic schemas
│   │   └── eval_result.py       # EvalResult Pydantic schemas
│   └── api/
│       ├── adapters.py          # Adapter CRUD + health check
│       └── runs.py              # EvalRun CRUD + start + stream + results + compare + export
└── tests/
    ├── test_bridge_base.py      # Bridge ABC + AgentResult tests
    ├── test_http_adapter.py     # HTTPAdapter tests (with mock server)
    ├── test_stdio_adapter.py    # StdioAdapter tests (with mock subprocess)
    ├── test_judge.py            # Judge service tests (prompt assembly + mock LLM)
    ├── test_orchestrator.py     # Orchestrator integration tests
    ├── test_adapters_api.py     # Adapter CRUD API tests
    └── test_runs_api.py         # EvalRun API tests
```

---

### Task 1: Bridge Layer — Base ABC + AgentResult

**Files:**
- Create: `backend/app/bridge/__init__.py`
- Create: `backend/app/bridge/base.py`
- Create: `backend/tests/test_bridge_base.py`

- [ ] **Step 1: Create `backend/app/bridge/__init__.py`**

Empty file.

- [ ] **Step 2: Create `backend/app/bridge/base.py`**

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class AgentResult:
    """Result returned by a bridge adapter after running a test case."""
    messages: list[dict[str, Any]]
    metadata: dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: str | None = None


@runtime_checkable
class LLMClient(Protocol):
    """Protocol for LLM clients used for judging."""
    async def chat(self, messages: list[dict[str, str]]) -> str: ...


class BridgeAdapter(ABC):
    """Contract that every target agent system must satisfy."""

    @abstractmethod
    async def connect(self, config: dict[str, Any]) -> None:
        """Initialize connection to the target agent system."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Clean up connection resources."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the target agent system is responsive."""
        ...

    @abstractmethod
    async def send_test(self, test_data: dict[str, Any]) -> AgentResult:
        """Send test data to the agent and return the result."""
        ...

    async def get_judge_llm(self) -> LLMClient | None:
        """Return an LLM client for judging, or None if not available."""
        return None

    @abstractmethod
    def adapter_type(self) -> str:
        """Return adapter type identifier: 'http', 'python', 'stdio'."""
        ...

    @abstractmethod
    def target_description(self) -> str:
        """Return a human-readable description of the target system."""
        ...
```

- [ ] **Step 3: Write tests for base classes**

Create `backend/tests/test_bridge_base.py`:

```python
import pytest
from app.bridge.base import AgentResult, BridgeAdapter


def test_agent_result_defaults():
    result = AgentResult(messages=[{"role": "assistant", "content": "hello"}])
    assert result.success is True
    assert result.error is None
    assert result.metadata == {}
    assert len(result.messages) == 1


def test_agent_result_with_error():
    result = AgentResult(messages=[], success=False, error="Connection timeout")
    assert result.success is False
    assert result.error == "Connection timeout"


def test_bridge_adapter_is_abstract():
    with pytest.raises(TypeError):
        BridgeAdapter()
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_bridge_base.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/bridge/ backend/tests/test_bridge_base.py
git commit -m "feat: add BridgeAdapter ABC and AgentResult dataclass"
```

---

### Task 2: HTTPAdapter Implementation

**Files:**
- Create: `backend/app/bridge/http_adapter.py`
- Create: `backend/tests/test_http_adapter.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_http_adapter.py`:

```python
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.bridge.http_adapter import HTTPAdapter


@pytest.mark.asyncio
async def test_http_adapter_connect():
    adapter = HTTPAdapter()
    config = {
        "base_url": "http://localhost:9999",
        "endpoints": {"send_test": "/eval/run", "health": "/eval/health"},
    }
    await adapter.connect(config)
    assert adapter.base_url == "http://localhost:9999"
    await adapter.disconnect()


@pytest.mark.asyncio
async def test_http_adapter_type():
    adapter = HTTPAdapter()
    assert adapter.adapter_type() == "http"


@pytest.mark.asyncio
async def test_http_adapter_health_check_success():
    adapter = HTTPAdapter()
    await adapter.connect({
        "base_url": "http://localhost:9999",
        "endpoints": {"send_test": "/eval/run", "health": "/eval/health"},
    })

    mock_response = AsyncMock()
    mock_response.status_code = 200

    with patch.object(adapter, "_client") as mock_client:
        mock_client.get = AsyncMock(return_value=mock_response)
        result = await adapter.health_check()
        assert result is True

    await adapter.disconnect()


@pytest.mark.asyncio
async def test_http_adapter_send_test():
    adapter = HTTPAdapter()
    await adapter.connect({
        "base_url": "http://localhost:9999",
        "endpoints": {"send_test": "/eval/run", "health": "/eval/health"},
    })

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value={
        "messages": [{"role": "assistant", "content": "answer"}],
        "metadata": {},
    })

    with patch.object(adapter, "_client") as mock_client:
        mock_client.post = AsyncMock(return_value=mock_response)
        result = await adapter.send_test({"prompt": "hello"})
        assert result.success is True
        assert len(result.messages) == 1
        assert result.messages[0]["content"] == "answer"

    await adapter.disconnect()


@pytest.mark.asyncio
async def test_http_adapter_send_test_failure():
    adapter = HTTPAdapter()
    await adapter.connect({
        "base_url": "http://localhost:9999",
        "endpoints": {"send_test": "/eval/run", "health": "/eval/health"},
    })

    mock_response = AsyncMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"

    with patch.object(adapter, "_client") as mock_client:
        mock_client.post = AsyncMock(return_value=mock_response)
        result = await adapter.send_test({"prompt": "hello"})
        assert result.success is False
        assert "500" in result.error

    await adapter.disconnect()
```

- [ ] **Step 2: Run tests — should fail**

Run: `cd backend && python -m pytest tests/test_http_adapter.py -v`

- [ ] **Step 3: Create `backend/app/bridge/http_adapter.py`**

```python
from typing import Any

import httpx

from app.bridge.base import AgentResult, BridgeAdapter


class HTTPAdapter(BridgeAdapter):
    """Bridge adapter for service-type agents that expose HTTP endpoints."""

    def __init__(self):
        self.base_url: str = ""
        self.endpoints: dict[str, str] = {}
        self._client: httpx.AsyncClient | None = None
        self._description: str = ""

    async def connect(self, config: dict[str, Any]) -> None:
        self.base_url = config["base_url"]
        self.endpoints = config.get("endpoints", {
            "send_test": "/eval/run",
            "health": "/eval/health",
        })
        self._description = config.get("description", f"HTTP agent at {self.base_url}")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=300.0)

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def health_check(self) -> bool:
        if not self._client:
            return False
        try:
            resp = await self._client.get(self.endpoints.get("health", "/eval/health"))
            return resp.status_code == 200
        except httpx.RequestError:
            return False

    async def send_test(self, test_data: dict[str, Any]) -> AgentResult:
        if not self._client:
            return AgentResult(messages=[], success=False, error="Not connected")
        try:
            resp = await self._client.post(
                self.endpoints.get("send_test", "/eval/run"),
                json=test_data,
            )
            if resp.status_code != 200:
                return AgentResult(
                    messages=[],
                    success=False,
                    error=f"HTTP {resp.status_code}: {resp.text[:500]}",
                )
            data = resp.json()
            return AgentResult(
                messages=data.get("messages", []),
                metadata=data.get("metadata", {}),
                success=True,
            )
        except httpx.RequestError as e:
            return AgentResult(messages=[], success=False, error=str(e))

    def adapter_type(self) -> str:
        return "http"

    def target_description(self) -> str:
        return self._description
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_http_adapter.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/bridge/http_adapter.py backend/tests/test_http_adapter.py
git commit -m "feat: implement HTTPAdapter for service-type agents"
```

---

### Task 3: StdioAdapter Implementation

**Files:**
- Create: `backend/app/bridge/stdio_adapter.py`
- Create: `backend/tests/test_stdio_adapter.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_stdio_adapter.py`:

```python
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.bridge.stdio_adapter import StdioAdapter


@pytest.mark.asyncio
async def test_stdio_adapter_type():
    adapter = StdioAdapter()
    assert adapter.adapter_type() == "stdio"


@pytest.mark.asyncio
async def test_stdio_adapter_connect():
    adapter = StdioAdapter()
    await adapter.connect({
        "command": "python",
        "args": ["-c", "pass"],
        "cwd": ".",
        "timeout_seconds": 30,
    })
    assert adapter.command == "python"
    assert adapter.timeout_seconds == 30


@pytest.mark.asyncio
async def test_stdio_adapter_default_timeout():
    adapter = StdioAdapter()
    await adapter.connect({"command": "python", "args": []})
    assert adapter.timeout_seconds == 300
```

- [ ] **Step 2: Run tests — should fail**

- [ ] **Step 3: Create `backend/app/bridge/stdio_adapter.py`**

```python
import asyncio
import json
import uuid
from typing import Any

from app.bridge.base import AgentResult, BridgeAdapter


class StdioAdapter(BridgeAdapter):
    """Bridge adapter for app-type agents communicating via stdin/stdout JSON Lines."""

    def __init__(self):
        self.command: str = ""
        self.args: list[str] = []
        self.cwd: str | None = None
        self.timeout_seconds: int = 300
        self._process: asyncio.subprocess.Process | None = None
        self._description: str = ""

    async def connect(self, config: dict[str, Any]) -> None:
        self.command = config["command"]
        self.args = config.get("args", [])
        self.cwd = config.get("cwd")
        self.timeout_seconds = config.get("timeout_seconds", 300)
        self._description = config.get(
            "description", f"Stdio agent: {self.command}"
        )

    async def _ensure_process(self) -> asyncio.subprocess.Process:
        if self._process is None or self._process.returncode is not None:
            self._process = await asyncio.create_subprocess_exec(
                self.command,
                *self.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.cwd,
            )
        return self._process

    async def disconnect(self) -> None:
        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._process.kill()
            self._process = None

    async def health_check(self) -> bool:
        try:
            process = await self._ensure_process()
            msg = json.dumps({"type": "health_check"}) + "\n"
            process.stdin.write(msg.encode())
            await process.stdin.drain()

            line = await asyncio.wait_for(
                process.stdout.readline(), timeout=10
            )
            if not line:
                return False
            data = json.loads(line.decode().strip())
            return data.get("type") == "health_ok"
        except (asyncio.TimeoutError, json.JSONDecodeError, OSError):
            return False

    async def send_test(self, test_data: dict[str, Any]) -> AgentResult:
        try:
            process = await self._ensure_process()
            request_id = str(uuid.uuid4())
            msg = json.dumps({
                "type": "run_test",
                "id": request_id,
                "data": test_data,
            }) + "\n"

            process.stdin.write(msg.encode())
            await process.stdin.drain()

            line = await asyncio.wait_for(
                process.stdout.readline(), timeout=self.timeout_seconds
            )

            if not line:
                return AgentResult(
                    messages=[],
                    success=False,
                    error="Subprocess closed stdout unexpectedly",
                )

            data = json.loads(line.decode().strip())

            if data.get("type") == "error":
                return AgentResult(
                    messages=[],
                    success=False,
                    error=data.get("message", "Unknown error from agent"),
                )

            return AgentResult(
                messages=data.get("messages", []),
                metadata=data.get("metadata", {}),
                success=True,
            )
        except asyncio.TimeoutError:
            await self.disconnect()
            return AgentResult(
                messages=[], success=False, error="Adapter timeout"
            )
        except json.JSONDecodeError as e:
            return AgentResult(
                messages=[], success=False, error=f"Invalid JSON from agent: {e}"
            )
        except OSError as e:
            return AgentResult(
                messages=[], success=False, error=f"Process error: {e}"
            )

    def adapter_type(self) -> str:
        return "stdio"

    def target_description(self) -> str:
        return self._description
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_stdio_adapter.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/bridge/stdio_adapter.py backend/tests/test_stdio_adapter.py
git commit -m "feat: implement StdioAdapter for app-type agents"
```

---

### Task 4: PythonAdapter + Bridge Registry

**Files:**
- Create: `backend/app/bridge/python_adapter.py`
- Create: `backend/app/bridge/registry.py`

- [ ] **Step 1: Create `backend/app/bridge/python_adapter.py`**

```python
import importlib
from typing import Any

from app.bridge.base import AgentResult, BridgeAdapter, LLMClient


class PythonAdapter(BridgeAdapter):
    """Bridge adapter for in-process Python agents."""

    def __init__(self):
        self._instance: Any = None
        self._module_path: str = ""
        self._class_name: str = ""
        self._description: str = ""

    async def connect(self, config: dict[str, Any]) -> None:
        self._module_path = config["module"]
        self._class_name = config["class"]
        self._description = config.get(
            "description", f"Python agent: {self._module_path}.{self._class_name}"
        )
        module = importlib.import_module(self._module_path)
        cls = getattr(module, self._class_name)
        self._instance = cls()
        if hasattr(self._instance, "connect"):
            await self._instance.connect(config)

    async def disconnect(self) -> None:
        if self._instance and hasattr(self._instance, "disconnect"):
            await self._instance.disconnect()
        self._instance = None

    async def health_check(self) -> bool:
        if not self._instance:
            return False
        if hasattr(self._instance, "health_check"):
            return await self._instance.health_check()
        return True

    async def send_test(self, test_data: dict[str, Any]) -> AgentResult:
        if not self._instance:
            return AgentResult(messages=[], success=False, error="Not connected")
        try:
            result = await self._instance.send_test(test_data)
            if isinstance(result, AgentResult):
                return result
            # Support dict return format
            return AgentResult(
                messages=result.get("messages", []),
                metadata=result.get("metadata", {}),
                success=result.get("success", True),
                error=result.get("error"),
            )
        except Exception as e:
            return AgentResult(messages=[], success=False, error=str(e))

    async def get_judge_llm(self) -> LLMClient | None:
        if self._instance and hasattr(self._instance, "get_judge_llm"):
            return await self._instance.get_judge_llm()
        return None

    def adapter_type(self) -> str:
        return "python"

    def target_description(self) -> str:
        return self._description
```

- [ ] **Step 2: Create `backend/app/bridge/registry.py`**

```python
from typing import Any

from app.bridge.base import BridgeAdapter
from app.bridge.http_adapter import HTTPAdapter
from app.bridge.python_adapter import PythonAdapter
from app.bridge.stdio_adapter import StdioAdapter

ADAPTER_TYPES: dict[str, type[BridgeAdapter]] = {
    "http": HTTPAdapter,
    "python": PythonAdapter,
    "stdio": StdioAdapter,
}


def create_adapter(adapter_type: str) -> BridgeAdapter:
    """Create a bridge adapter instance by type name."""
    cls = ADAPTER_TYPES.get(adapter_type)
    if cls is None:
        raise ValueError(
            f"Unknown adapter type: {adapter_type}. "
            f"Available: {list(ADAPTER_TYPES.keys())}"
        )
    return cls()
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/bridge/python_adapter.py backend/app/bridge/registry.py
git commit -m "feat: add PythonAdapter and bridge adapter registry"
```

---

### Task 5: Adapter Model, Schema, and CRUD API

**Files:**
- Create: `backend/app/models/adapter.py`
- Create: `backend/app/schemas/adapter.py`
- Create: `backend/app/api/adapters.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_adapters_api.py`

- [ ] **Step 1: Create `backend/app/models/adapter.py`**

```python
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Adapter(Base):
    __tablename__ = "adapters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    adapter_type: Mapped[str] = mapped_column(String(50), nullable=False)  # http, python, stdio
    config: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 2: Create `backend/app/schemas/adapter.py`**

```python
import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator


class AdapterCreate(BaseModel):
    name: str
    adapter_type: str  # http, python, stdio
    config: dict[str, Any]
    description: str = ""


class AdapterResponse(BaseModel):
    id: int
    name: str
    adapter_type: str
    config: dict[str, Any]
    description: str
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("config", mode="before")
    @classmethod
    def parse_config(cls, v: Any) -> Any:
        if isinstance(v, str):
            return json.loads(v)
        return v


class AdapterUpdate(BaseModel):
    name: str | None = None
    adapter_type: str | None = None
    config: dict[str, Any] | None = None
    description: str | None = None
```

- [ ] **Step 3: Write failing tests**

Create `backend/tests/test_adapters_api.py`:

```python
import pytest

HTTP_ADAPTER = {
    "name": "Test Service",
    "adapter_type": "http",
    "config": {
        "base_url": "http://localhost:9999",
        "endpoints": {"send_test": "/eval/run", "health": "/eval/health"},
    },
    "description": "Test HTTP agent",
}

STDIO_ADAPTER = {
    "name": "Test App",
    "adapter_type": "stdio",
    "config": {"command": "node", "args": ["eval-bridge.js"], "cwd": "/app"},
}


@pytest.mark.asyncio
async def test_create_adapter(client):
    response = await client.post("/api/adapters", json=HTTP_ADAPTER)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Service"
    assert data["adapter_type"] == "http"
    assert data["config"]["base_url"] == "http://localhost:9999"


@pytest.mark.asyncio
async def test_list_adapters(client):
    await client.post("/api/adapters", json=HTTP_ADAPTER)
    await client.post("/api/adapters", json=STDIO_ADAPTER)
    response = await client.get("/api/adapters")
    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_get_adapter(client):
    resp = await client.post("/api/adapters", json=HTTP_ADAPTER)
    adapter_id = resp.json()["id"]
    response = await client.get(f"/api/adapters/{adapter_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Test Service"


@pytest.mark.asyncio
async def test_get_adapter_not_found(client):
    response = await client.get("/api/adapters/999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_adapter(client):
    resp = await client.post("/api/adapters", json=HTTP_ADAPTER)
    adapter_id = resp.json()["id"]
    response = await client.put(
        f"/api/adapters/{adapter_id}", json={"name": "Updated"}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated"


@pytest.mark.asyncio
async def test_delete_adapter(client):
    resp = await client.post("/api/adapters", json=HTTP_ADAPTER)
    adapter_id = resp.json()["id"]
    response = await client.delete(f"/api/adapters/{adapter_id}")
    assert response.status_code == 204
    assert (await client.get(f"/api/adapters/{adapter_id}")).status_code == 404
```

- [ ] **Step 4: Create `backend/app/api/adapters.py`**

```python
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bridge.registry import create_adapter
from app.db.database import get_db
from app.models.adapter import Adapter
from app.schemas.adapter import AdapterCreate, AdapterResponse, AdapterUpdate

router = APIRouter(prefix="/api", tags=["adapters"])


@router.post("/adapters", response_model=AdapterResponse, status_code=201)
async def create_adapter_endpoint(
    payload: AdapterCreate, db: AsyncSession = Depends(get_db)
):
    adapter = Adapter(
        name=payload.name,
        adapter_type=payload.adapter_type,
        config=json.dumps(payload.config),
        description=payload.description,
    )
    db.add(adapter)
    await db.commit()
    await db.refresh(adapter)
    return adapter


@router.get("/adapters", response_model=list[AdapterResponse])
async def list_adapters(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Adapter).order_by(Adapter.created_at.desc()))
    return result.scalars().all()


@router.get("/adapters/{adapter_id}", response_model=AdapterResponse)
async def get_adapter(adapter_id: int, db: AsyncSession = Depends(get_db)):
    adapter = await db.get(Adapter, adapter_id)
    if not adapter:
        raise HTTPException(status_code=404, detail="Adapter not found")
    return adapter


@router.put("/adapters/{adapter_id}", response_model=AdapterResponse)
async def update_adapter(
    adapter_id: int, payload: AdapterUpdate, db: AsyncSession = Depends(get_db)
):
    adapter = await db.get(Adapter, adapter_id)
    if not adapter:
        raise HTTPException(status_code=404, detail="Adapter not found")
    if payload.name is not None:
        adapter.name = payload.name
    if payload.adapter_type is not None:
        adapter.adapter_type = payload.adapter_type
    if payload.config is not None:
        adapter.config = json.dumps(payload.config)
    if payload.description is not None:
        adapter.description = payload.description
    await db.commit()
    await db.refresh(adapter)
    return adapter


@router.delete("/adapters/{adapter_id}", status_code=204)
async def delete_adapter(adapter_id: int, db: AsyncSession = Depends(get_db)):
    adapter = await db.get(Adapter, adapter_id)
    if not adapter:
        raise HTTPException(status_code=404, detail="Adapter not found")
    await db.delete(adapter)
    await db.commit()


@router.post("/adapters/{adapter_id}/health")
async def health_check_adapter(adapter_id: int, db: AsyncSession = Depends(get_db)):
    adapter_row = await db.get(Adapter, adapter_id)
    if not adapter_row:
        raise HTTPException(status_code=404, detail="Adapter not found")
    try:
        bridge = create_adapter(adapter_row.adapter_type)
        config = json.loads(adapter_row.config)
        await bridge.connect(config)
        healthy = await bridge.health_check()
        await bridge.disconnect()
        return {"healthy": healthy}
    except Exception as e:
        return {"healthy": False, "error": str(e)}
```

- [ ] **Step 5: Update `backend/app/models/__init__.py`**

Add import for Adapter:

```python
from app.models.adapter import Adapter
```

Add `"Adapter"` to `__all__`.

- [ ] **Step 6: Register adapter router in `backend/app/main.py`**

Add import: `from app.api.adapters import router as adapters_router`
Add: `app.include_router(adapters_router)`

- [ ] **Step 7: Run tests**

Run: `cd backend && python -m pytest tests/test_adapters_api.py -v`
Expected: All 6 tests PASS.

- [ ] **Step 8: Run full suite**

Run: `cd backend && python -m pytest -v`
Expected: All tests PASS (22 existing + 3 bridge + 5 http + 3 stdio + 6 adapters = 39).

- [ ] **Step 9: Commit**

```bash
git add backend/app/models/adapter.py backend/app/schemas/adapter.py backend/app/api/adapters.py backend/app/models/__init__.py backend/app/main.py backend/tests/test_adapters_api.py
git commit -m "feat: implement Adapter model, CRUD API, and health check"
```

---

### Task 6: EvalRun + EvalResult Models and Schemas

**Files:**
- Create: `backend/app/models/eval_run.py`
- Create: `backend/app/models/eval_result.py`
- Create: `backend/app/schemas/eval_run.py`
- Create: `backend/app/schemas/eval_result.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create `backend/app/models/eval_run.py`**

```python
import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class RunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    dataset_id: Mapped[int] = mapped_column(Integer, ForeignKey("datasets.id"), nullable=False)
    scorer_id: Mapped[int] = mapped_column(Integer, ForeignKey("scorers.id"), nullable=False)
    adapter_id: Mapped[int] = mapped_column(Integer, ForeignKey("adapters.id"), nullable=False)
    judge_config: Mapped[str] = mapped_column(Text, default='{"use_target_llm": true}')  # JSON
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), default=RunStatus.pending)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    results: Mapped[list["EvalResult"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
```

- [ ] **Step 2: Create `backend/app/models/eval_result.py`**

```python
from sqlalchemy import Boolean, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class EvalResult(Base):
    __tablename__ = "eval_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("eval_runs.id"), nullable=False)
    test_case_id: Mapped[int] = mapped_column(Integer, ForeignKey("test_cases.id"), nullable=False)
    agent_messages: Mapped[str] = mapped_column(Text, default="[]")  # JSON
    score: Mapped[str] = mapped_column(Text, default="{}")  # JSON
    judge_reasoning: Mapped[str] = mapped_column(Text, default="")
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)

    run: Mapped["EvalRun"] = relationship(back_populates="results")
```

- [ ] **Step 3: Create `backend/app/schemas/eval_run.py`**

```python
import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator


class EvalRunCreate(BaseModel):
    name: str = ""
    dataset_id: int
    scorer_id: int
    adapter_id: int
    judge_config: dict[str, Any] = {"use_target_llm": True}


class EvalRunResponse(BaseModel):
    id: int
    name: str
    dataset_id: int
    scorer_id: int
    adapter_id: int
    judge_config: dict[str, Any]
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("judge_config", mode="before")
    @classmethod
    def parse_json(cls, v: Any) -> Any:
        if isinstance(v, str):
            return json.loads(v)
        return v
```

- [ ] **Step 4: Create `backend/app/schemas/eval_result.py`**

```python
import json
from typing import Any

from pydantic import BaseModel, field_validator


class EvalResultResponse(BaseModel):
    id: int
    run_id: int
    test_case_id: int
    agent_messages: list[dict[str, Any]]
    score: dict[str, Any]
    judge_reasoning: str
    passed: bool
    duration_ms: int

    model_config = {"from_attributes": True}

    @field_validator("agent_messages", mode="before")
    @classmethod
    def parse_messages(cls, v: Any) -> Any:
        if isinstance(v, str):
            return json.loads(v)
        return v

    @field_validator("score", mode="before")
    @classmethod
    def parse_score(cls, v: Any) -> Any:
        if isinstance(v, str):
            return json.loads(v)
        return v
```

- [ ] **Step 5: Update `backend/app/models/__init__.py`**

Add imports: `from app.models.eval_run import EvalRun` and `from app.models.eval_result import EvalResult`
Add both to `__all__`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/eval_run.py backend/app/models/eval_result.py backend/app/schemas/eval_run.py backend/app/schemas/eval_result.py backend/app/models/__init__.py
git commit -m "feat: add EvalRun and EvalResult models and schemas"
```

---

### Task 7: Judge Service

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/judge.py`
- Create: `backend/tests/test_judge.py`

- [ ] **Step 1: Create `backend/app/services/__init__.py`**

Empty file.

- [ ] **Step 2: Create `backend/app/services/judge.py`**

```python
import json
from typing import Any

import httpx

from app.bridge.base import LLMClient
from app.config import settings


SYSTEM_EVAL_PROMPT = """You are an expert evaluation judge. Your job is to evaluate an AI agent's output against expected results using the provided scoring criteria.

You MUST respond with valid JSON matching the requested output format. Do not include any text outside the JSON object.
"""


class DefaultLLMClient:
    """LLM client using httpx for OpenAI-compatible APIs."""

    def __init__(self, model: str, api_key: str, base_url: str = ""):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/") if base_url else "https://api.openai.com/v1"

    async def chat(self, messages: list[dict[str, str]]) -> str:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "messages": messages},
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]


def resolve_judge_llm(
    judge_config: dict[str, Any],
    adapter_llm: LLMClient | None = None,
) -> LLMClient:
    """Resolve which LLM to use for judging.

    Resolution order:
    1. Override model from judge_config
    2. Target agent's LLM (if use_target_llm=True and adapter provides one)
    3. System default from env vars
    4. Error
    """
    # 1. Explicit override
    override_model = judge_config.get("override_model")
    if override_model:
        return DefaultLLMClient(
            model=override_model,
            api_key=judge_config.get("override_api_key", ""),
            base_url=judge_config.get("override_base_url", ""),
        )

    # 2. Target agent's LLM
    if judge_config.get("use_target_llm", True) and adapter_llm is not None:
        return adapter_llm

    # 3. System default
    if settings.judge_model and settings.judge_api_key:
        return DefaultLLMClient(
            model=settings.judge_model,
            api_key=settings.judge_api_key,
            base_url=settings.judge_base_url,
        )

    # 4. Error
    raise ValueError(
        "No judge LLM configured. Set JUDGE_MODEL/JUDGE_API_KEY env vars "
        "or configure an override in judge_config."
    )


def assemble_judge_prompt(
    scorer_eval_prompt: str,
    scorer_criteria: dict[str, Any],
    scorer_output_format: str,
    expected_result: Any,
    agent_messages: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Assemble the messages to send to the judge LLM."""
    user_content = f"""## Scoring Criteria
{scorer_eval_prompt}

## Criteria Details
{json.dumps(scorer_criteria, indent=2)}

## Expected Result
{json.dumps(expected_result, indent=2)}

## Agent Output (message list)
{json.dumps(agent_messages, indent=2)}

## Required Output Format: {scorer_output_format}
Respond with ONLY a valid JSON object matching the {scorer_output_format} format."""

    return [
        {"role": "system", "content": SYSTEM_EVAL_PROMPT},
        {"role": "user", "content": user_content},
    ]


def parse_judge_response(
    response_text: str,
    output_format: str,
    score_range: dict[str, Any],
    pass_threshold: float | None,
) -> dict[str, Any]:
    """Parse the judge LLM response into a structured result."""
    # Strip markdown code fences if present
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]  # remove opening fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    data = json.loads(text)

    if output_format == "binary":
        return {
            "score": data,
            "passed": data.get("passed", False),
            "reasoning": data.get("reasoning", ""),
        }

    elif output_format == "numeric":
        score_val = data.get("score", 0)
        threshold = pass_threshold
        if threshold is None:
            smin = score_range.get("min", 0)
            smax = score_range.get("max", 100)
            threshold = smin + (smax - smin) * 0.6
        return {
            "score": data,
            "passed": score_val >= threshold,
            "reasoning": data.get("reasoning", ""),
        }

    elif output_format == "rubric":
        overall = data.get("overall_score", 0)
        threshold = pass_threshold
        if threshold is None:
            smin = score_range.get("min", 1)
            smax = score_range.get("max", 5)
            threshold = smin + (smax - smin) * 0.6
        return {
            "score": data,
            "passed": overall >= threshold,
            "reasoning": data.get("reasoning", ""),
        }

    return {"score": data, "passed": False, "reasoning": "Unknown format"}
```

- [ ] **Step 3: Write tests**

Create `backend/tests/test_judge.py`:

```python
import json
import pytest
from app.services.judge import (
    assemble_judge_prompt,
    parse_judge_response,
    resolve_judge_llm,
    DefaultLLMClient,
)


def test_assemble_judge_prompt():
    messages = assemble_judge_prompt(
        scorer_eval_prompt="Check if the answer is correct.",
        scorer_criteria={"conditions": [{"name": "correct", "description": "Is correct"}]},
        scorer_output_format="binary",
        expected_result={"answer": "4"},
        agent_messages=[{"role": "assistant", "content": "The answer is 4"}],
    )
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "Check if the answer is correct" in messages[1]["content"]
    assert '"answer": "4"' in messages[1]["content"]


def test_parse_binary_response():
    result = parse_judge_response(
        '{"passed": true, "reasoning": "Correct answer"}',
        "binary", {}, None,
    )
    assert result["passed"] is True
    assert result["reasoning"] == "Correct answer"


def test_parse_numeric_response():
    result = parse_judge_response(
        '{"score": 85, "reasoning": "Good"}',
        "numeric", {"min": 0, "max": 100}, None,
    )
    assert result["passed"] is True  # 85 >= 60 (0.6 * 100)
    assert result["score"]["score"] == 85


def test_parse_numeric_response_fail():
    result = parse_judge_response(
        '{"score": 30, "reasoning": "Poor"}',
        "numeric", {"min": 0, "max": 100}, None,
    )
    assert result["passed"] is False


def test_parse_numeric_with_custom_threshold():
    result = parse_judge_response(
        '{"score": 75, "reasoning": "OK"}',
        "numeric", {"min": 0, "max": 100}, 80.0,
    )
    assert result["passed"] is False  # 75 < 80


def test_parse_rubric_response():
    result = parse_judge_response(
        json.dumps({
            "dimensions": [
                {"name": "correctness", "score": 4, "reasoning": "Good"},
                {"name": "completeness", "score": 5, "reasoning": "Complete"},
            ],
            "overall_score": 4.5,
            "reasoning": "Very good overall",
        }),
        "rubric", {"min": 1, "max": 5}, 3.0,
    )
    assert result["passed"] is True
    assert result["reasoning"] == "Very good overall"


def test_parse_response_with_code_fences():
    result = parse_judge_response(
        '```json\n{"passed": true, "reasoning": "OK"}\n```',
        "binary", {}, None,
    )
    assert result["passed"] is True


def test_resolve_judge_llm_override():
    client = resolve_judge_llm({
        "override_model": "gpt-4",
        "override_api_key": "sk-test",
    })
    assert isinstance(client, DefaultLLMClient)
    assert client.model == "gpt-4"


def test_resolve_judge_llm_no_config():
    with pytest.raises(ValueError, match="No judge LLM configured"):
        resolve_judge_llm({"use_target_llm": False})
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_judge.py -v`
Expected: All 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ backend/tests/test_judge.py
git commit -m "feat: implement judge service with prompt assembly and LLM resolution"
```

---

### Task 8: Aggregator Service

**Files:**
- Create: `backend/app/services/aggregator.py`

- [ ] **Step 1: Create `backend/app/services/aggregator.py`**

```python
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.eval_result import EvalResult


async def aggregate_run_results(
    run_id: int, db: AsyncSession
) -> dict[str, Any]:
    """Compute aggregate statistics for an eval run."""
    result = await db.execute(
        select(EvalResult).where(EvalResult.run_id == run_id)
    )
    results = result.scalars().all()

    if not results:
        return {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "pass_rate": 0.0,
            "avg_duration_ms": 0,
        }

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    avg_duration = sum(r.duration_ms for r in results) / total

    # Collect numeric scores if available
    scores = []
    for r in results:
        score_data = json.loads(r.score) if isinstance(r.score, str) else r.score
        if isinstance(score_data, dict):
            if "score" in score_data and isinstance(score_data["score"], (int, float)):
                scores.append(score_data["score"])
            elif "overall_score" in score_data:
                scores.append(score_data["overall_score"])

    summary: dict[str, Any] = {
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": round(passed / total * 100, 1),
        "avg_duration_ms": round(avg_duration),
    }

    if scores:
        summary["avg_score"] = round(sum(scores) / len(scores), 2)
        summary["min_score"] = min(scores)
        summary["max_score"] = max(scores)

    return summary
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/aggregator.py
git commit -m "feat: add result aggregator service"
```

---

### Task 9: Orchestrator Service

**Files:**
- Create: `backend/app/services/orchestrator.py`
- Create: `backend/tests/test_orchestrator.py`

- [ ] **Step 1: Create `backend/app/services/orchestrator.py`**

```python
import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bridge.base import BridgeAdapter
from app.bridge.registry import create_adapter
from app.models.adapter import Adapter
from app.models.dataset import TestCase
from app.models.eval_result import EvalResult
from app.models.eval_run import EvalRun, RunStatus
from app.models.scorer import Scorer
from app.services.aggregator import aggregate_run_results
from app.services.judge import (
    assemble_judge_prompt,
    parse_judge_response,
    resolve_judge_llm,
)


async def run_eval(
    run_id: int,
    db: AsyncSession,
) -> AsyncGenerator[dict[str, Any], None]:
    """Execute an eval run, yielding progress events."""

    # Load run config
    run = await db.get(EvalRun, run_id)
    if not run:
        yield {"type": "error", "message": "Run not found"}
        return

    scorer = await db.get(Scorer, run.scorer_id)
    if not scorer:
        yield {"type": "error", "message": "Scorer not found"}
        return

    adapter_row = await db.get(Adapter, run.adapter_id)
    if not adapter_row:
        yield {"type": "error", "message": "Adapter not found"}
        return

    # Load test cases
    result = await db.execute(
        select(TestCase).where(TestCase.dataset_id == run.dataset_id)
    )
    test_cases = result.scalars().all()

    if not test_cases:
        yield {"type": "error", "message": "Dataset has no test cases"}
        return

    # Parse configs
    judge_config = json.loads(run.judge_config) if isinstance(run.judge_config, str) else run.judge_config
    scorer_criteria = json.loads(scorer.criteria) if isinstance(scorer.criteria, str) else scorer.criteria
    score_range = json.loads(scorer.score_range) if isinstance(scorer.score_range, str) else scorer.score_range
    adapter_config = json.loads(adapter_row.config) if isinstance(adapter_row.config, str) else adapter_row.config

    # Initialize bridge adapter
    bridge = create_adapter(adapter_row.adapter_type)
    try:
        await bridge.connect(adapter_config)
    except Exception as e:
        run.status = RunStatus.failed
        await db.commit()
        yield {"type": "error", "message": f"Failed to connect adapter: {e}"}
        return

    # Resolve judge LLM
    try:
        adapter_llm = await bridge.get_judge_llm()
        judge_client = resolve_judge_llm(judge_config, adapter_llm)
    except ValueError as e:
        run.status = RunStatus.failed
        await db.commit()
        await bridge.disconnect()
        yield {"type": "error", "message": str(e)}
        return

    # Mark run as started
    run.status = RunStatus.running
    run.started_at = datetime.now(timezone.utc)
    await db.commit()

    yield {
        "type": "run_started",
        "run_id": run_id,
        "total_cases": len(test_cases),
    }

    # Run each test case
    for i, tc in enumerate(test_cases):
        yield {
            "type": "case_started",
            "case_index": i,
            "case_name": tc.name,
            "total_cases": len(test_cases),
        }

        start_time = time.monotonic()
        test_data = json.loads(tc.data) if isinstance(tc.data, str) else tc.data
        expected = json.loads(tc.expected_result) if isinstance(tc.expected_result, str) else tc.expected_result

        # Send to agent
        agent_result = await bridge.send_test(test_data)

        if not agent_result.success:
            eval_result = EvalResult(
                run_id=run_id,
                test_case_id=tc.id,
                agent_messages=json.dumps(agent_result.messages),
                score=json.dumps({}),
                judge_reasoning=f"Agent error: {agent_result.error}",
                passed=False,
                duration_ms=int((time.monotonic() - start_time) * 1000),
            )
            db.add(eval_result)
            await db.commit()
            yield {
                "type": "case_completed",
                "case_index": i,
                "case_name": tc.name,
                "passed": False,
                "error": agent_result.error,
            }
            continue

        # Judge the result
        try:
            judge_messages = assemble_judge_prompt(
                scorer_eval_prompt=scorer.eval_prompt,
                scorer_criteria=scorer_criteria,
                scorer_output_format=scorer.output_format,
                expected_result=expected,
                agent_messages=agent_result.messages,
            )

            judge_response = await judge_client.chat(judge_messages)

            parsed = parse_judge_response(
                judge_response,
                scorer.output_format,
                score_range,
                scorer.pass_threshold,
            )

            eval_result = EvalResult(
                run_id=run_id,
                test_case_id=tc.id,
                agent_messages=json.dumps(agent_result.messages),
                score=json.dumps(parsed["score"]),
                judge_reasoning=parsed["reasoning"],
                passed=parsed["passed"],
                duration_ms=int((time.monotonic() - start_time) * 1000),
            )
        except Exception as e:
            eval_result = EvalResult(
                run_id=run_id,
                test_case_id=tc.id,
                agent_messages=json.dumps(agent_result.messages),
                score=json.dumps({}),
                judge_reasoning=f"Judge error: {e}",
                passed=False,
                duration_ms=int((time.monotonic() - start_time) * 1000),
            )

        db.add(eval_result)
        await db.commit()

        yield {
            "type": "case_completed",
            "case_index": i,
            "case_name": tc.name,
            "passed": eval_result.passed,
            "reasoning": eval_result.judge_reasoning,
        }

    # Finalize
    await bridge.disconnect()
    run.status = RunStatus.completed
    run.finished_at = datetime.now(timezone.utc)
    await db.commit()

    summary = await aggregate_run_results(run_id, db)
    yield {"type": "run_completed", "run_id": run_id, "summary": summary}
```

- [ ] **Step 2: Write tests**

Create `backend/tests/test_orchestrator.py`:

```python
import json
import pytest
from unittest.mock import AsyncMock, patch

from app.bridge.base import AgentResult
from app.models.eval_run import RunStatus


@pytest.mark.asyncio
async def test_orchestrator_run(client, db_session):
    """Integration test: create dataset, scorer, adapter, run, verify results."""
    # Create dataset with test case
    ds = await client.post("/api/datasets", json={"name": "Test DS"})
    ds_id = ds.json()["id"]
    await client.post(f"/api/datasets/{ds_id}/testcases", json={
        "name": "TC1",
        "data": {"prompt": "What is 2+2?"},
        "expected_result": {"answer": "4"},
    })

    # Create scorer
    scorer = await client.post("/api/scorers", json={
        "name": "Test Scorer",
        "output_format": "binary",
        "eval_prompt": "Check if answer is correct",
        "criteria": {"conditions": [{"name": "correct", "description": "Is correct"}], "pass_rule": "all"},
    })
    scorer_id = scorer.json()["id"]

    # Create adapter
    adapter = await client.post("/api/adapters", json={
        "name": "Mock Adapter",
        "adapter_type": "http",
        "config": {"base_url": "http://fake:9999", "endpoints": {}},
    })
    adapter_id = adapter.json()["id"]

    # Create run
    run = await client.post("/api/runs", json={
        "dataset_id": ds_id,
        "scorer_id": scorer_id,
        "adapter_id": adapter_id,
        "judge_config": {"use_target_llm": False, "override_model": "test", "override_api_key": "sk-test"},
    })
    assert run.status_code == 201
    run_id = run.json()["id"]
    assert run.json()["status"] == "pending"

    # Mock the bridge adapter and judge
    mock_bridge = AsyncMock()
    mock_bridge.connect = AsyncMock()
    mock_bridge.disconnect = AsyncMock()
    mock_bridge.get_judge_llm = AsyncMock(return_value=None)
    mock_bridge.send_test = AsyncMock(return_value=AgentResult(
        messages=[{"role": "assistant", "content": "The answer is 4"}],
        success=True,
    ))

    mock_judge_client = AsyncMock()
    mock_judge_client.chat = AsyncMock(return_value='{"passed": true, "reasoning": "Correct"}')

    with patch("app.services.orchestrator.create_adapter", return_value=mock_bridge), \
         patch("app.services.orchestrator.resolve_judge_llm", return_value=mock_judge_client):

        # Start the run
        resp = await client.post(f"/api/runs/{run_id}/start")
        assert resp.status_code == 200

    # Check run completed
    run_resp = await client.get(f"/api/runs/{run_id}")
    assert run_resp.json()["status"] == "completed"

    # Check results
    results_resp = await client.get(f"/api/runs/{run_id}/results")
    results = results_resp.json()
    assert len(results) == 1
    assert results[0]["passed"] is True
```

- [ ] **Step 3: Run test — should fail (runs API not yet implemented)**

Run: `cd backend && python -m pytest tests/test_orchestrator.py -v`
Expected: FAIL — `/api/runs` endpoint doesn't exist.

- [ ] **Step 4: Commit test and orchestrator**

```bash
git add backend/app/services/orchestrator.py backend/tests/test_orchestrator.py
git commit -m "feat: implement orchestrator eval loop with progress streaming"
```

---

### Task 10: Runs API (CRUD + Start + Results + Compare + Export + SSE)

**Files:**
- Create: `backend/app/api/runs.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_runs_api.py`

- [ ] **Step 1: Add `sse-starlette` dependency**

Add to `backend/requirements.txt`: `sse-starlette>=2.0.0`
Add to `backend/pyproject.toml` dependencies: `"sse-starlette>=2.0.0",`
Run: `cd backend && pip install sse-starlette`

- [ ] **Step 2: Create `backend/app/api/runs.py`**

```python
import csv
import io
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.db.database import get_db, async_session
from app.models.eval_result import EvalResult
from app.models.eval_run import EvalRun, RunStatus
from app.schemas.eval_result import EvalResultResponse
from app.schemas.eval_run import EvalRunCreate, EvalRunResponse
from app.services.aggregator import aggregate_run_results
from app.services.orchestrator import run_eval

router = APIRouter(prefix="/api", tags=["runs"])


@router.post("/runs", response_model=EvalRunResponse, status_code=201)
async def create_run(payload: EvalRunCreate, db: AsyncSession = Depends(get_db)):
    run = EvalRun(
        name=payload.name,
        dataset_id=payload.dataset_id,
        scorer_id=payload.scorer_id,
        adapter_id=payload.adapter_id,
        judge_config=json.dumps(payload.judge_config),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


@router.get("/runs", response_model=list[EvalRunResponse])
async def list_runs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EvalRun).order_by(EvalRun.created_at.desc()))
    return result.scalars().all()


@router.get("/runs/compare")
async def compare_runs(
    run1: int, run2: int, db: AsyncSession = Depends(get_db)
):
    summary1 = await aggregate_run_results(run1, db)
    summary2 = await aggregate_run_results(run2, db)

    # Get per-case results for both runs
    r1 = await db.execute(select(EvalResult).where(EvalResult.run_id == run1))
    r2 = await db.execute(select(EvalResult).where(EvalResult.run_id == run2))
    results1 = {r.test_case_id: r for r in r1.scalars().all()}
    results2 = {r.test_case_id: r for r in r2.scalars().all()}

    # Find common test cases and compare
    common_ids = set(results1.keys()) & set(results2.keys())
    comparisons = []
    for tc_id in common_ids:
        r1_result = results1[tc_id]
        r2_result = results2[tc_id]
        comparisons.append({
            "test_case_id": tc_id,
            "run1_passed": r1_result.passed,
            "run2_passed": r2_result.passed,
            "changed": r1_result.passed != r2_result.passed,
        })

    return {
        "run1": {"id": run1, "summary": summary1},
        "run2": {"id": run2, "summary": summary2},
        "comparisons": comparisons,
    }


@router.get("/runs/{run_id}", response_model=EvalRunResponse)
async def get_run(run_id: int, db: AsyncSession = Depends(get_db)):
    run = await db.get(EvalRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/runs/{run_id}/start")
async def start_run(run_id: int, db: AsyncSession = Depends(get_db)):
    run = await db.get(EvalRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status != RunStatus.pending:
        raise HTTPException(status_code=400, detail=f"Run is {run.status}, not pending")

    # Run synchronously and collect events
    events = []
    async for event in run_eval(run_id, db):
        events.append(event)

    last_event = events[-1] if events else {}
    return {"status": "completed", "events": events, "summary": last_event.get("summary", {})}


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: int):
    """SSE endpoint for live progress during an eval run."""
    async def event_generator():
        async with async_session() as db:
            run = await db.get(EvalRun, run_id)
            if not run:
                yield {"event": "error", "data": json.dumps({"message": "Run not found"})}
                return
            if run.status != RunStatus.pending:
                yield {"event": "error", "data": json.dumps({"message": f"Run is {run.status}"})}
                return

            async for event in run_eval(run_id, db):
                yield {"event": event["type"], "data": json.dumps(event)}

    return EventSourceResponse(event_generator())


@router.get("/runs/{run_id}/results", response_model=list[EvalResultResponse])
async def get_run_results(run_id: int, db: AsyncSession = Depends(get_db)):
    run = await db.get(EvalRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    result = await db.execute(
        select(EvalResult).where(EvalResult.run_id == run_id)
    )
    return result.scalars().all()


@router.get("/runs/{run_id}/export")
async def export_run(run_id: int, db: AsyncSession = Depends(get_db)):
    run = await db.get(EvalRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    result = await db.execute(
        select(EvalResult).where(EvalResult.run_id == run_id)
    )
    results = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["test_case_id", "passed", "score", "judge_reasoning", "duration_ms"])
    for r in results:
        writer.writerow([r.test_case_id, r.passed, r.score, r.judge_reasoning, r.duration_ms])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=run_{run_id}_results.csv"},
    )
```

- [ ] **Step 3: Register runs router in `backend/app/main.py`**

Add import: `from app.api.runs import router as runs_router`
Add: `app.include_router(runs_router)`

- [ ] **Step 4: Write basic API tests**

Create `backend/tests/test_runs_api.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_create_run(client):
    ds = await client.post("/api/datasets", json={"name": "DS"})
    ds_id = ds.json()["id"]
    scorer = await client.post("/api/scorers", json={
        "name": "S", "output_format": "binary", "eval_prompt": "test",
        "criteria": {"conditions": [], "pass_rule": "all"},
    })
    scorer_id = scorer.json()["id"]
    adapter = await client.post("/api/adapters", json={
        "name": "A", "adapter_type": "http",
        "config": {"base_url": "http://fake:9999"},
    })
    adapter_id = adapter.json()["id"]

    run = await client.post("/api/runs", json={
        "dataset_id": ds_id, "scorer_id": scorer_id, "adapter_id": adapter_id,
    })
    assert run.status_code == 201
    assert run.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_list_runs(client):
    ds = await client.post("/api/datasets", json={"name": "DS"})
    scorer = await client.post("/api/scorers", json={
        "name": "S", "output_format": "binary", "eval_prompt": "test",
        "criteria": {"conditions": [], "pass_rule": "all"},
    })
    adapter = await client.post("/api/adapters", json={
        "name": "A", "adapter_type": "http",
        "config": {"base_url": "http://fake:9999"},
    })
    await client.post("/api/runs", json={
        "dataset_id": ds.json()["id"],
        "scorer_id": scorer.json()["id"],
        "adapter_id": adapter.json()["id"],
    })
    resp = await client.get("/api/runs")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_get_run_not_found(client):
    resp = await client.get("/api/runs/999")
    assert resp.status_code == 404
```

- [ ] **Step 5: Run all tests**

Run: `cd backend && python -m pytest -v`
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/runs.py backend/app/main.py backend/tests/test_runs_api.py backend/pyproject.toml backend/requirements.txt
git commit -m "feat: implement EvalRun API with start, stream, results, compare, and export"
```

---

### Task 11: Final Verification

- [ ] **Step 1: Run full test suite**

Run: `cd backend && python -m pytest -v --tb=short`
Expected: All tests PASS.

- [ ] **Step 2: Verify the server starts**

Run: `cd backend && timeout 5 python -m uvicorn app.main:app --port 8000 2>&1 || true`
Expected: Server starts with all routes registered.

- [ ] **Step 3: Check git log**

Run: `git log --oneline`
Verify clean commit history.

---

## Plan 2 Complete

After all tasks pass, the following is working:
- **Bridge Layer** — BridgeAdapter ABC, HTTPAdapter, StdioAdapter, PythonAdapter, adapter registry
- **Adapter CRUD API** — create, list, get, update, delete adapters + health check
- **EvalRun + EvalResult models** — full data model for eval runs
- **Judge Service** — prompt assembly, LLM resolution, response parsing for all 3 formats
- **Aggregator Service** — pass rate, average scores, score distribution
- **Orchestrator** — sequential eval loop with progress events
- **Runs API** — create, list, get, start, stream (SSE), results, compare, export

**Next:** Plan 3 (CLI) and Plan 4 (React Frontend Dashboard)
