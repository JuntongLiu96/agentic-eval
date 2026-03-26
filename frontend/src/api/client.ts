const BASE_URL = '/api'

class ApiError extends Error {
  status: number
  detail: string
  constructor(status: number, detail: string) {
    super(`API Error ${status}: ${detail}`)
    this.status = status
    this.detail = detail
  }
}

async function handleResponse<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    let detail = resp.statusText
    try {
      const body = await resp.json()
      detail = body.detail || JSON.stringify(body)
    } catch { /* ignore parse errors */ }
    throw new ApiError(resp.status, detail)
  }
  if (resp.status === 204) return undefined as T
  return resp.json()
}

export async function apiGet<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(`${BASE_URL}${path}`, window.location.origin)
  if (params) Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v))
  const resp = await fetch(url.toString())
  return handleResponse<T>(resp)
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const resp = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  })
  return handleResponse<T>(resp)
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  const resp = await fetch(`${BASE_URL}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return handleResponse<T>(resp)
}

export async function apiDelete(path: string): Promise<void> {
  const resp = await fetch(`${BASE_URL}${path}`, { method: 'DELETE' })
  if (!resp.ok) {
    throw new ApiError(resp.status, resp.statusText)
  }
}

export async function apiUpload<T>(path: string, file: File, fieldName = 'file'): Promise<T> {
  const formData = new FormData()
  formData.append(fieldName, file)
  const resp = await fetch(`${BASE_URL}${path}`, { method: 'POST', body: formData })
  return handleResponse<T>(resp)
}

export function apiDownloadUrl(path: string): string {
  return `${BASE_URL}${path}`
}
