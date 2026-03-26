import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator


class TestCaseCreate(BaseModel):
    name: str
    data: Any  # Accepts any JSON-serializable value
    expected_result: Any
    metadata: dict[str, Any] = {}


class TestCaseResponse(BaseModel):
    id: int
    dataset_id: int
    name: str
    data: Any
    expected_result: Any
    metadata: dict[str, Any]

    model_config = {"from_attributes": True}

    @field_validator("data", "expected_result", "metadata", mode="before")
    @classmethod
    def parse_json_string(cls, v: Any) -> Any:
        if isinstance(v, str):
            return json.loads(v)
        return v


class TestCaseUpdate(BaseModel):
    name: str | None = None
    data: Any | None = None
    expected_result: Any | None = None
    metadata: dict[str, Any] | None = None


class DatasetCreate(BaseModel):
    name: str
    description: str = ""
    target_type: str = "custom"
    tags: list[str] = []


class DatasetResponse(BaseModel):
    id: int
    name: str
    description: str
    target_type: str
    tags: list[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("tags", mode="before")
    @classmethod
    def parse_tags(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return json.loads(v)
        return v


class DatasetUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    target_type: str | None = None
    tags: list[str] | None = None
