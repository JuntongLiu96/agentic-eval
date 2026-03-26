import pytest
from app.bridge.stdio_adapter import StdioAdapter, StdioJudgeLLMClient
from app.bridge.base import LLMClient

@pytest.mark.asyncio
async def test_stdio_adapter_type():
    adapter = StdioAdapter()
    assert adapter.adapter_type() == "stdio"

@pytest.mark.asyncio
async def test_stdio_adapter_connect():
    adapter = StdioAdapter()
    await adapter.connect({"command": "python", "args": ["-c", "pass"], "timeout_seconds": 30})
    assert adapter.command == "python"
    assert adapter.timeout_seconds == 30

@pytest.mark.asyncio
async def test_stdio_adapter_default_timeout():
    adapter = StdioAdapter()
    await adapter.connect({"command": "python", "args": []})
    assert adapter.timeout_seconds == 300

@pytest.mark.asyncio
async def test_stdio_adapter_get_judge_llm():
    adapter = StdioAdapter()
    await adapter.connect({"command": "python", "args": []})
    judge = await adapter.get_judge_llm()
    assert judge is not None
    assert isinstance(judge, LLMClient)
    assert isinstance(judge, StdioJudgeLLMClient)
