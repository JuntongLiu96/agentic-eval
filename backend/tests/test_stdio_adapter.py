import pytest
from app.bridge.stdio_adapter import StdioAdapter

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
