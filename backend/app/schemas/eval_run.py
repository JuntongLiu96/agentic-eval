import json
from datetime import datetime
from typing import Any
from pydantic import BaseModel, field_validator

class EvalRunCreate(BaseModel):
    name: str = ""
    dataset_id: int
    scorer_id: int
    adapter_id: int
    judge_config: dict[str, Any] = {"use_target_llm": True}

class EvalRunResponse(BaseModel):
    id: int
    name: str
    dataset_id: int
    scorer_id: int
    adapter_id: int
    judge_config: dict[str, Any]
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    model_config = {"from_attributes": True}

    @field_validator("judge_config", mode="before")
    @classmethod
    def parse_json(cls, v: Any) -> Any:
        if isinstance(v, str): return json.loads(v)
        return v
