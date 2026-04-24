import pytest
from app.services.turns import parse_turns


def test_parse_turns_single_prompt():
    """Single-turn shorthand wraps to one turn."""
    data = {"prompt": "hello"}
    turns = parse_turns(data)
    assert turns == [{"prompt": "hello"}]


def test_parse_turns_explicit_turns():
    """Multi-turn data passes through."""
    data = {"turns": [
        {"prompt": "msg1"},
        {"prompt": "msg2", "expected_result": {"criteria": "check"}},
    ]}
    turns = parse_turns(data)
    assert len(turns) == 2
    assert turns[0] == {"prompt": "msg1"}
    assert turns[1]["expected_result"] == {"criteria": "check"}


def test_parse_turns_both_raises():
    """Having both prompt and turns is invalid."""
    data = {"prompt": "hello", "turns": [{"prompt": "hello"}]}
    with pytest.raises(ValueError, match="Cannot have both"):
        parse_turns(data)


def test_parse_turns_neither_raises():
    """Having neither prompt nor turns is invalid."""
    data = {"something_else": "value"}
    with pytest.raises(ValueError, match="must have either"):
        parse_turns(data)


def test_parse_turns_empty_turns_raises():
    """Empty turns array is invalid."""
    data = {"turns": []}
    with pytest.raises(ValueError, match="must not be empty"):
        parse_turns(data)


def test_parse_turns_missing_prompt_in_turn_raises():
    """Each turn must have a prompt."""
    data = {"turns": [{"expected_result": {"criteria": "check"}}]}
    with pytest.raises(ValueError, match="prompt"):
        parse_turns(data)
