# Scorer Prompt Writing Guide

The `eval_prompt` is the instruction given to the judge model. It determines how agent responses are scored.

AgenticEval supports two scoring formats. Choose the one that fits your evaluation needs.

---

## Format 1: Standard Scoring (Continuous)

Best for: fine-grained quality assessment where partial credit matters.

### Template

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

**Pass logic:** `passed = score >= pass_threshold` (default: 60)

### Best Practices

- **Points must add up**: All criterion points should sum to the max score (e.g., 100).
- **Be explicit about scoring**: State what earns full marks, partial marks, and zero for each criterion.
- **Handle non-applicable criteria**: If a criterion might not trigger (e.g., Error Handling when no errors occur), specify a default score: "If no errors occurred, award full points."
- **Require structured justification**: Ask the judge to report per-criterion scores so you can trace exactly where points were lost.
- **Avoid ambiguity**: Replace "good" / "appropriate" with measurable descriptions. "Completes the task with correct output" > "Does a good job."

### Example

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

---

## Format 2: Boolean Rubric Scoring

Best for: behavioral compliance checks where each requirement is binary (met or not met). Research shows boolean rubrics produce more consistent LLM-as-judge results than continuous scales (Arize 2025, arXiv 2604.06996).

### Template

```
You are evaluating an AI agent using a BOOLEAN RUBRIC. For each sub-item below, judge PASS (1) or FAIL (0). No partial credit.

You will receive:
- **Prompt**: The user message sent to the agent
- **Expected Result**: Contains evaluation criteria
- **Agent Output**: The agent's actual response

## Sub-Items

### Dimension: [Dimension Name] (N items)

**[ID]-1: [Sub-item name]**
[What to check]
- PASS example: [concrete example]
- FAIL example: [concrete example]

**[ID]-2: [Sub-item name]**
...

## Scoring Rules

1. Judge each sub-item independently as PASS (1) or FAIL (0).
2. [Add cascade rules for critical sub-items — see below]

## Output Format

Return a JSON object:
{
  "items": {"[ID]-1": {"pass": 1, "reason": "..."}, ...},
  "dimensions": {"[dim_name]": {"passed": N, "total": M, "rate": 0.8}, ...},
  "overall_pass_rate": 0.77,
  "critical_failures": ["[ID]-2"],
  "verdict": "pass"
}

Verdict rules:
- "fail": [condition, e.g., core dimension rate < 0.6]
- "needs_improvement": [condition, e.g., any dimension rate < 0.5]
- "pass": [condition, e.g., all dimensions >= 0.5]
```

**Pass logic:** `passed = (verdict == "pass") AND (overall_pass_rate >= pass_threshold)`

Both conditions must be met. This dual-gate design lets you encode **cascade rules** in the scorer's verdict logic (ensuring critical sub-item failures pull down the overall judgment) while the system's `pass_threshold` enforces a minimum bar.

Set `pass_threshold` in the 0–1 range for boolean rubrics (e.g., `0.6` = 60% of sub-items must pass).

### Cascade Rules

Cascade rules are the key advantage of boolean rubrics over continuous scoring — they let you express that **some sub-items are more important than others** without assigning arbitrary point values.

**How they work:** When a critical sub-item fails, the scorer's eval_prompt instructs the judge to force-fail dependent sub-items, which lowers the overall_pass_rate and changes the verdict. The system then applies both the verdict and the threshold.

**Example cascade rules:**

```
## Cascade Rules

1. CORE CASCADE: If BOTH BEH-1 AND BEH-2 are FAIL, set ALL other items
   to FAIL. (If the agent fails the core behavioral requirement, nothing
   else matters.)

2. FABRICATION CASCADE (Level 1): If FAC-1 (no fabricated facts) is FAIL,
   force-FAIL these items regardless of standalone quality:
   - STR-2 (Copy-Paste Ready) — fabricated content is not safe to reuse
   - FWD-1 (Proposes Next Step) — next steps on fabricated foundations mislead
   - FWD-2 (Next Step Is Context-Specific) — same rationale

3. SEVERE FABRICATION CASCADE (Level 2): If BOTH FAC-1 AND FAC-2 are FAIL,
   additionally force-FAIL:
   - CAL-1 (Expresses Uncertainty) — agent clearly failed to express uncertainty
   - CAL-2 (Distinguishes Facts from Assumptions) — agent failed to distinguish
```

**Why this matters:** Without cascade rules, a boolean rubric treats all sub-items equally. An agent could fabricate data (FAC-1 FAIL) but still pass because formatting and next-steps sub-items are easy wins. Cascade rules prevent this by propagating critical failures to dependent sub-items, ensuring the overall pass rate reflects the true severity.

### Best Practices for Boolean Rubrics

- **Include PASS and FAIL examples** for each sub-item — this dramatically improves judge consistency.
- **Design cascade rules around your most important sub-items** — what failures should be deal-breakers?
- **Keep sub-items independent** (except for explicit cascades) — each should be judgeable on its own.
- **Use 8–15 sub-items** — fewer loses granularity, more overwhelms the judge.
- **Test verdict rules** by mentally walking through edge cases: "If only FAC-1 fails, what's the verdict?"

---

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
| Factual Integrity | Did the agent avoid fabricating data? |
| Calibration | Does the agent express uncertainty appropriately? |

## Iteration Tips

1. **Run one eval round first**, then read the `judge_reasoning` across results.
2. **If the judge scores inconsistently**: add explicit rules like "If the agent uses tool X when tool Y would suffice, deduct N points." For boolean rubrics, add more specific PASS/FAIL examples.
3. **If scores cluster too high**: tighten criteria or add harder dimensions. For boolean rubrics, add cascade rules so easy-pass items get force-failed when critical items fail.
4. **If scores cluster too low**: check if criteria are unreasonably strict or if `expected_result` is too narrow.
5. **Add edge case rules**: "If the prompt asks for X but the agent does Y instead, score Criterion A as 0 regardless of other quality."
