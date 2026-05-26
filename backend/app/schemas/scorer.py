from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator

from app.models.scorer import (
    SCORER_TYPE_LLM_JUDGE,
    VALID_SCORER_TYPES,
)
from app.schemas._helpers import parse_json_if_str


class ScorerCreate(BaseModel):
    name: str
    description: str = ""
    # AE-1: dispatch tag. "llm_judge" (default), "boolean_rubric",
    # "programmatic", or "series".
    scorer_type: str = SCORER_TYPE_LLM_JUDGE
    eval_prompt: str = ""
    pass_threshold: float | None = None
    tags: list[str] = []
    # AE-1: programmatic-scorer rules / AE-6 series-scorer config. Dict at the
    # API boundary; persisted as JSON in the DB column.
    config: dict[str, Any] = {}

    @field_validator("scorer_type")
    @classmethod
    def _check_scorer_type(cls, v: str) -> str:
        if v not in VALID_SCORER_TYPES:
            raise ValueError(
                f"scorer_type must be one of {sorted(VALID_SCORER_TYPES)}; got {v!r}"
            )
        return v


class ScorerResponse(BaseModel):
    id: int
    name: str
    description: str
    scorer_type: str
    eval_prompt: str
    pass_threshold: float | None
    tags: list[str]
    config: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("tags", mode="before")
    @classmethod
    def parse_tags(cls, v: Any) -> Any:
        return parse_json_if_str(v)

    @field_validator("config", mode="before")
    @classmethod
    def parse_config(cls, v: Any) -> Any:
        return parse_json_if_str(v) or {}


class ScorerUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    scorer_type: str | None = None
    eval_prompt: str | None = None
    pass_threshold: float | None = None
    tags: list[str] | None = None
    config: dict[str, Any] | None = None

    @field_validator("scorer_type")
    @classmethod
    def _check_scorer_type(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_SCORER_TYPES:
            raise ValueError(
                f"scorer_type must be one of {sorted(VALID_SCORER_TYPES)}; got {v!r}"
            )
        return v
