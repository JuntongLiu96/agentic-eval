import pytest
from unittest.mock import AsyncMock
from app.bridge.base import AgentResult, BridgeAdapter


def test_agent_result_defaults():
    result = AgentResult(messages=[{"role": "assistant", "content": "hello"}])
    assert result.success is True
    assert result.error is None
    assert result.metadata == {}

def test_agent_result_with_error():
    result = AgentResult(messages=[], success=False, error="Timeout")
    assert result.success is False

def test_bridge_adapter_is_abstract():
    with pytest.raises(TypeError):
        BridgeAdapter()


class ConcreteBridge(BridgeAdapter):
    async def connect(self, config): pass
    async def disconnect(self): pass
    async def health_check(self): return True
    async def send_test(self, test_data, session_id=None): return AgentResult(messages=[])
    def adapter_type(self): return "test"
    def target_description(self): return "test"


@pytest.mark.asyncio
async def test_send_test_accepts_session_id():
    adapter = ConcreteBridge()
    result = await adapter.send_test({"prompt": "hi"}, session_id="abc123")
    assert result.success is True


@pytest.mark.asyncio
async def test_send_test_session_id_defaults_to_none():
    adapter = ConcreteBridge()
    result = await adapter.send_test({"prompt": "hi"})
    assert result.success is True
