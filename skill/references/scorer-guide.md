# Scorer Prompt Writing Guide

The `eval_prompt` is the instruction given to the judge model. It determines how agent responses are scored.

## Template

```
You are evaluating an AI agent's ability to [describe the capability].

Given:
- **Prompt**: The user request sent to the agent
- **Expected Result**: The reference answer or behavior
- **Agent Response**: What the agent actually produced

Score the agent's performance on these criteria:

1. [Criterion A] (X points): [what to look for, when to give full/partial/zero]
2. [Criterion B] (Y points): [what to look for, when to give full/partial/zero]
3. [Criterion C] (Z points): [what to look for, when to give full/partial/zero]

Total score range: 0-[X+Y+Z].

Return your evaluation as:
{"score": <0-total>, "justification": "<per-criterion breakdown with points awarded>"}
```

## Best Practices

- **Points must add up**: All criterion points should sum to the max score (e.g., 100).
- **Be explicit about scoring**: State what earns full marks, partial marks, and zero for each criterion.
- **Handle non-applicable criteria**: If a criterion might not trigger (e.g., Error Handling when no errors occur), specify a default score: "If no errors occurred, award full points."
- **Require structured justification**: Ask the judge to report per-criterion scores so you can trace exactly where points were lost.
- **Avoid ambiguity**: Replace "good" / "appropriate" with measurable descriptions. "Completes the task with correct output" > "Does a good job."

## Common Scoring Dimensions

Pick the ones relevant to your eval:

| Dimension | What It Measures |
|-----------|-----------------|
| Task Completion | Did the agent achieve the stated goal? |
| Tool Usage | Were tools called correctly with right parameters? |
| Result Interpretation | Did the agent correctly understand tool outputs? |
| Prompt Efficiency | Was the approach concise and direct? |
| Error Handling | Did the agent recover from failures gracefully? |
| Code Quality | Is generated code correct, readable, idiomatic? |
| Communication | Is the response clear and well-structured? |

## Iteration Tips

1. **Run one eval round first**, then read the `judge_reasoning` across results.
2. **If the judge scores inconsistently**: add explicit rules like "If the agent uses tool X when tool Y would suffice, deduct N points."
3. **If scores cluster too high**: tighten criteria or add harder dimensions.
4. **If scores cluster too low**: check if criteria are unreasonably strict or if `expected_result` is too narrow.
5. **Add edge case rules**: "If the prompt asks for X but the agent does Y instead, score Criterion A as 0 regardless of other quality."

## Example

```
You are evaluating an AI agent's ability to answer questions using web search.

Given:
- **Prompt**: The question asked
- **Expected Result**: The reference answer
- **Agent Response**: The agent's actual answer

Score on these criteria:

1. Accuracy (40 points): Does the answer match the expected result? 40 = fully correct, 20 = partially correct, 0 = wrong or hallucinated.
2. Source Usage (30 points): Did the agent search and cite relevant sources? 30 = searched and cited, 15 = searched but didn't cite, 0 = didn't search.
3. Clarity (20 points): Is the answer well-structured and easy to understand? 20 = clear and concise, 10 = understandable but verbose, 0 = confusing.
4. Efficiency (10 points): Did the agent avoid unnecessary steps? 10 = direct path, 5 = minor detours, 0 = excessive redundant actions.

Total: 0-100. Return {"score": <0-100>, "justification": "<breakdown>"}
```
