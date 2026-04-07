"""Tests for the OpenClaw Bridge Adapter."""
import os
import pytest
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

from app.bridge.openclaw_adapter import OpenClawAdapter, OpenClawJudgeLLMClient
from app.bridge.base import LLMClient
from app.bridge.registry import ADAPTER_TYPES, create_adapter


# ---------------------------------------------------------------------------
# Basic adapter properties
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_openclaw_adapter_type():
    adapter = OpenClawAdapter()
    assert adapter.adapter_type() == "openclaw"


@pytest.mark.asyncio
async def test_openclaw_adapter_connect():
    adapter = OpenClawAdapter()
    await adapter.connect({
        "gateway_url": "ws://127.0.0.1:18789",
        "auth_token": "test-token",
        "agent_id": "mew",
        "timeout_seconds": 60,
    })
    assert adapter.gateway_url == "ws://127.0.0.1:18789"
    assert adapter.auth_token == "test-token"
    assert adapter.agent_id == "mew"
    assert adapter.timeout_seconds == 60
    assert adapter.session_key.startswith("agent:mew:eval-")


@pytest.mark.asyncio
async def test_openclaw_adapter_connect_defaults():
    adapter = OpenClawAdapter()
    await adapter.connect({})
    assert adapter.gateway_url == "ws://127.0.0.1:18789"
    assert adapter.agent_id == "mew"
    assert adapter.timeout_seconds == 3600
    assert adapter.llm_base_url == "http://localhost:4140"
    assert adapter.judge_model == "claude-sonnet-4.6"


@pytest.mark.asyncio
async def test_openclaw_adapter_connect_custom_session_key():
    adapter = OpenClawAdapter()
    await adapter.connect({
        "session_key": "agent:mew:custom-session",
    })
    assert adapter.session_key == "agent:mew:custom-session"


@pytest.mark.asyncio
async def test_openclaw_adapter_target_description():
    adapter = OpenClawAdapter()
    await adapter.connect({
        "gateway_url": "ws://127.0.0.1:18789",
        "agent_id": "mew",
    })
    desc = adapter.target_description()
    assert "mew" in desc
    assert "18789" in desc


@pytest.mark.asyncio
async def test_openclaw_adapter_custom_description():
    adapter = OpenClawAdapter()
    await adapter.connect({
        "description": "My custom OpenClaw agent",
    })
    assert adapter.target_description() == "My custom OpenClaw agent"


@pytest.mark.asyncio
async def test_openclaw_adapter_disconnect_no_process():
    """disconnect() should not raise when no process is running."""
    adapter = OpenClawAdapter()
    await adapter.connect({})
    await adapter.disconnect()  # Should be a no-op


@pytest.mark.asyncio
async def test_disconnect_does_not_close_llm_client():
    """disconnect() must leave _llm_client open for judge scoring."""
    adapter = OpenClawAdapter()
    await adapter.connect({})
    judge = await adapter.get_judge_llm()
    assert adapter._llm_client is not None
    assert not adapter._llm_client.is_closed
    await adapter.disconnect()
    # Client should still be usable
    assert adapter._llm_client is not None
    assert not adapter._llm_client.is_closed
    # Final cleanup
    await adapter.close()
    assert adapter._llm_client is None


@pytest.mark.asyncio
async def test_close_cleans_up_llm_client():
    """close() should fully tear down the httpx client."""
    adapter = OpenClawAdapter()
    await adapter.connect({})
    await adapter.get_judge_llm()
    assert adapter._llm_client is not None
    await adapter.close()
    assert adapter._llm_client is None


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def test_openclaw_in_registry():
    assert "openclaw" in ADAPTER_TYPES
    assert ADAPTER_TYPES["openclaw"] is OpenClawAdapter


def test_create_adapter_openclaw():
    adapter = create_adapter("openclaw")
    assert isinstance(adapter, OpenClawAdapter)
    assert adapter.adapter_type() == "openclaw"


# ---------------------------------------------------------------------------
# send_test — no prompt
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_test_no_prompt():
    adapter = OpenClawAdapter()
    await adapter.connect({})
    result = await adapter.send_test({})
    assert result.success is False
    assert "No prompt" in result.error


