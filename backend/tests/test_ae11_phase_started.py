"""AE-11: SSE phase_started events for scorer-mode pipelines."""

from __future__ import annotations

from app.services import orchestrator as orch


def test_run_scorer_mode_emits_phase_started_events_source_contains_both_phases():
    import inspect
    src = inspect.getsource(orch._run_scorer_mode)
    # Both phases must emit phase_started before their round_started cascade.
    assert 'phase_started' in src and '"phase": "agent_run"' in src
    assert '"phase": "judge"' in src
    # Order: agent_run phase_started appears before judge phase_started.
    assert src.index('"phase": "agent_run"') < src.index('"phase": "judge"')
