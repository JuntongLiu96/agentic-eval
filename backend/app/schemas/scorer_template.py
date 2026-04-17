from typing import Any

from pydantic import BaseModel, field_validator

from app.schemas._helpers import parse_json_if_str


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
        return parse_json_if_str(v)
