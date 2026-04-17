import json
from typing import Any
from pydantic import BaseModel, field_validator

class EvalResultResponse(BaseModel):
    id: int
    run_id: int
    test_case_id: int
    test_case_name: str = ""
    round_number: int = 1
    agent_messages: Any  # list[dict] or {"main": [...], "sub_agents": [...]}
    score: Any
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
