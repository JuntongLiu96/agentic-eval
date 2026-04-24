"""Helpers for parsing single-turn and multi-turn test data."""


def parse_turns(data: dict) -> list[dict]:
    """Parse test data into a list of turns.

    Accepts either:
      {"prompt": "..."} — single-turn shorthand, wrapped to [{"prompt": "..."}]
      {"turns": [...]}  — explicit multi-turn list

    Raises ValueError on invalid input.
    """
    has_prompt = "prompt" in data
    has_turns = "turns" in data

    if has_prompt and has_turns:
        raise ValueError("Cannot have both 'prompt' and 'turns' in test data")
    if not has_prompt and not has_turns:
        raise ValueError("Test data must have either 'prompt' or 'turns'")

    if has_prompt:
        return [{"prompt": data["prompt"]}]

    turns = data["turns"]
    if not turns:
        raise ValueError("'turns' must not be empty")

    for i, turn in enumerate(turns):
        if "prompt" not in turn:
            raise ValueError(f"Turn {i} must have a 'prompt' field")

    return turns
