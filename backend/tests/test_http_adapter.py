import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.bridge.http_adapter import HTTPAdapter, HTTPJudgeLLMClient
from app.bridge.base import LLMClient

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

@pytest.mark.asyncio
async def test_http_adapter_get_judge_llm_returns_client():
    adapter = HTTPAdapter()
    await adapter.connect({"base_url": "http://localhost:9999"})
    judge = await adapter.get_judge_llm()
    assert judge is not None
    assert isinstance(judge, LLMClient)
    assert isinstance(judge, HTTPJudgeLLMClient)
    await adapter.disconnect()

@pytest.mark.asyncio
async def test_http_adapter_get_judge_llm_not_connected():
    adapter = HTTPAdapter()
    judge = await adapter.get_judge_llm()
    assert judge is None

@pytest.mark.asyncio
async def test_http_judge_llm_client_chat():
    adapter = HTTPAdapter()
    await adapter.connect({"base_url": "http://localhost:9999"})
    judge = await adapter.get_judge_llm()
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value={"content": '{"passed": true, "reasoning": "correct"}'})
    mock_response.raise_for_status = MagicMock()
    with patch.object(adapter, "_client") as mock_client:
        mock_client.post = AsyncMock(return_value=mock_response)
        # Re-create judge with the mocked client
        judge = HTTPJudgeLLMClient(mock_client, "/eval/judge")
        result = await judge.chat([
            {"role": "system", "content": "You are a judge."},
            {"role": "user", "content": "Evaluate this."},
        ])
        assert "passed" in result
        mock_client.post.assert_called_once_with(
            "/eval/judge",
            json={"messages": [
                {"role": "system", "content": "You are a judge."},
                {"role": "user", "content": "Evaluate this."},
            ]},
        )
    await adapter.disconnect()

@pytest.mark.asyncio
async def test_http_adapter_default_judge_endpoint():
    adapter = HTTPAdapter()
    await adapter.connect({"base_url": "http://localhost:9999"})
    assert adapter.endpoints.get("judge") == "/eval/judge"
    await adapter.disconnect()

@pytest.mark.asyncio
async def test_http_adapter_custom_judge_endpoint():
    adapter = HTTPAdapter()
    await adapter.connect({
        "base_url": "http://localhost:9999",
        "endpoints": {"judge": "/custom/judge"},
    })
    judge = await adapter.get_judge_llm()
    assert isinstance(judge, HTTPJudgeLLMClient)
    assert judge._endpoint == "/custom/judge"
    await adapter.disconnect()

@pytest.mark.asyncio
async def test_http_adapter_auth_token_bearer_prefix():
    adapter = HTTPAdapter()
    await adapter.connect({
        "base_url": "http://localhost:9999",
        "auth_token": "Bearer eyJtoken123",
    })
    assert adapter._client.headers["authorization"] == "Bearer eyJtoken123"
    await adapter.disconnect()

@pytest.mark.asyncio
async def test_http_adapter_auth_token_raw():
    adapter = HTTPAdapter()
    await adapter.connect({
        "base_url": "http://localhost:9999",
        "auth_token": "eyJtoken123",
    })
    assert adapter._client.headers["authorization"] == "Bearer eyJtoken123"
    await adapter.disconnect()

@pytest.mark.asyncio
async def test_http_adapter_no_auth_token():
    adapter = HTTPAdapter()
    await adapter.connect({"base_url": "http://localhost:9999"})
    assert "authorization" not in adapter._client.headers
    await adapter.disconnect()
