import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator


class ScorerCreate(BaseModel):
    name: str
    description: str = ""
    output_format: str  # "binary", "numeric", "rubric"
    eval_prompt: str
    criteria: dict[str, Any]
    score_range: dict[str, Any] = {}
    pass_threshold: float | None = None
    tags: list[str] = []


class ScorerResponse(BaseModel):
    id: int
    name: str
    description: str
    output_format: str
    eval_prompt: str
    criteria: dict[str, Any]
    score_range: dict[str, Any]
    pass_threshold: float | None
    tags: list[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("criteria", "score_range", mode="before")
    @classmethod
    def parse_json(cls, v: Any) -> Any:
        if isinstance(v, str):
            return json.loads(v)
        return v

    @field_validator("tags", mode="before")
    @classmethod
    def parse_tags(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return json.loads(v)
        return v


class ScorerUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    output_format: str | None = None
    eval_prompt: str | None = None
    criteria: dict[str, Any] | None = None
    score_range: dict[str, Any] | None = None
    pass_threshold: float | None = None
    tags: list[str] | None = None
