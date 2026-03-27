import { apiGet, apiPost, apiPut, apiDelete } from './client'
import type { Adapter, AdapterCreate } from '../types'

export const listAdapters = () => apiGet<Adapter[]>('/adapters')
export const getAdapter = (id: number) => apiGet<Adapter>(`/adapters/${id}`)
export const createAdapter = (data: AdapterCreate) => apiPost<Adapter>('/adapters', data)
export const updateAdapter = (id: number, data: Partial<AdapterCreate>) => apiPut<Adapter>(`/adapters/${id}`, data)
export const deleteAdapter = (id: number) => apiDelete(`/adapters/${id}`)
export const healthCheckAdapter = (id: number) =>
  apiPost<{ healthy: boolean; error?: string }>(`/adapters/${id}/health`)
