import pytest
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
