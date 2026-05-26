"""AE-6: cross-round series scorer tests."""

from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from app.services.series_scorer import _eval_check, evaluate_series


@dataclass
class _FakeScorer:
    config: str = ""
    pass_threshold: float | None = None


def test_monotonic_increasing_passes_on_rising_series():
    out = _eval_check(
        {"id": "c", "type": "monotonic_increasing", "path": "agent_metadata.confidence"},
        [{"confidence": 0.5}, {"confidence": 0.7}, {"confidence": 0.9}],
    )
    assert out["passed"] is True


def test_monotonic_increasing_fails_on_regression():
    out = _eval_check(
        {"id": "c", "type": "monotonic_increasing", "path": "agent_metadata.confidence"},
        [{"confidence": 0.5}, {"confidence": 0.4}],
    )
    assert out["passed"] is False


def test_equals_applies_to_last_by_default():
    out = _eval_check(
        {"id": "d", "type": "equals", "path": "agent_metadata.memory_count", "value": 1},
        [{"memory_count": 3}, {"memory_count": 1}],
    )
    assert out["passed"] is True


def test_delta_at_least_checks_first_to_last_delta():
    out = _eval_check(
        {"id": "g", "type": "delta_at_least",
         "path": "agent_metadata.confidence", "value": 0.3},
        [{"confidence": 0.5}, {"confidence": 0.65}, {"confidence": 0.85}],
    )
    assert out["passed"] is True
    assert out["delta"] == pytest.approx(0.35)


def test_ca003_reinforcement_passes_all_checks():
    """CA-003: dedup collapses to 1 memory; confidence rises monotonically."""
    scorer = _FakeScorer(config=json.dumps({
        "checks": [
            {"id": "conf_monotone", "type": "monotonic_increasing",
             "path": "agent_metadata.confidence"},
            {"id": "dedup_one", "type": "equals",
             "path": "agent_metadata.memory_count", "value": 1},
        ],
        "pass_threshold": 1.0,
    }))
    result = evaluate_series(scorer, [
        {"confidence": 0.5, "memory_count": 1},
        {"confidence": 0.65, "memory_count": 1},
        {"confidence": 0.78, "memory_count": 1},
        {"confidence": 0.88, "memory_count": 1},
        {"confidence": 0.95, "memory_count": 1},
    ])
    assert result["passed"] is True
    assert result["score"] == 1.0


def test_unsupported_check_marked_failed():
    scorer = _FakeScorer(config=json.dumps({
        "checks": [{"id": "x", "type": "weird", "path": "agent_metadata.a"}],
    }))
    result = evaluate_series(scorer, [{"a": 1}])
    just = json.loads(result["justification"])
    assert "unsupported" in just["checks"][0]["reason"]


def test_no_checks_passes_trivially():
    result = evaluate_series(_FakeScorer(config=json.dumps({"checks": []})), [{}])
    assert result["passed"] is True


@pytest.mark.asyncio
async def test_dispatcher_routes_series_scorer_without_llm():
    """Orchestrator's _run_judge should dispatch series scorers via evaluate_series."""
    from app.services.orchestrator import _run_judge

    scorer = _FakeScorer(config=json.dumps({
        "checks": [{"id": "c", "type": "equals",
                    "path": "agent_metadata.confidence", "value": 0.5}],
        "pass_threshold": 1.0,
    }))
    setattr(scorer, "scorer_type", "series")
    setattr(scorer, "name", "test-series")
    setattr(scorer, "eval_prompt", "")

    class _ExplodingJudge:
        async def chat(self, _messages):
            raise AssertionError("LLM must not be called for series scorer")

    result = await _run_judge(
        judge_client=_ExplodingJudge(),
        scorer=scorer,
        expected={},
        agent_messages=[],
        sub_agent_messages=None,
        agent_metadata={"confidence": 0.5},
    )
    assert result["passed"] is True
