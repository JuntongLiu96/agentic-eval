import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.bridge.http_adapter import HTTPAdapter

@pytest.mark.asyncio
async def test_http_adapter_connect():
    adapter = HTTPAdapter()
    await adapter.connect({"base_url": "http://localhost:9999", "endpoints": {}})
    assert adapter.base_url == "http://localhost:9999"
    await adapter.disconnect()

@pytest.mark.asyncio
async def test_http_adapter_type():
    adapter = HTTPAdapter()
    assert adapter.adapter_type() == "http"

@pytest.mark.asyncio
async def test_http_adapter_send_test():
    adapter = HTTPAdapter()
    await adapter.connect({"base_url": "http://localhost:9999", "endpoints": {}})
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value={"messages": [{"role": "assistant", "content": "4"}], "metadata": {}})
    with patch.object(adapter, "_client") as mock_client:
        mock_client.post = AsyncMock(return_value=mock_response)
        result = await adapter.send_test({"prompt": "2+2"})
        assert result.success is True
        assert result.messages[0]["content"] == "4"
    await adapter.disconnect()

@pytest.mark.asyncio
async def test_http_adapter_send_test_failure():
    adapter = HTTPAdapter()
    await adapter.connect({"base_url": "http://localhost:9999", "endpoints": {}})
    mock_response = AsyncMock()
    mock_response.status_code = 500
    mock_response.text = "Error"
    with patch.object(adapter, "_client") as mock_client:
        mock_client.post = AsyncMock(return_value=mock_response)
        result = await adapter.send_test({"prompt": "hello"})
        assert result.success is False
        assert "500" in result.error
    await adapter.disconnect()

@pytest.mark.asyncio
async def test_http_adapter_health():
    adapter = HTTPAdapter()
    await adapter.connect({"base_url": "http://localhost:9999", "endpoints": {}})
    mock_response = AsyncMock()
    mock_response.status_code = 200
    with patch.object(adapter, "_client") as mock_client:
        mock_client.get = AsyncMock(return_value=mock_response)
        assert await adapter.health_check() is True
    await adapter.disconnect()
