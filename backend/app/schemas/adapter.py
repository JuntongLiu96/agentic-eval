import json
from datetime import datetime
from typing import Any
from pydantic import BaseModel, field_validator

class AdapterCreate(BaseModel):
    name: str
    adapter_type: str
    config: dict[str, Any]
    description: str = ""

class AdapterResponse(BaseModel):
    id: int
    name: str
    adapter_type: str
    config: dict[str, Any]
    description: str
    created_at: datetime
    model_config = {"from_attributes": True}

    @field_validator("config", mode="before")
    @classmethod
    def parse_config(cls, v: Any) -> Any:
        if isinstance(v, str): return json.loads(v)
        return v

class AdapterUpdate(BaseModel):
    name: str | None = None
    adapter_type: str | None = None
    config: dict[str, Any] | None = None
    description: str | None = None
