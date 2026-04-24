import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.bridge.base import AgentResult
from app.services.turns import parse_turns


@pytest.mark.asyncio
async def test_single_turn_backward_compat():
    """Single-turn data produces one send_test call with no session_id."""
    bridge = AsyncMock()
    bridge.send_test = AsyncMock(return_value=AgentResult(
        messages=[{"role": "assistant", "content": "hi"}],
        metadata={},
        success=True,
    ))

    data = {"prompt": "hello"}
    turns = parse_turns(data)
    assert len(turns) == 1

    session_id = None
    all_messages = []
    for turn in turns:
        result = await bridge.send_test({"prompt": turn["prompt"]}, session_id=session_id)
        if session_id is None and result.metadata.get("session_id"):
            session_id = result.metadata["session_id"]
        all_messages.extend(result.messages)

    bridge.send_test.assert_called_once_with({"prompt": "hello"}, session_id=None)
    assert len(all_messages) == 1


@pytest.mark.asyncio
async def test_multi_turn_sends_session_id():
    """Multi-turn data sends session_id on subsequent turns."""
    bridge = AsyncMock()
    bridge.send_test = AsyncMock(side_effect=[
        AgentResult(
            messages=[{"role": "assistant", "content": "meeting created"}],
            metadata={"session_id": "sess-001"},
            success=True,
        ),
        AgentResult(
            messages=[{"role": "assistant", "content": "time changed"}],
            metadata={"session_id": "sess-001"},
            success=True,
        ),
    ])

    data = {"turns": [
        {"prompt": "Create a meeting"},
        {"prompt": "Change it to 4pm"},
    ]}
    turns = parse_turns(data)

    session_id = None
    all_messages = []
    for turn in turns:
        result = await bridge.send_test({"prompt": turn["prompt"]}, session_id=session_id)
        if session_id is None and result.metadata.get("session_id"):
            session_id = result.metadata["session_id"]
        all_messages.extend(result.messages)

    assert bridge.send_test.call_count == 2
    first_call = bridge.send_test.call_args_list[0]
    assert first_call[1]["session_id"] is None
    second_call = bridge.send_test.call_args_list[1]
    assert second_call[1]["session_id"] == "sess-001"
    assert len(all_messages) == 2


@pytest.mark.asyncio
async def test_multi_turn_fails_on_error():
    """If a turn fails, subsequent turns are not executed."""
    bridge = AsyncMock()
    bridge.send_test = AsyncMock(side_effect=[
        AgentResult(messages=[], success=False, error="Agent crashed"),
    ])

    data = {"turns": [
        {"prompt": "msg1"},
        {"prompt": "msg2"},
    ]}
    turns = parse_turns(data)

    session_id = None
    failed = False
    for turn in turns:
        result = await bridge.send_test({"prompt": turn["prompt"]}, session_id=session_id)
        if not result.success:
            failed = True
            break
        if session_id is None and result.metadata.get("session_id"):
            session_id = result.metadata["session_id"]

    assert failed
    assert bridge.send_test.call_count == 1
