import type { BooleanRubricResult } from "../types"

/**
 * Attempts to parse judge_reasoning as a BooleanRubricResult.
 * Returns the parsed object if it matches the expected shape, null otherwise.
 *
 * Detection: parse as JSON, then duck-type check for "items", "dimensions", "verdict".
 */
export function parseBooleanRubric(
  reasoning: string
): BooleanRubricResult | null {
  if (!reasoning || !reasoning.trimStart().startsWith("{")) {
    return null
  }

  try {
    const parsed = JSON.parse(reasoning)

    if (
      parsed &&
      typeof parsed === "object" &&
      "items" in parsed &&
      "dimensions" in parsed &&
      "verdict" in parsed
    ) {
      return parsed as BooleanRubricResult
    }
  } catch {
    // not JSON — fall through
  }

  return null
}
