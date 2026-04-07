import pytest
from app.bridge.python_adapter import PythonAdapter
from app.bridge.registry import create_adapter, ADAPTER_TYPES
from app.bridge.http_adapter import HTTPAdapter
from app.bridge.stdio_adapter import StdioAdapter


# --- PythonAdapter tests ---

@pytest.mark.asyncio
async def test_python_adapter_type():
    adapter = PythonAdapter()
    assert adapter.adapter_type() == "python"

@pytest.mark.asyncio
async def test_python_adapter_not_connected():
    adapter = PythonAdapter()
    result = await adapter.send_test({"prompt": "hello"})
    assert result.success is False
    assert result.error == "Not connected"

@pytest.mark.asyncio
async def test_python_adapter_health_not_connected():
    adapter = PythonAdapter()
    assert await adapter.health_check() is False


# --- Registry tests ---

def test_registry_has_all_types():
    assert set(ADAPTER_TYPES.keys()) == {"http", "python", "stdio", "openclaw"}

def test_create_adapter_http():
    adapter = create_adapter("http")
    assert isinstance(adapter, HTTPAdapter)

def test_create_adapter_python():
    adapter = create_adapter("python")
    assert isinstance(adapter, PythonAdapter)

def test_create_adapter_stdio():
    adapter = create_adapter("stdio")
    assert isinstance(adapter, StdioAdapter)

def test_create_adapter_unknown():
    with pytest.raises(ValueError, match="Unknown adapter type"):
        create_adapter("grpc")
