"""AE-2: agent_metadata is exposed to scorers — both as a prompt section and
as the ``{{agent_metadata}}`` template variable.
"""

from __future__ import annotations

import json

from app.services.judge import assemble_judge_prompt


def test_judge_prompt_renders_template_variable():
    """{{agent_metadata}} in the eval_prompt is replaced with rendered JSON."""
    eval_prompt = (
        "Check that n_reduction >= 0.7. The metrics are:\n{{agent_metadata}}"
    )
    metadata = {"n_reduction": 0.82, "files_recall": 0.95}
    msgs = assemble_judge_prompt(
        eval_prompt=eval_prompt,
        expected_result={"pass": True},
        agent_messages=[{"role": "assistant", "content": "done"}],
        agent_metadata=metadata,
    )
    user = msgs[1]["content"]
    # Template variable was substituted (not left literal).
    assert "{{agent_metadata}}" not in user
    assert '"n_reduction": 0.82' in user


def test_judge_prompt_renders_metadata_section_even_without_template():
    """Scorers written before AE-2 still see metadata as a dedicated section."""
    eval_prompt = "Just score the trajectory."
    metadata = {"task_resolution": True}
    msgs = assemble_judge_prompt(
        eval_prompt=eval_prompt,
        expected_result={},
        agent_messages=[],
        agent_metadata=metadata,
    )
    user = msgs[1]["content"]
    assert "Agent Metadata" in user
    assert '"task_resolution": true' in user


def test_judge_prompt_omits_metadata_section_when_empty():
    """No agent_metadata -> no dedicated section, no template substitution."""
    msgs = assemble_judge_prompt(
        eval_prompt="Score it.",
        expected_result={},
        agent_messages=[],
        agent_metadata=None,
    )
    user = msgs[1]["content"]
    assert "Agent Metadata" not in user


def test_judge_prompt_backward_compat_without_metadata_kwarg():
    """Pre-AE-2 callers can still invoke without the metadata kwarg."""
    msgs = assemble_judge_prompt(
        eval_prompt="Score it.",
        expected_result={"x": 1},
        agent_messages=[{"role": "assistant", "content": "ok"}],
    )
    assert len(msgs) == 2
    assert "Score it." in msgs[1]["content"]
