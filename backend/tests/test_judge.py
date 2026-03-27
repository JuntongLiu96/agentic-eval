import json
import pytest
from unittest.mock import patch
from app.services.judge import assemble_judge_prompt, parse_judge_response, resolve_judge_llm, DefaultLLMClient

def test_assemble_judge_prompt():
    messages = assemble_judge_prompt(
        scorer_eval_prompt="Check correctness.",
        scorer_criteria={"conditions": [{"name": "correct", "description": "Is correct"}]},
        scorer_output_format="binary",
        expected_result={"answer": "4"},
        agent_messages=[{"role": "assistant", "content": "4"}],
    )
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert "Check correctness" in messages[1]["content"]
    assert "score" in messages[1]["content"]
    assert "justification" in messages[1]["content"]

def test_parse_binary_pass():
    r = parse_judge_response('{"score": 1, "justification": "The agent answered correctly."}', "binary", {}, None)
    assert r["passed"] is True
    assert r["justification"] == "The agent answered correctly."

def test_parse_binary_fail():
    r = parse_judge_response('{"score": 0, "justification": "The agent gave a wrong answer."}', "binary", {}, None)
    assert r["passed"] is False

def test_parse_numeric_pass():
    r = parse_judge_response('{"score": 85, "justification": "Good response, met most criteria."}', "numeric", {"min": 0, "max": 100}, None)
    assert r["passed"] is True  # 85 >= 60
    assert "Good response" in r["justification"]

def test_parse_numeric_fail():
    r = parse_judge_response('{"score": 30, "justification": "Poor quality, missed key requirements."}', "numeric", {"min": 0, "max": 100}, None)
    assert r["passed"] is False

def test_parse_numeric_custom_threshold():
    r = parse_judge_response('{"score": 75, "justification": "Acceptable but below threshold."}', "numeric", {"min": 0, "max": 100}, 80.0)
    assert r["passed"] is False  # 75 < 80

def test_parse_rubric():
    r = parse_judge_response(json.dumps({
        "dimensions": [{"name": "correctness", "score": 4, "justification": "Mostly correct"}],
        "overall_score": 4.5, "score": 4.5,
        "justification": "Very good overall, strong on correctness.",
    }), "rubric", {"min": 1, "max": 5}, 3.0)
    assert r["passed"] is True
    assert "Very good" in r["justification"]

def test_parse_code_fences():
    r = parse_judge_response('```json\n{"score": 1, "justification": "OK"}\n```', "binary", {}, None)
    assert r["passed"] is True

def test_resolve_override():
    c = resolve_judge_llm({"override_model": "gpt-4", "override_api_key": "sk-test"})
    assert isinstance(c, DefaultLLMClient)
    assert c.model == "gpt-4"

def test_resolve_no_config():
    # Patch settings to ensure no env defaults
    with patch("app.services.judge.settings") as mock_settings:
        mock_settings.judge_model = ""
        mock_settings.judge_api_key = ""
        with pytest.raises(ValueError, match="No judge LLM configured"):
            resolve_judge_llm({"use_target_llm": False})
