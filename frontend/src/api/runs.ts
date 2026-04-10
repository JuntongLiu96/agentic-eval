import { apiGet, apiPost, apiDelete, apiDownloadUrl } from './client'
import type { EvalRun, EvalRunCreate, EvalResult, RunComparison, MultiRoundSummary } from '../types'

export const listRuns = () => apiGet<EvalRun[]>('/runs')
export const getRun = (id: number) => apiGet<EvalRun>(`/runs/${id}`)
export const createRun = (data: EvalRunCreate) => apiPost<EvalRun>('/runs', data)
export const deleteRun = (id: number) => apiDelete(`/runs/${id}`)
export const startRun = (id: number) => apiPost<{ status: string; summary: Record<string, unknown> }>(`/runs/${id}/start`)
export const getRunResults = (id: number, round?: number) =>
  apiGet<EvalResult[]>(`/runs/${id}/results`, round !== undefined ? { round: String(round) } : undefined)
export const getRunSummary = (id: number) => apiGet<MultiRoundSummary>(`/runs/${id}/summary`)
export const compareRuns = (run1: number, run2: number) =>
  apiGet<RunComparison>('/runs/compare', { run1: String(run1), run2: String(run2) })
export const exportRunUrl = (id: number) => apiDownloadUrl(`/runs/${id}/export`)

export function streamRun(runId: number, onEvent: (event: Record<string, unknown>) => void, onDone: () => void) {
  const source = new EventSource(`/api/runs/${runId}/stream`)
  source.addEventListener('run_started', (e) => onEvent(JSON.parse((e as MessageEvent).data)))
  source.addEventListener('case_started', (e) => onEvent(JSON.parse((e as MessageEvent).data)))
  source.addEventListener('round_started', (e) => onEvent(JSON.parse((e as MessageEvent).data)))
  source.addEventListener('case_completed', (e) => onEvent(JSON.parse((e as MessageEvent).data)))
  source.addEventListener('round_completed', (e) => onEvent(JSON.parse((e as MessageEvent).data)))
  source.addEventListener('run_completed', (e) => { onEvent(JSON.parse((e as MessageEvent).data)); source.close(); onDone() })
  source.addEventListener('error', () => { source.close(); onDone() })
  return () => source.close()
}
