from typing import Any
from pydantic import BaseModel, field_validator

from app.schemas._helpers import parse_json_if_str

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
    turn_results: Any = None
    model_config = {"from_attributes": True}

    @field_validator("agent_messages", mode="before")
    @classmethod
    def parse_messages(cls, v: Any) -> Any:
        return parse_json_if_str(v)

    @field_validator("score", mode="before")
    @classmethod
    def parse_score(cls, v: Any) -> Any:
        return parse_json_if_str(v)

    @field_validator("turn_results", mode="before")
    @classmethod
    def parse_turn_results(cls, v: Any) -> Any:
        return parse_json_if_str(v)
