"""AE-6: series scorer — assertions over results across multiple rounds.

Per-round programmatic scorers can't express cross-round invariants like
"confidence rises monotonically across rounds 1..N" (CA-003) or "after 3
partial ratings the memory is re-distilled" (CA-008). The series scorer reads
all per-round results for a single test case and applies a small DSL of
cross-round checks.

Config shape (stored in ``Scorer.config``)::

    {
      "checks": [
        {"id": "conf_monotone",
         "type": "monotonic_increasing",
         "path": "agent_metadata.confidence"},
        {"id": "dedup_one",
         "type": "equals",
         "path": "agent_metadata.memory_count",
         "value": 1,
         "applies_to": "last"}
      ],
      "pass_threshold": 1.0
    }

Check types:
  * ``monotonic_increasing`` / ``monotonic_decreasing`` — series must not regress
  * ``equals`` — value at ``applies_to`` round equals ``value``
    (``applies_to`` ∈ ``"first" | "last" | <int>``; default ``"last"``)
  * ``delta_at_least`` — ``last - first >= value``
"""

from __future__ import annotations

import json
from typing import Any

from app.services.programmatic_scorer import _resolve_path

VALID_CHECK_TYPES = {"monotonic_increasing", "monotonic_decreasing",
                     "equals", "delta_at_least"}


def _series(path: str, per_round_metadata: list[dict[str, Any]]) -> list[Any]:
    return [_resolve_path(path, md or {}) for md in per_round_metadata]


def _pick(series: list[Any], applies_to: Any) -> Any:
    if not series:
        return None
    if applies_to == "first":
        return series[0]
    if applies_to in (None, "last"):
        return series[-1]
    if isinstance(applies_to, int):
        try:
            return series[applies_to]
        except IndexError:
            return None
    return None


def _eval_check(check: dict[str, Any],
                per_round_metadata: list[dict[str, Any]]) -> dict[str, Any]:
    ctype = check.get("type")
    cid = check.get("id", ctype or "?")
    if ctype not in VALID_CHECK_TYPES:
        return {"id": cid, "passed": False, "reason": f"unsupported check type: {ctype}"}
    path = check.get("path", "")
    series = _series(path, per_round_metadata)
    nums = [v for v in series if isinstance(v, (int, float)) and not isinstance(v, bool)]

    if ctype == "monotonic_increasing":
        if len(nums) < 2:
            return {"id": cid, "passed": False, "series": series,
                    "reason": "need >=2 numeric points"}
        ok = all(b >= a for a, b in zip(nums, nums[1:]))
        return {"id": cid, "passed": ok, "series": series}
    if ctype == "monotonic_decreasing":
        if len(nums) < 2:
            return {"id": cid, "passed": False, "series": series,
                    "reason": "need >=2 numeric points"}
        ok = all(b <= a for a, b in zip(nums, nums[1:]))
        return {"id": cid, "passed": ok, "series": series}
    if ctype == "equals":
        observed = _pick(series, check.get("applies_to", "last"))
        return {"id": cid, "passed": observed == check.get("value"),
                "observed": observed, "expected": check.get("value")}
    if ctype == "delta_at_least":
        if len(nums) < 2:
            return {"id": cid, "passed": False, "series": series,
                    "reason": "need >=2 numeric points"}
        delta = nums[-1] - nums[0]
        ok = delta >= check.get("value", 0)
        return {"id": cid, "passed": ok, "delta": delta, "series": series}
    return {"id": cid, "passed": False, "reason": "unreachable"}


def _load_config(scorer: Any) -> dict[str, Any]:
    raw = getattr(scorer, "config", None)
    if isinstance(raw, str) and raw.strip():
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    if isinstance(raw, dict):
        return raw
    return {}


def evaluate_series(
    scorer: Any,
    per_round_metadata: list[dict[str, Any]],
) -> dict[str, Any]:
    """Evaluate cross-round checks over per-round agent_metadata.

    ``per_round_metadata`` is an ordered list of the ``agent_metadata`` dicts
    captured for rounds 1..N of a single test case.

    Returns ``{score, passed, justification}`` in the same shape as LLM judges and
    the programmatic scorer.
    """
    cfg = _load_config(scorer)
    checks = cfg.get("checks", []) if isinstance(cfg, dict) else []
    threshold = cfg.get("pass_threshold")
    if threshold is None:
        threshold = getattr(scorer, "pass_threshold", None)
    if threshold is None:
        threshold = 1.0
    if threshold > 1.0:
        threshold = threshold / 100.0

    outcomes = [_eval_check(c, per_round_metadata) for c in checks]
    total = len(outcomes)
    passed_count = sum(1 for o in outcomes if o.get("passed"))
    score = 1.0 if total == 0 else passed_count / total
    passed = score >= threshold if total > 0 else True
    return {
        "score": score,
        "passed": passed,
        "justification": json.dumps({
            "scorer_type": "series",
            "rounds": len(per_round_metadata),
            "passed_count": passed_count,
            "total": total,
            "pass_threshold": threshold,
            "checks": outcomes,
        }, indent=2),
    }
