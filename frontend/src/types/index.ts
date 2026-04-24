// --- Dataset ---
export interface Dataset {
  id: number
  name: string
  description: string
  target_type: string
  tags: string[]
  created_at: string
  updated_at: string
}

export interface DatasetCreate {
  name: string
  description?: string
  target_type?: string
  tags?: string[]
}

export interface TestCase {
  id: number
  dataset_id: number
  name: string
  data: unknown
  expected_result: unknown
  metadata: Record<string, unknown>
}

export interface TestCaseCreate {
  name: string
  data: unknown
  expected_result: unknown
  metadata?: Record<string, unknown>
}

// --- Scorer ---
export interface Scorer {
  id: number
  name: string
  description: string
  eval_prompt: string
  pass_threshold: number | null
  tags: string[]
  created_at: string
  updated_at: string
}

export interface ScorerCreate {
  name: string
  description?: string
  eval_prompt: string
  pass_threshold?: number | null
  tags?: string[]
}

// --- Scorer Template ---
export interface ScorerTemplate {
  id: number
  name: string
  description: string
  category: string
  template_prompt: string
  example_scorer: Record<string, unknown>
  usage_instructions: string
}

// --- Adapter ---
export interface Adapter {
  id: number
  name: string
  adapter_type: string
  config: Record<string, unknown>
  description: string
  created_at: string
}

export interface AdapterCreate {
  name: string
  adapter_type: string
  config: Record<string, unknown>
  description?: string
}

// --- Eval Run ---
export interface EvalRun {
  id: number
  name: string
  dataset_id: number
  scorer_id: number
  adapter_id: number
  judge_config: Record<string, unknown>
  num_rounds: number
  round_mode: string
  status: string
  started_at: string | null
  finished_at: string | null
  created_at: string
}

export interface EvalRunCreate {
  name?: string
  dataset_id: number
  scorer_id: number
  adapter_id: number
  judge_config?: Record<string, unknown>
  num_rounds?: number
  round_mode?: string
}

// --- Eval Result ---
export interface TurnResult {
  turn_index: number
  score: number
  passed: boolean
  justification: string
}

export interface EvalResult {
  id: number
  run_id: number
  test_case_id: number
  test_case_name: string
  round_number: number
  agent_messages: Record<string, unknown>[] | { main: Record<string, unknown>[]; sub_agents: Record<string, unknown>[] }
  score: number | Record<string, unknown> | string | null | unknown
  judge_reasoning: string
  passed: boolean
  duration_ms: number
  turn_results: TurnResult[] | null
}

// --- Compare ---
export interface RunComparison {
  run1: { id: number; summary: RunSummary }
  run2: { id: number; summary: RunSummary }
  comparisons: TestCaseComparison[]
}

export interface RunSummary {
  total: number
  passed: number
  pass_rate: number
  avg_score?: number
  min_score?: number
  max_score?: number
}

export interface TestCaseComparison {
  test_case_id: number
  run1_passed: boolean
  run2_passed: boolean
  run1_score: number | null
  run2_score: number | null
  changed: boolean
}

// --- Multi-Round Summary ---
export interface RoundSummary {
  round: number
  total: number
  passed: number
  pass_rate: number
  avg_score?: number
  min_score?: number
  max_score?: number
}

export interface TestCaseAveraged {
  test_case_id: number
  test_case_name: string
  avg_score: number | null
  passed: boolean
  avg_duration_ms: number
  rounds_passed: number
  total_rounds: number
}

export interface MultiRoundSummary {
  num_rounds: number
  round_mode: string
  round_summaries: RoundSummary[]
  averaged: RoundSummary
  tc_averaged: TestCaseAveraged[]
}

// --- Boolean Rubric ---
export interface RubricItem {
  pass: 0 | 1
  reason: string
}

export interface RubricDimension {
  passed: number
  total: number
  rate: number
}

export interface BooleanRubricResult {
  items: Record<string, RubricItem>
  dimensions: Record<string, RubricDimension>
  overall_pass_rate: number
  critical_failures: string[]
  verdict: "pass" | "needs_improvement" | "fail"
}
