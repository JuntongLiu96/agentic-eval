from typing import Any
from pydantic import BaseModel


class RoundSummary(BaseModel):
    round: int
    total: int
    passed: int
    pass_rate: float
    avg_score: float | None = None
    min_score: float | None = None
    max_score: float | None = None


class MultiRoundSummary(BaseModel):
    num_rounds: int
    round_mode: str
    round_summaries: list[RoundSummary]
    averaged: RoundSummary
