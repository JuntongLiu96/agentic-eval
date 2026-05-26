"""AE-1: programmatic scorer dispatches deterministic rule evaluation against
agent_metadata, with no LLM call.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from app.services.programmatic_scorer import (
    _apply,
    _resolve_path,
    evaluate_programmatic,
)


@dataclass
class _FakeScorer:
    eval_prompt: str = ""
    pass_threshold: float | None = None
    config: str = ""


# ---------------------------------------------------------------------------
# _resolve_path
# ---------------------------------------------------------------------------

def test_resolve_path_walks_agent_metadata():
    md = {"retrieval": {"hits": [{"rank": 1}, {"rank": 2}]}, "n_reduction": 0.8}
    assert _resolve_path("agent_metadata.n_reduction", md) == 0.8
    assert _resolve_path("agent_metadata.retrieval.hits.1.rank", md) == 2
    assert _resolve_path("agent_metadata.missing", md) is None
    assert _resolve_path("agent_metadata.retrieval.hits.99.rank", md) is None
    assert _resolve_path("unknown_root.foo", md) is None


# ---------------------------------------------------------------------------
# _apply
# ---------------------------------------------------------------------------

def test_apply_numeric_ops_require_numbers():
    assert _apply(">=", 0.8, 0.7) is True
    assert _apply(">=", 0.6, 0.7) is False
    # Strings/None don't quietly coerce.
    assert _apply(">=", "0.8", 0.7) is False
    assert _apply(">=", None, 0.7) is False
    # Booleans are NOT numbers for ordering ops (they'd silently pass otherwise).
    assert _apply(">=", True, 0) is False


def test_apply_eq_neq_in_notin():
    assert _apply("==", "x", "x") is True
    assert _apply("!=", "x", "y") is True
    assert _apply("in", "a", ["a", "b"]) is True
    assert _apply("not_in", "z", ["a", "b"]) is True


# ---------------------------------------------------------------------------
# evaluate_programmatic
# ---------------------------------------------------------------------------

def test_programmatic_scorer_passes_when_all_rules_pass():
    scorer = _FakeScorer(config=json.dumps({
        "rules": [
            {"id": "n_red", "path": "agent_metadata.n_reduction",
             "op": ">=", "value": 0.7},
            {"id": "fr", "path": "agent_metadata.files_recall",
             "op": ">=", "value": 0.9},
        ],
        "pass_threshold": 1.0,
    }))
    result = evaluate_programmatic(scorer, {"n_reduction": 0.82, "files_recall": 0.95})
    assert result["passed"] is True
    assert result["score"] == 1.0
    just = json.loads(result["justification"])
    assert just["passed_count"] == 2
    assert just["total"] == 2


def test_programmatic_scorer_fails_when_a_rule_fails():
    scorer = _FakeScorer(config=json.dumps({
        "rules": [
            {"id": "n_red", "path": "agent_metadata.n_reduction",
             "op": ">=", "value": 0.7},
        ],
        "pass_threshold": 1.0,
    }))
    result = evaluate_programmatic(scorer, {"n_reduction": 0.3})
    assert result["passed"] is False
    assert result["score"] == 0.0


def test_programmatic_scorer_partial_passes_with_low_threshold():
    """pass_threshold=0.5 allows half the rules to pass."""
    scorer = _FakeScorer(config=json.dumps({
        "rules": [
            {"id": "a", "path": "agent_metadata.a", "op": "==", "value": 1},
            {"id": "b", "path": "agent_metadata.b", "op": "==", "value": 2},
        ],
        "pass_threshold": 0.5,
    }))
    result = evaluate_programmatic(scorer, {"a": 1, "b": 999})
    assert result["score"] == 0.5
    assert result["passed"] is True


def test_programmatic_scorer_no_rules_passes_trivially():
    """A scorer with zero rules (e.g. CA-009 control) should not crash."""
    scorer = _FakeScorer(config=json.dumps({"rules": []}))
    result = evaluate_programmatic(scorer, {})
    assert result["passed"] is True


def test_programmatic_scorer_normalises_0_to_100_threshold():
    """Legacy LLM threshold like 80 (0-100) is treated as 0.8."""
    scorer = _FakeScorer(
        config=json.dumps({
            "rules": [
                {"id": "a", "path": "agent_metadata.a", "op": "==", "value": 1},
                {"id": "b", "path": "agent_metadata.b", "op": "==", "value": 1},
                {"id": "c", "path": "agent_metadata.c", "op": "==", "value": 1},
                {"id": "d", "path": "agent_metadata.d", "op": "==", "value": 1},
                {"id": "e", "path": "agent_metadata.e", "op": "==", "value": 1},
            ],
            "pass_threshold": 80,
        }),
    )
    result = evaluate_programmatic(scorer, {"a": 1, "b": 1, "c": 1, "d": 1, "e": 0})
    assert result["score"] == pytest.approx(0.8)
    assert result["passed"] is True


def test_programmatic_scorer_falls_back_to_eval_prompt_when_config_empty():
    """For scorers seeded before AE-1's config column, eval_prompt may carry JSON."""
    scorer = _FakeScorer(
        config="",
        eval_prompt=json.dumps({
            "rules": [{"id": "a", "path": "agent_metadata.x",
                       "op": "==", "value": 1}],
            "pass_threshold": 1.0,
        }),
    )
    result = evaluate_programmatic(scorer, {"x": 1})
    assert result["passed"] is True


def test_programmatic_scorer_unsupported_op_marks_rule_failed():
    scorer = _FakeScorer(config=json.dumps({
        "rules": [{"id": "weird", "path": "agent_metadata.x",
                   "op": "matches", "value": "foo"}],
        "pass_threshold": 1.0,
    }))
    result = evaluate_programmatic(scorer, {"x": "foo"})
    assert result["passed"] is False
    just = json.loads(result["justification"])
    assert "unsupported op" in just["rules"][0]["reason"]


# ---------------------------------------------------------------------------
# Orchestrator dispatch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_judge_dispatches_to_programmatic_without_llm():
    """When scorer_type == 'programmatic', no LLM call is made."""
    from app.services.orchestrator import _run_judge

    scorer = _FakeScorer(config=json.dumps({
        "rules": [{"id": "x", "path": "agent_metadata.x", "op": "==", "value": 1}],
        "pass_threshold": 1.0,
    }))
    setattr(scorer, "scorer_type", "programmatic")
    setattr(scorer, "name", "test-prog")

    class _ExplodingJudge:
        async def chat(self, _messages):
            raise AssertionError("LLM judge must not be called for programmatic scorer")

    result = await _run_judge(
        judge_client=_ExplodingJudge(),
        scorer=scorer,
        expected={},
        agent_messages=[],
        sub_agent_messages=None,
        agent_metadata={"x": 1},
    )
    assert result["passed"] is True
