import json
import pytest
from unittest.mock import patch
from app.services.judge import assemble_judge_prompt, parse_judge_response, resolve_judge_llm, DefaultLLMClient

def test_assemble_judge_prompt():
    messages = assemble_judge_prompt(
        eval_prompt="Check if the agent answered correctly.\nScore 0-100.\nDeduct points for wrong answers.",
        expected_result={"answer": "4"},
        agent_messages=[{"role": "assistant", "content": "4"}],
    )
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert "Check if the agent answered" in messages[1]["content"]
    assert "score" in messages[1]["content"]
    assert "justification" in messages[1]["content"]

def test_parse_pass():
    r = parse_judge_response('{"score": 85, "justification": "Good response, met most criteria."}', None)
    assert r["passed"] is True  # 85 >= 60 (default threshold)
    assert r["score"] == 85
    assert "Good response" in r["justification"]

def test_parse_fail():
    r = parse_judge_response('{"score": 30, "justification": "Poor quality, missed key requirements."}', None)
    assert r["passed"] is False  # 30 < 60
    assert r["score"] == 30

def test_parse_custom_threshold():
    r = parse_judge_response('{"score": 75, "justification": "Acceptable but below threshold."}', 80.0)
    assert r["passed"] is False  # 75 < 80
    assert r["score"] == 75

def test_parse_custom_threshold_pass():
    r = parse_judge_response('{"score": 85, "justification": "Above threshold."}', 80.0)
    assert r["passed"] is True  # 85 >= 80
    assert r["score"] == 85

def test_parse_zero_score():
    r = parse_judge_response('{"score": 0, "justification": "Completely wrong."}', None)
    assert r["passed"] is False
    assert r["score"] == 0

def test_parse_perfect_score():
    r = parse_judge_response('{"score": 100, "justification": "Perfect."}', None)
    assert r["passed"] is True
    assert r["score"] == 100

def test_parse_code_fences():
    r = parse_judge_response('```json\n{"score": 90, "justification": "OK"}\n```', None)
    assert r["passed"] is True
    assert r["score"] == 90

def test_resolve_override():
    c = resolve_judge_llm({"override_model": "gpt-4", "override_api_key": "sk-test"})
    assert isinstance(c, DefaultLLMClient)
    assert c.model == "gpt-4"

def test_resolve_no_config():
    with patch("app.services.judge.settings") as mock_settings:
        mock_settings.judge_model = ""
        mock_settings.judge_api_key = ""
        with pytest.raises(ValueError, match="No judge LLM configured"):
            resolve_judge_llm({"use_target_llm": False})
