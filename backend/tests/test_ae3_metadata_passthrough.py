"""AE-3: dataset_row.metadata flows from TestCase through bridge.send_test to the target agent.

Three adapter shapes are covered (http, stdio, python). The orchestrator-side
behaviour is covered by ``test_orchestrator_metadata_passthrough`` further down.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.bridge.base import AgentResult, BridgeAdapter
from app.bridge.http_adapter import HTTPAdapter
from app.bridge.python_adapter import PythonAdapter
from app.bridge.stdio_adapter import StdioAdapter


# ---------------------------------------------------------------------------
# ABC signature
# ---------------------------------------------------------------------------

def test_bridge_adapter_abc_send_test_accepts_metadata():
    """The ABC must declare ``metadata`` so type-checkers and adapters agree."""
    import inspect

    sig = inspect.signature(BridgeAdapter.send_test)
    assert "metadata" in sig.parameters
    # Default must be None so existing adapters/agents don't break.
    assert sig.parameters["metadata"].default is None


# ---------------------------------------------------------------------------
# HTTPAdapter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_http_adapter_forwards_metadata_in_payload():
    adapter = HTTPAdapter()
    await adapter.connect({"base_url": "http://localhost:9999", "endpoints": {}})
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value={"messages": [], "metadata": {}})
    with patch.object(adapter, "_client") as mock_client:
        mock_client.post = AsyncMock(return_value=mock_response)
        meta = {"case_id": "CA-001", "scope": {"org_id": "acme"}, "round_idx": 1}
        await adapter.send_test({"prompt": "go"}, session_id="sess-1", metadata=meta)
        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["prompt"] == "go"
        assert payload["session_id"] == "sess-1"
        assert payload["metadata"] == meta
    await adapter.disconnect()


@pytest.mark.asyncio
async def test_http_adapter_omits_metadata_field_when_none():
    """Backward-compat: no metadata field if caller didn't pass one."""
    adapter = HTTPAdapter()
    await adapter.connect({"base_url": "http://localhost:9999", "endpoints": {}})
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value={"messages": [], "metadata": {}})
    with patch.object(adapter, "_client") as mock_client:
        mock_client.post = AsyncMock(return_value=mock_response)
        await adapter.send_test({"prompt": "go"})
        payload = mock_client.post.call_args.kwargs["json"]
        assert "metadata" not in payload
    await adapter.disconnect()


# ---------------------------------------------------------------------------
# StdioAdapter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stdio_adapter_forwards_metadata_in_jsonl_message():
    adapter = StdioAdapter()
    await adapter.connect({"command": "python", "args": ["-c", "pass"]})

    fake_proc = MagicMock()
    fake_proc.stdin = MagicMock()
    fake_proc.stdin.write = MagicMock()
    fake_proc.stdin.drain = AsyncMock()
    fake_proc.stdout = MagicMock()
    fake_proc.returncode = None

    with patch.object(adapter, "_ensure_process", AsyncMock(return_value=fake_proc)), \
         patch.object(adapter, "_read_json_line", AsyncMock(return_value={
             "type": "run_response", "messages": [], "metadata": {},
         })):
        meta = {"case_id": "CA-002", "scope": {"org_id": "acme", "repo_id": "x"}}
        await adapter.send_test({"prompt": "go"}, session_id="sess-7", metadata=meta)
        written_bytes = fake_proc.stdin.write.call_args.args[0]
        line = written_bytes.decode().strip()
        msg = json.loads(line)
        assert msg["type"] == "run_test"
        assert msg["data"] == {"prompt": "go"}
        assert msg["session_id"] == "sess-7"
        assert msg["metadata"] == meta


# ---------------------------------------------------------------------------
# PythonAdapter
# ---------------------------------------------------------------------------

class _MetadataAwareAgent:
    """In-process agent that opts into the AE-3 metadata kwarg."""

    captured: dict | None = None

    async def send_test(self, test_data, session_id=None, metadata=None):
        type(self).captured = metadata
        return AgentResult(messages=[{"role": "assistant", "content": "ok"}])


class _LegacyAgent:
    """In-process agent on the pre-AE-3 contract (no metadata kwarg)."""

    captured_called: bool = False

    async def send_test(self, test_data, session_id=None):
        type(self).captured_called = True
        return AgentResult(messages=[{"role": "assistant", "content": "ok"}])


@pytest.mark.asyncio
async def test_python_adapter_forwards_metadata_when_agent_accepts_it():
    _MetadataAwareAgent.captured = None
    adapter = PythonAdapter()
    adapter._instance = _MetadataAwareAgent()
    meta = {"case_id": "CA-001"}
    result = await adapter.send_test({"prompt": "hi"}, metadata=meta)
    assert result.success
    assert _MetadataAwareAgent.captured == meta


@pytest.mark.asyncio
async def test_python_adapter_legacy_agent_without_metadata_still_works():
    _LegacyAgent.captured_called = False
    adapter = PythonAdapter()
    adapter._instance = _LegacyAgent()
    # Passing metadata must not crash even though the inner agent doesn't accept it.
    result = await adapter.send_test({"prompt": "hi"}, metadata={"case_id": "X"})
    assert result.success
    assert _LegacyAgent.captured_called


# ---------------------------------------------------------------------------
# Orchestrator: TestCase.metadata flows through to bridge.send_test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_orchestrator_metadata_passthrough_helper():
    """The helper that parses TestCase.metadata_ handles all the on-disk shapes."""
    from app.services.orchestrator import _parse_case_metadata

    class _TC:
        def __init__(self, raw):
            self.metadata_ = raw

    assert _parse_case_metadata(_TC(None)) == {}
    assert _parse_case_metadata(_TC("")) == {}
    assert _parse_case_metadata(_TC("not json")) == {}
    assert _parse_case_metadata(_TC('{"case_id": "CA-001"}')) == {"case_id": "CA-001"}
    assert _parse_case_metadata(_TC({"case_id": "CA-001"})) == {"case_id": "CA-001"}
    # Must return a fresh dict each time so callers can mutate safely.
    src = {"case_id": "x"}
    out = _parse_case_metadata(_TC(src))
    out["mutated"] = True
    assert "mutated" not in src
