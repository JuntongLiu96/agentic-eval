import { apiGet, apiPost, apiPut, apiDelete } from './client'
import type { Scorer, ScorerCreate } from '../types'

export const listScorers = () => apiGet<Scorer[]>('/scorers')
export const getScorer = (id: number) => apiGet<Scorer>(`/scorers/${id}`)
export const createScorer = (data: ScorerCreate) => apiPost<Scorer>('/scorers', data)
export const updateScorer = (id: number, data: Partial<ScorerCreate>) => apiPut<Scorer>(`/scorers/${id}`, data)
export const deleteScorer = (id: number) => apiDelete(`/scorers/${id}`)
