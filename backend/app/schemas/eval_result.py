import json
from typing import Any
from pydantic import BaseModel, field_validator

class EvalResultResponse(BaseModel):
    id: int
    run_id: int
    test_case_id: int
    agent_messages: list[dict[str, Any]]
    score: dict[str, Any]
    judge_reasoning: str
    passed: bool
    duration_ms: int
    model_config = {"from_attributes": True}

    @field_validator("agent_messages", mode="before")
    @classmethod
    def parse_messages(cls, v: Any) -> Any:
        if isinstance(v, str): return json.loads(v)
        return v

    @field_validator("score", mode="before")
    @classmethod
    def parse_score(cls, v: Any) -> Any:
        if isinstance(v, str): return json.loads(v)
        return v
