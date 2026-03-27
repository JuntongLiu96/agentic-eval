import json
from typing import Any

from pydantic import BaseModel, field_validator


class ScorerTemplateResponse(BaseModel):
    id: int
    name: str
    description: str
    category: str
    template_prompt: str
    example_scorer: dict[str, Any]
    usage_instructions: str

    model_config = {"from_attributes": True}

    @field_validator("example_scorer", mode="before")
    @classmethod
    def parse_json(cls, v: Any) -> Any:
        if isinstance(v, str):
            return json.loads(v)
        return v
