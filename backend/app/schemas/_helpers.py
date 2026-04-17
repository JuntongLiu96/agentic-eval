"""Internal helpers shared across schema modules."""

from __future__ import annotations

import json
from typing import Any


def parse_json_if_str(v: Any) -> Any:
    """Decode *v* as JSON when it is a string, otherwise return it unchanged.

    Used as a Pydantic ``field_validator(mode='before')`` callable for fields
    that are stored as JSON text in the database but surfaced as structured
    values (dict/list) on the API.  Non-string values pass through untouched
    so that already-parsed payloads (e.g. when validating a dict directly)
    round-trip cleanly.
    """
    if isinstance(v, str):
        return json.loads(v)
    return v
