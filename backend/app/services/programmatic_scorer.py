"""AE-1: deterministic programmatic scorer.

A programmatic scorer evaluates a list of rules against agent_metadata (and,
optionally, message-level paths) without calling an LLM. Each rule is a
{id, path, op, value} object; passing requires ``passed_count / total >=
scorer.pass_threshold``.

This avoids LLM variance and per-call cost for numeric thresholds like
``n_reduction >= 0.7`` or ``cross_tenant_leakage_rate == 0``.

Config shape (stored in Scorer.config as JSON, or in Scorer.eval_prompt as a
fallback for scorers seeded before the column was added)::

    {
      "rules": [
        {"id": "n_reduction", "path": "agent_metadata.n_reduction",
         "op": ">=", "value": 0.70},
        {"id": "files_recall", "path": "agent_metadata.files_recall",
         "op": ">=", "value": 0.90}
      ],
      "pass_threshold": 1.0
    }

Supported ops: ``== != > >= < <= in not_in``.
Path syntax: dotted, rooted at ``agent_metadata`` or ``messages`` (only the
former is wired today — message-rooted paths return ``None`` and rules referring
to them fail).
"""

from __future__ import annotations

import json
from typing import Any

VALID_OPS = {"==", "!=", ">", ">=", "<", "<=", "in", "not_in"}


def _resolve_path(path: str, agent_metadata: dict[str, Any],
                  agent_messages: list[dict[str, Any]] | None = None,
                  testcase_metadata: dict[str, Any] | None = None,
                  expected_result: Any = None) -> Any:
    """Resolve ``agent_metadata.foo.bar`` against the provided context.

    Returns ``None`` when any segment is missing — comparisons against None
    naturally evaluate to False under ``>``/``>=``/``<``/``<=``.

    AE-12: also supports ``testcase_metadata.*`` and ``expected_result.*`` roots
    so per-case thresholds and assertions can live in the testcase row.
    """
    if not path:
        return None
    parts = path.split(".")
    root_name, *rest = parts
    if root_name == "agent_metadata":
        cursor: Any = agent_metadata
    elif root_name == "messages":
        cursor = agent_messages
    elif root_name == "testcase_metadata":
        cursor = testcase_metadata
    elif root_name == "expected_result":
        cursor = expected_result
    else:
        return None
    for seg in rest:
        if isinstance(cursor, dict):
            cursor = cursor.get(seg)
        elif isinstance(cursor, list):
            try:
                cursor = cursor[int(seg)]
            except (ValueError, IndexError):
                return None
        else:
            return None
        if cursor is None:
            return None
    return cursor


def _apply(op: str, lhs: Any, rhs: Any) -> bool:
    if op == "==":
        return lhs == rhs
    if op == "!=":
        return lhs != rhs
    if op == "in":
        try:
            return lhs in rhs
        except TypeError:
            return False
    if op == "not_in":
        try:
            return lhs not in rhs
        except TypeError:
            return False
    # numeric ops require both sides to be numbers
    if not isinstance(lhs, (int, float)) or isinstance(lhs, bool):
        return False
    if not isinstance(rhs, (int, float)) or isinstance(rhs, bool):
        return False
    if op == ">":
        return lhs > rhs
    if op == ">=":
        return lhs >= rhs
    if op == "<":
        return lhs < rhs
    if op == "<=":
        return lhs <= rhs
    return False


def _load_rules(scorer: Any) -> tuple[list[dict[str, Any]], float | None]:
    """Pull rules + pass_threshold out of a Scorer.

    Prefers ``scorer.config`` (the AE-1 column). Falls back to parsing
    ``scorer.eval_prompt`` as JSON to support scorers seeded before AE-1.
    """
    raw = getattr(scorer, "config", None)
    parsed: dict[str, Any] = {}
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {}
    elif isinstance(raw, dict):
        parsed = raw
    if not parsed and getattr(scorer, "eval_prompt", None):
        try:
            parsed = json.loads(scorer.eval_prompt)
        except (json.JSONDecodeError, TypeError):
            parsed = {}
    rules = parsed.get("rules", []) if isinstance(parsed, dict) else []
    threshold = parsed.get("pass_threshold") if isinstance(parsed, dict) else None
    if threshold is None:
        threshold = getattr(scorer, "pass_threshold", None)
    return list(rules), threshold


def evaluate_programmatic(
    scorer: Any,
    agent_metadata: dict[str, Any],
    agent_messages: list[dict[str, Any]] | None = None,
    testcase_metadata: dict[str, Any] | None = None,
    expected_result: Any = None,
) -> dict[str, Any]:
    """Evaluate the scorer's rules against agent_metadata.

    Returns the same {score, passed, justification} shape that LLM judges produce,
    so the orchestrator can persist it identically.

    AE-12: ``testcase_metadata`` and ``expected_result`` are passed through so
    rules can reference per-case data via ``testcase_metadata.*`` /
    ``expected_result.*`` paths, and ``rule.path_value`` can resolve the
    comparison target from the testcase row (e.g. per-case thresholds).
    """
    rules, threshold = _load_rules(scorer)
    if threshold is None:
        threshold = 1.0
    # Threshold may be on the 0-100 scale (legacy LLM-judge convention) or 0-1.
    if threshold > 1.0:
        threshold = threshold / 100.0

    rule_outcomes: list[dict[str, Any]] = []
    passed_count = 0
    for rule in rules:
        rule_id = rule.get("id", rule.get("path", "?"))
        op = rule.get("op")
        if op not in VALID_OPS:
            rule_outcomes.append({"id": rule_id, "passed": False,
                                  "reason": f"unsupported op: {op}"})
            continue
        path = rule.get("path", "")
        observed = _resolve_path(path, agent_metadata, agent_messages,
                                 testcase_metadata, expected_result)
        # AE-12: prefer path_value (resolved from testcase row) over literal value.
        if "path_value" in rule:
            expected = _resolve_path(rule["path_value"], agent_metadata,
                                     agent_messages, testcase_metadata,
                                     expected_result)
        else:
            expected = rule.get("value")
        ok = _apply(op, observed, expected)
        rule_outcomes.append({
            "id": rule_id, "passed": ok, "op": op,
            "observed": observed, "expected": expected, "path": path,
        })
        if ok:
            passed_count += 1

    total = len(rules)
    score_val = 1.0 if total == 0 else passed_count / total
    passed = score_val >= threshold if total > 0 else True
    return {
        "score": score_val,
        "passed": passed,
        "justification": json.dumps({
            "scorer_type": "programmatic",
            "passed_count": passed_count,
            "total": total,
            "pass_threshold": threshold,
            "rules": rule_outcomes,
        }, indent=2),
    }