@pytest.mark.asyncio
async def test_send_test_empty_prompt():
    adapter = OpenClawAdapter()
    await adapter.connect({})
    result = await adapter.send_test({"prompt": ""})
    assert result.success is False
    assert "No prompt" in result.error


# ---------------------------------------------------------------------------
# Judge LLM
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_judge_llm_returns_client():
    adapter = OpenClawAdapter()
    await adapter.connect({"llm_base_url": "http://localhost:4140"})
    judge = await adapter.get_judge_llm()
    assert judge is not None
    assert isinstance(judge, LLMClient)
    assert isinstance(judge, OpenClawJudgeLLMClient)
    await adapter.close()


@pytest.mark.asyncio
async def test_judge_llm_chat():
    """Test that the judge LLM client calls the OpenAI-compatible endpoint."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": '{"passed": true}'}}]
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    judge = OpenClawJudgeLLMClient(mock_client, "claude-sonnet-4.6")
    result = await judge.chat([
        {"role": "system", "content": "You are a judge."},
        {"role": "user", "content": "Evaluate this."},
    ])
    assert "passed" in result
    mock_client.post.assert_called_once_with(
        "/chat/completions",
        json={
            "model": "claude-sonnet-4.6",
            "messages": [
                {"role": "system", "content": "You are a judge."},
                {"role": "user", "content": "Evaluate this."},
            ],
        },
    )


@pytest.mark.asyncio
async def test_judge_llm_custom_model():
    adapter = OpenClawAdapter()
    await adapter.connect({"judge_model": "gpt-5.4"})
    judge = await adapter.get_judge_llm()
    assert isinstance(judge, OpenClawJudgeLLMClient)
    assert judge._model == "gpt-5.4"
    await adapter.close()


# ---------------------------------------------------------------------------
# Skills loading
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_skills_dir_not_set():
    """When skills_dir is not set, no prefix is injected."""
    adapter = OpenClawAdapter()
    await adapter.connect({})
    assert adapter.skills_dir == ""
    assert adapter._skills_prefix == ""


@pytest.mark.asyncio
async def test_skills_dir_loads_skills():
    """When skills_dir points to a directory with SKILL.md files, they are loaded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a skill subdirectory
        skill_dir = os.path.join(tmpdir, "my-skill")
        os.makedirs(skill_dir)
        skill_md = os.path.join(skill_dir, "SKILL.md")
        with open(skill_md, "w") as f:
            f.write("---\nname: my-skill\ndescription: A test skill\n---\n\n# My Skill\nDo things.\n")

        adapter = OpenClawAdapter()
        await adapter.connect({"skills_dir": tmpdir})
        assert adapter.skills_dir == tmpdir
        assert "[Available Skills]" in adapter._skills_prefix
        assert "## Skill: my-skill" in adapter._skills_prefix
        assert "# My Skill" in adapter._skills_prefix
        assert "Do things." in adapter._skills_prefix
        assert "[End Available Skills]" in adapter._skills_prefix


@pytest.mark.asyncio
async def test_skills_dir_nonexistent():
    """A nonexistent skills_dir should produce an empty prefix."""
    adapter = OpenClawAdapter()
    await adapter.connect({"skills_dir": "/nonexistent/path"})
    assert adapter._skills_prefix == ""


@pytest.mark.asyncio
async def test_skills_dir_no_frontmatter():
    """SKILL.md without frontmatter uses directory name as skill name."""
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_dir = os.path.join(tmpdir, "bare-skill")
        os.makedirs(skill_dir)
        with open(os.path.join(skill_dir, "SKILL.md"), "w") as f:
            f.write("# Bare Skill\nJust content.\n")

        adapter = OpenClawAdapter()
        await adapter.connect({"skills_dir": tmpdir})
        assert "## Skill: bare-skill" in adapter._skills_prefix
        assert "Just content." in adapter._skills_prefix


# ---------------------------------------------------------------------------
# Import sanity
# ---------------------------------------------------------------------------

def test_import_no_errors():
    """Ensure the module imports cleanly."""
    from app.bridge import openclaw_adapter  # noqa: F401
    from app.bridge.openclaw_adapter import OpenClawAdapter  # noqa: F401
    from app.bridge.openclaw_adapter import OpenClawJudgeLLMClient  # noqa: F401
