import { apiGet, apiPost, apiDelete } from './client'
import type { Adapter, AdapterCreate } from '../types'

export const listAdapters = () => apiGet<Adapter[]>('/adapters')
export const getAdapter = (id: number) => apiGet<Adapter>(`/adapters/${id}`)
export const createAdapter = (data: AdapterCreate) => apiPost<Adapter>('/adapters', data)
export const deleteAdapter = (id: number) => apiDelete(`/adapters/${id}`)
export const healthCheckAdapter = (id: number) =>
  apiPost<{ healthy: boolean; error?: string }>(`/adapters/${id}/health`)
