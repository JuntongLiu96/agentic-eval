import json
from typing import Any
import httpx
from app.bridge.base import LLMClient
from app.config import settings

SYSTEM_EVAL_PROMPT = """You are an expert evaluation judge. Your job is to evaluate an AI agent's output against expected results using the provided scoring criteria.

You MUST respond with valid JSON matching the requested output format. Do not include any text outside the JSON object.
"""

class DefaultLLMClient:
    def __init__(self, model: str, api_key: str, base_url: str = ""):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/") if base_url else "https://api.openai.com/v1"

    async def chat(self, messages: list[dict[str, str]]) -> str:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
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

def assemble_judge_prompt(scorer_eval_prompt: str, scorer_criteria: dict[str, Any], scorer_output_format: str,
                          expected_result: Any, agent_messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    user_content = f"""## Scoring Criteria
{scorer_eval_prompt}

## Criteria Details
{json.dumps(scorer_criteria, indent=2)}

## Expected Result
{json.dumps(expected_result, indent=2)}

## Agent Output (message list)
{json.dumps(agent_messages, indent=2)}

## Required Output Format: {scorer_output_format}
Respond with ONLY a valid JSON object matching the {scorer_output_format} format."""
    return [
        {"role": "system", "content": SYSTEM_EVAL_PROMPT},
        {"role": "user", "content": user_content},
    ]

def parse_judge_response(response_text: str, output_format: str, score_range: dict[str, Any], pass_threshold: float | None) -> dict[str, Any]:
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    data = json.loads(text)

    if output_format == "binary":
        return {"score": data, "passed": data.get("passed", False), "reasoning": data.get("reasoning", "")}
    elif output_format == "numeric":
        score_val = data.get("score", 0)
        threshold = pass_threshold
        if threshold is None:
            smin = score_range.get("min", 0)
            smax = score_range.get("max", 100)
            threshold = smin + (smax - smin) * 0.6
        return {"score": data, "passed": score_val >= threshold, "reasoning": data.get("reasoning", "")}
    elif output_format == "rubric":
        overall = data.get("overall_score", 0)
        threshold = pass_threshold
        if threshold is None:
            smin = score_range.get("min", 1)
            smax = score_range.get("max", 5)
            threshold = smin + (smax - smin) * 0.6
        return {"score": data, "passed": overall >= threshold, "reasoning": data.get("reasoning", "")}
    return {"score": data, "passed": False, "reasoning": "Unknown format"}
