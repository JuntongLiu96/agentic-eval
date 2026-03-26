import { apiGet, apiPost, apiDelete, apiUpload, apiDownloadUrl } from './client'
import type { Dataset, DatasetCreate, TestCase, TestCaseCreate } from '../types'

export const listDatasets = () => apiGet<Dataset[]>('/datasets')
export const getDataset = (id: number) => apiGet<Dataset>(`/datasets/${id}`)
export const createDataset = (data: DatasetCreate) => apiPost<Dataset>('/datasets', data)
export const deleteDataset = (id: number) => apiDelete(`/datasets/${id}`)

export const listTestCases = (datasetId: number) => apiGet<TestCase[]>(`/datasets/${datasetId}/testcases`)
export const createTestCase = (datasetId: number, data: TestCaseCreate) =>
  apiPost<TestCase>(`/datasets/${datasetId}/testcases`, data)
export const deleteTestCase = (id: number) => apiDelete(`/testcases/${id}`)

export const importCsv = (datasetId: number, file: File) =>
  apiUpload<{ imported_count: number }>(`/datasets/${datasetId}/import`, file)
export const exportCsvUrl = (datasetId: number) => apiDownloadUrl(`/datasets/${datasetId}/export`)
