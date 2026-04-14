import json
from typing import Any
import httpx
from app.bridge.base import LLMClient
from app.config import settings

SYSTEM_EVAL_PROMPT = """You are an expert evaluation judge. Your job is to evaluate an AI agent's output against expected results using the provided scoring criteria.

Follow the output format specified in the scoring criteria exactly. If the scoring criteria specify a particular JSON format, use that format.

If no specific format is given, respond with this default JSON format:
{
  "score": <number>,
  "justification": "<detailed explanation of why you gave this score, referencing the scoring criteria>"
}

Do not include any text outside the JSON object.
"""

class DefaultLLMClient:
    def __init__(self, model: str, api_key: str, base_url: str = ""):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/") if base_url else "https://api.openai.com/v1"

    async def chat(self, messages: list[dict[str, str]]) -> str:
        base = self.base_url.rstrip("/")
        if not base.endswith("/v1"):
            base += "/v1"
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "messages": messages},
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

def resolve_judge_llm(judge_config: dict[str, Any], adapter_llm: LLMClient | None = None) -> LLMClient:
    # 1. Explicit override
    override_model = judge_config.get("override_model")
    if override_model:
        return DefaultLLMClient(
            model=override_model,
            api_key=judge_config.get("override_api_key", ""),
            base_url=judge_config.get("override_base_url", ""),
        )
    # 2. Target agent's LLM
    if judge_config.get("use_target_llm", True) and adapter_llm is not None:
        return adapter_llm
    # 3. System default
    if settings.judge_model and settings.judge_api_key:
        return DefaultLLMClient(model=settings.judge_model, api_key=settings.judge_api_key, base_url=settings.judge_base_url)
    # 4. Error
    raise ValueError("No judge LLM configured. Set JUDGE_MODEL/JUDGE_API_KEY env vars or configure an override in judge_config.")

def assemble_judge_prompt(eval_prompt: str, expected_result: Any,
                          agent_messages: list[dict[str, Any]],
                          sub_agent_messages: list[dict[str, Any]] | None = None) -> list[dict[str, str]]:
    """Assemble the judge prompt from the scorer's eval_prompt, expected result, and agent output.

    The eval_prompt contains everything: scoring criteria, score range, and scoring rules.
    """
    sub_agent_section = ""
    if sub_agent_messages:
        sub_agent_section = f"""

## Sub-Agent Messages (internal agent calls)
{json.dumps(sub_agent_messages, indent=2)}
"""

    user_content = f"""## Scoring Criteria & Rules
{eval_prompt}

## Expected Result
{json.dumps(expected_result, indent=2)}

## Agent Output (main agent message list)
{json.dumps(agent_messages, indent=2)}
{sub_agent_section}
Respond with a JSON object containing:
- "score": a numeric score value per the scoring rules above
- "justification": a detailed explanation of why you assigned this score, referencing specific scoring criteria and specific parts of the agent's output

Respond with ONLY the JSON object, no other text."""
    return [
        {"role": "system", "content": SYSTEM_EVAL_PROMPT},
        {"role": "user", "content": user_content},
    ]

def _extract_json(text: str) -> dict[str, Any]:
    """Extract the first valid JSON object from text, tolerating trailing content.

    Handles common LLM quirks:
      1. Markdown code fences (```json ... ```)
      2. Extra text before the opening '{' (e.g. "Here is my evaluation:\\n{...}")
      3. Extra text after the closing '}' (the original "Extra data" crash)
    """
    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]  # drop opening fence line
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    # Find the first '{' — skip any preamble the LLM added
    start = text.find("{")
    if start == -1:
        raise json.JSONDecodeError("No JSON object found in judge response", text, 0)

    # raw_decode parses exactly one JSON value and stops, ignoring trailing content
    decoder = json.JSONDecoder(strict=False)
    data, _ = decoder.raw_decode(text, start)

    if not isinstance(data, dict):
        raise json.JSONDecodeError("Expected a JSON object, got " + type(data).__name__, text, start)

    return data


def parse_judge_response(response_text: str, pass_threshold: float | None) -> dict[str, Any]:
    """Parse the judge LLM response. Extracts score + justification, computes passed.

    Supports two formats:
    1. Standard: {"score": N, "justification": "..."}
    2. Boolean rubric: {"items": {...}, "dimensions": {...}, "overall_pass_rate": 0.77, "verdict": "pass"}
    """
    data = _extract_json(response_text.strip())

    # Detect boolean rubric format (has "items" and "overall_pass_rate")
    if "items" in data and "overall_pass_rate" in data:
        score_val = data["overall_pass_rate"]
        verdict = data.get("verdict", "")
        threshold = pass_threshold if pass_threshold is not None else 0.6
        # Both conditions must be met: scorer verdict says "pass" AND rate >= threshold
        passed = verdict == "pass" and score_val >= threshold
        justification = json.dumps(data, indent=2)
        return {"score": score_val, "passed": passed, "justification": justification}

    # Standard format
    score_val = data.get("score", 0)
    justification = data.get("justification", "")
    threshold = pass_threshold if pass_threshold is not None else 60.0
    passed = score_val >= threshold

    return {"score": score_val, "passed": passed, "justification": justification}
