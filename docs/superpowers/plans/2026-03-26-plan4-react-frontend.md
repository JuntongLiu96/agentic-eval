# Plan 4: React Frontend Dashboard

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a React TypeScript single-page application that provides a web dashboard for managing datasets, scorers, adapters, and eval runs with live progress monitoring, results visualization, and run comparison.

**Architecture:** Vite + React 18 + TypeScript. Uses React Router for navigation, a shared API client module (fetch-based), and a simple component library with consistent styling via CSS modules. No heavy state management — React Query handles server state. SSE via EventSource for live run progress.

**Tech Stack:** React 18, TypeScript, Vite, React Router v6, TanStack React Query, CSS Modules, Vitest + React Testing Library

**Spec:** `docs/superpowers/specs/2026-03-26-agentic-eval-system-design.md` (Section 4: Web Dashboard Pages)

**Depends on:** Plan 1 (Data Layer) + Plan 2 (Bridge/Orchestrator) + Plan 3 (CLI) — complete, 105 tests passing.

---

## File Structure

```
frontend/
├── index.html
├── package.json
├── tsconfig.json
├── tsconfig.node.json
├── vite.config.ts
├── src/
│   ├── main.tsx                    # React root + QueryClientProvider + BrowserRouter
│   ├── App.tsx                     # Layout shell + route definitions
│   ├── App.module.css              # Layout styles (sidebar, header, content area)
│   ├── api/
│   │   ├── client.ts              # Shared fetch wrapper (BASE_URL, error handling)
│   │   ├── datasets.ts            # Dataset + TestCase API functions
│   │   ├── scorers.ts             # Scorer API functions
│   │   ├── adapters.ts            # Adapter API functions
│   │   ├── runs.ts                # EvalRun API functions (CRUD, start, stream, compare, export)
│   │   └── templates.ts           # ScorerTemplate API functions
│   ├── types/
│   │   └── index.ts               # All TypeScript interfaces matching backend schemas
│   ├── pages/
│   │   ├── DatasetsPage.tsx        # Dataset list + create form
│   │   ├── DatasetsPage.module.css
│   │   ├── DatasetDetailPage.tsx   # Single dataset with test cases table + CSV import/export
│   │   ├── DatasetDetailPage.module.css
│   │   ├── ScorersPage.tsx         # Scorer list + create form
│   │   ├── ScorersPage.module.css
│   │   ├── TemplatesPage.tsx       # Scorer template gallery with copy-to-clipboard
│   │   ├── TemplatesPage.module.css
│   │   ├── AdaptersPage.tsx        # Adapter list + create form + health check
│   │   ├── AdaptersPage.module.css
│   │   ├── RunsPage.tsx            # Run history list + new run form
│   │   ├── RunsPage.module.css
│   │   ├── RunDetailPage.tsx       # Run detail with results table + expandable reasoning
│   │   ├── RunDetailPage.module.css
│   │   ├── ComparePage.tsx         # Side-by-side run comparison
│   │   └── ComparePage.module.css
│   └── components/
│       ├── StatusBadge.tsx         # Colored badge for run status (pending/running/completed/failed)
│       ├── StatusBadge.module.css
│       ├── PassFailIcon.tsx        # ✓/✗ icon for pass/fail
│       └── PassFailIcon.module.css
```

---

### Task 1: Project scaffolding with Vite + React + TypeScript

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`

- [ ] **Step 1: Initialize the frontend project**

```bash
cd F:/AgenticEval && mkdir frontend && cd frontend
npm create vite@latest . -- --template react-ts
```

If the interactive prompt is an issue, create the files manually.

- [ ] **Step 2: Install dependencies**

```bash
cd F:/AgenticEval/frontend
npm install react-router-dom @tanstack/react-query
npm install -D @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom vitest @types/react @types/react-dom
```

- [ ] **Step 3: Configure Vite with proxy**

`frontend/vite.config.ts`:
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test-setup.ts',
  },
})
```

- [ ] **Step 4: Create test setup file**

`frontend/src/test-setup.ts`:
```typescript
import '@testing-library/jest-dom'
```

- [ ] **Step 5: Create root entry point**

`frontend/src/main.tsx`:
```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
)
```

- [ ] **Step 6: Create placeholder App**

`frontend/src/App.tsx`:
```tsx
import { Routes, Route, Link } from 'react-router-dom'
import styles from './App.module.css'

export default function App() {
  return (
    <div className={styles.layout}>
      <nav className={styles.sidebar}>
        <h2 className={styles.logo}>AgenticEval</h2>
        <ul className={styles.navList}>
          <li><Link to="/">Runs</Link></li>
          <li><Link to="/datasets">Datasets</Link></li>
          <li><Link to="/scorers">Scorers</Link></li>
          <li><Link to="/templates">Templates</Link></li>
          <li><Link to="/adapters">Adapters</Link></li>
        </ul>
      </nav>
      <main className={styles.content}>
        <Routes>
          <Route path="/" element={<div>Runs page coming soon</div>} />
          <Route path="/datasets" element={<div>Datasets page coming soon</div>} />
          <Route path="/scorers" element={<div>Scorers page coming soon</div>} />
          <Route path="/templates" element={<div>Templates page coming soon</div>} />
          <Route path="/adapters" element={<div>Adapters page coming soon</div>} />
        </Routes>
      </main>
    </div>
  )
}
```

`frontend/src/App.module.css`:
```css
.layout {
  display: flex;
  min-height: 100vh;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.sidebar {
  width: 220px;
  background: #1a1a2e;
  color: #e0e0e0;
  padding: 1rem;
  flex-shrink: 0;
}

.logo {
  font-size: 1.3rem;
  color: #a78bfa;
  margin-bottom: 2rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid #334155;
}

.navList {
  list-style: none;
  padding: 0;
  margin: 0;
}

.navList li {
  margin-bottom: 0.5rem;
}

.navList a {
  color: #94a3b8;
  text-decoration: none;
  display: block;
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
  transition: background 0.15s;
}

.navList a:hover {
  background: #16213e;
  color: #e2e8f0;
}

.content {
  flex: 1;
  padding: 2rem;
  background: #0f0f23;
  color: #e0e0e0;
  overflow-y: auto;
}
```

- [ ] **Step 7: Verify dev server starts**

```bash
cd F:/AgenticEval/frontend && npm run dev
```
Expected: Dev server starts on port 3000, shows sidebar with nav links.

- [ ] **Step 8: Commit**

```bash
cd F:/AgenticEval && git add frontend/ && git commit -m "feat(frontend): scaffold React+Vite+TS project with routing and layout"
```

---

### Task 2: TypeScript types and API client

**Files:**
- Create: `frontend/src/types/index.ts`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/api/datasets.ts`
- Create: `frontend/src/api/scorers.ts`
- Create: `frontend/src/api/adapters.ts`
- Create: `frontend/src/api/runs.ts`
- Create: `frontend/src/api/templates.ts`

- [ ] **Step 1: Create TypeScript types**

`frontend/src/types/index.ts`:
```typescript
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
  output_format: string
  eval_prompt: string
  criteria: Record<string, unknown>
  score_range: Record<string, unknown>
  pass_threshold: number | null
  tags: string[]
  created_at: string
  updated_at: string
}

export interface ScorerCreate {
  name: string
  description?: string
  output_format: string
  eval_prompt: string
  criteria: Record<string, unknown>
  score_range?: Record<string, unknown>
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
  output_format: string
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
}

// --- Eval Result ---
export interface EvalResult {
  id: number
  run_id: number
  test_case_id: number
  agent_messages: Record<string, unknown>[]
  score: Record<string, unknown>
  judge_reasoning: string
  passed: boolean
  duration_ms: number
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
  changed: boolean
}
```

- [ ] **Step 2: Create shared API client**

`frontend/src/api/client.ts`:
```typescript
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
```

- [ ] **Step 3: Create domain API modules**

`frontend/src/api/datasets.ts`:
```typescript
import { apiGet, apiPost, apiPut, apiDelete, apiUpload, apiDownloadUrl } from './client'
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
```

`frontend/src/api/scorers.ts`:
```typescript
import { apiGet, apiPost, apiDelete } from './client'
import type { Scorer, ScorerCreate } from '../types'

export const listScorers = () => apiGet<Scorer[]>('/scorers')
export const getScorer = (id: number) => apiGet<Scorer>(`/scorers/${id}`)
export const createScorer = (data: ScorerCreate) => apiPost<Scorer>('/scorers', data)
export const deleteScorer = (id: number) => apiDelete(`/scorers/${id}`)
```

`frontend/src/api/adapters.ts`:
```typescript
import { apiGet, apiPost, apiDelete } from './client'
import type { Adapter, AdapterCreate } from '../types'

export const listAdapters = () => apiGet<Adapter[]>('/adapters')
export const getAdapter = (id: number) => apiGet<Adapter>(`/adapters/${id}`)
export const createAdapter = (data: AdapterCreate) => apiPost<Adapter>('/adapters', data)
export const deleteAdapter = (id: number) => apiDelete(`/adapters/${id}`)
export const healthCheckAdapter = (id: number) =>
  apiPost<{ healthy: boolean; error?: string }>(`/adapters/${id}/health`)
```

`frontend/src/api/runs.ts`:
```typescript
import { apiGet, apiPost, apiDownloadUrl } from './client'
import type { EvalRun, EvalRunCreate, EvalResult, RunComparison } from '../types'

export const listRuns = () => apiGet<EvalRun[]>('/runs')
export const getRun = (id: number) => apiGet<EvalRun>(`/runs/${id}`)
export const createRun = (data: EvalRunCreate) => apiPost<EvalRun>('/runs', data)
export const startRun = (id: number) => apiPost<{ status: string; summary: Record<string, unknown> }>(`/runs/${id}/start`)
export const getRunResults = (id: number) => apiGet<EvalResult[]>(`/runs/${id}/results`)
export const compareRuns = (run1: number, run2: number) =>
  apiGet<RunComparison>('/runs/compare', { run1: String(run1), run2: String(run2) })
export const exportRunUrl = (id: number) => apiDownloadUrl(`/runs/${id}/export`)

export function streamRun(runId: number, onEvent: (event: Record<string, unknown>) => void, onDone: () => void) {
  const source = new EventSource(`/api/runs/${runId}/stream`)
  source.addEventListener('progress', (e) => onEvent(JSON.parse(e.data)))
  source.addEventListener('result', (e) => onEvent(JSON.parse(e.data)))
  source.addEventListener('complete', (e) => { onEvent(JSON.parse(e.data)); source.close(); onDone() })
  source.addEventListener('error', (e) => { source.close(); onDone() })
  return () => source.close()
}
```

`frontend/src/api/templates.ts`:
```typescript
import { apiGet } from './client'
import type { ScorerTemplate } from '../types'

export const listTemplates = () => apiGet<ScorerTemplate[]>('/scorer-templates')
export const getTemplate = (id: number) => apiGet<ScorerTemplate>(`/scorer-templates/${id}`)
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd F:/AgenticEval/frontend && npx tsc --noEmit
```
Expected: No errors.

- [ ] **Step 5: Commit**

```bash
cd F:/AgenticEval && git add frontend/src/types/ frontend/src/api/ && git commit -m "feat(frontend): add TypeScript types and API client modules"
```

---

### Task 3: Shared UI components (StatusBadge, PassFailIcon)

**Files:**
- Create: `frontend/src/components/StatusBadge.tsx`
- Create: `frontend/src/components/StatusBadge.module.css`
- Create: `frontend/src/components/PassFailIcon.tsx`
- Create: `frontend/src/components/PassFailIcon.module.css`

- [ ] **Step 1: Create StatusBadge component**

`frontend/src/components/StatusBadge.tsx`:
```tsx
import styles from './StatusBadge.module.css'

interface Props { status: string }

export default function StatusBadge({ status }: Props) {
  const cls = styles[status] || styles.default
  return <span className={`${styles.badge} ${cls}`}>{status}</span>
}
```

`frontend/src/components/StatusBadge.module.css`:
```css
.badge {
  display: inline-block;
  padding: 0.2rem 0.6rem;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.pending { background: #1e3a5f; color: #60a5fa; }
.running { background: #3b2f0a; color: #fbbf24; }
.completed { background: #14532d; color: #4ade80; }
.failed { background: #450a0a; color: #f87171; }
.default { background: #334155; color: #94a3b8; }
```

- [ ] **Step 2: Create PassFailIcon component**

`frontend/src/components/PassFailIcon.tsx`:
```tsx
import styles from './PassFailIcon.module.css'

interface Props { passed: boolean }

export default function PassFailIcon({ passed }: Props) {
  return (
    <span className={passed ? styles.pass : styles.fail}>
      {passed ? '✓' : '✗'}
    </span>
  )
}
```

`frontend/src/components/PassFailIcon.module.css`:
```css
.pass { color: #4ade80; font-weight: bold; font-size: 1.1rem; }
.fail { color: #f87171; font-weight: bold; font-size: 1.1rem; }
```

- [ ] **Step 3: Commit**

```bash
cd F:/AgenticEval && git add frontend/src/components/ && git commit -m "feat(frontend): add StatusBadge and PassFailIcon components"
```

---

### Task 4: Datasets page + Dataset detail page

**Files:**
- Create: `frontend/src/pages/DatasetsPage.tsx`
- Create: `frontend/src/pages/DatasetsPage.module.css`
- Create: `frontend/src/pages/DatasetDetailPage.tsx`
- Create: `frontend/src/pages/DatasetDetailPage.module.css`
- Modify: `frontend/src/App.tsx` (add routes)

- [ ] **Step 1: Create DatasetsPage**

`frontend/src/pages/DatasetsPage.tsx`:
```tsx
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { listDatasets, createDataset, deleteDataset } from '../api/datasets'
import type { DatasetCreate } from '../types'
import styles from './DatasetsPage.module.css'

export default function DatasetsPage() {
  const queryClient = useQueryClient()
  const { data: datasets, isLoading } = useQuery({ queryKey: ['datasets'], queryFn: listDatasets })
  const createMut = useMutation({
    mutationFn: createDataset,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['datasets'] }); resetForm() },
  })
  const deleteMut = useMutation({
    mutationFn: deleteDataset,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['datasets'] }),
  })

  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<DatasetCreate>({ name: '', description: '', target_type: 'custom', tags: [] })

  function resetForm() { setForm({ name: '', description: '', target_type: 'custom', tags: [] }); setShowForm(false) }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    createMut.mutate(form)
  }

  if (isLoading) return <div>Loading...</div>

  return (
    <div>
      <div className={styles.header}>
        <h1>Datasets</h1>
        <button className={styles.btn} onClick={() => setShowForm(!showForm)}>
          {showForm ? 'Cancel' : '+ New Dataset'}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className={styles.form}>
          <input placeholder="Name" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required />
          <input placeholder="Description" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
          <select value={form.target_type} onChange={e => setForm({ ...form, target_type: e.target.value })}>
            <option value="custom">Custom</option>
            <option value="tool">Tool</option>
            <option value="e2e_flow">E2E Flow</option>
          </select>
          <button type="submit" className={styles.btn} disabled={createMut.isPending}>Create</button>
        </form>
      )}

      <table className={styles.table}>
        <thead>
          <tr><th>ID</th><th>Name</th><th>Type</th><th>Tags</th><th>Created</th><th>Actions</th></tr>
        </thead>
        <tbody>
          {datasets?.map(d => (
            <tr key={d.id}>
              <td>{d.id}</td>
              <td><Link to={`/datasets/${d.id}`}>{d.name}</Link></td>
              <td>{d.target_type}</td>
              <td>{d.tags.join(', ')}</td>
              <td>{d.created_at.slice(0, 10)}</td>
              <td>
                <button className={styles.btnDanger} onClick={() => { if (confirm('Delete?')) deleteMut.mutate(d.id) }}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {datasets?.length === 0 && <p className={styles.empty}>No datasets yet. Create one to get started.</p>}
    </div>
  )
}
```

- [ ] **Step 2: Create DatasetsPage styles**

`frontend/src/pages/DatasetsPage.module.css`:
```css
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
.header h1 { margin: 0; color: #e2e8f0; }
.btn { background: #6366f1; color: white; border: none; padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; font-size: 0.9rem; }
.btn:hover { background: #818cf8; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btnDanger { background: #dc2626; color: white; border: none; padding: 0.3rem 0.7rem; border-radius: 4px; cursor: pointer; font-size: 0.8rem; }
.btnDanger:hover { background: #ef4444; }
.form { display: flex; gap: 0.5rem; margin-bottom: 1.5rem; flex-wrap: wrap; }
.form input, .form select { background: #1e293b; color: #e2e8f0; border: 1px solid #334155; padding: 0.5rem; border-radius: 4px; }
.table { width: 100%; border-collapse: collapse; }
.table th, .table td { text-align: left; padding: 0.6rem 0.8rem; border-bottom: 1px solid #1e293b; }
.table th { color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; }
.table a { color: #818cf8; text-decoration: none; }
.table a:hover { text-decoration: underline; }
.empty { color: #64748b; text-align: center; padding: 2rem; }
```

- [ ] **Step 3: Create DatasetDetailPage**

`frontend/src/pages/DatasetDetailPage.tsx`:
```tsx
import { useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getDataset, listTestCases, deleteTestCase, importCsv, exportCsvUrl } from '../api/datasets'
import styles from './DatasetDetailPage.module.css'

export default function DatasetDetailPage() {
  const { id } = useParams<{ id: string }>()
  const datasetId = Number(id)
  const queryClient = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)

  const { data: dataset } = useQuery({ queryKey: ['dataset', datasetId], queryFn: () => getDataset(datasetId) })
  const { data: testCases, isLoading } = useQuery({ queryKey: ['testcases', datasetId], queryFn: () => listTestCases(datasetId) })
  const deleteMut = useMutation({
    mutationFn: deleteTestCase,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['testcases', datasetId] }),
  })
  const importMut = useMutation({
    mutationFn: (file: File) => importCsv(datasetId, file),
    onSuccess: (data) => {
      alert(`Imported ${data.imported_count} test cases`)
      queryClient.invalidateQueries({ queryKey: ['testcases', datasetId] })
    },
  })

  function handleImport() {
    const file = fileRef.current?.files?.[0]
    if (file) importMut.mutate(file)
  }

  if (isLoading) return <div>Loading...</div>

  return (
    <div>
      <Link to="/datasets" className={styles.backLink}>← Back to Datasets</Link>
      <h1>{dataset?.name || 'Dataset'}</h1>
      <p className={styles.desc}>{dataset?.description}</p>
      <p className={styles.meta}>Type: {dataset?.target_type} | Tags: {dataset?.tags.join(', ') || 'none'}</p>

      <div className={styles.actions}>
        <input type="file" ref={fileRef} accept=".csv" style={{ display: 'none' }} onChange={handleImport} />
        <button className={styles.btn} onClick={() => fileRef.current?.click()}>Import CSV</button>
        <a href={exportCsvUrl(datasetId)} download className={styles.btn}>Export CSV</a>
      </div>

      <h2>Test Cases ({testCases?.length || 0})</h2>
      <table className={styles.table}>
        <thead>
          <tr><th>ID</th><th>Name</th><th>Data</th><th>Expected Result</th><th>Actions</th></tr>
        </thead>
        <tbody>
          {testCases?.map(tc => (
            <tr key={tc.id}>
              <td>{tc.id}</td>
              <td>{tc.name}</td>
              <td className={styles.jsonCell}>{JSON.stringify(tc.data).slice(0, 80)}</td>
              <td className={styles.jsonCell}>{JSON.stringify(tc.expected_result).slice(0, 80)}</td>
              <td>
                <button className={styles.btnDanger} onClick={() => { if (confirm('Delete?')) deleteMut.mutate(tc.id) }}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {testCases?.length === 0 && <p className={styles.empty}>No test cases. Import a CSV or create via CLI/API.</p>}
    </div>
  )
}
```

`frontend/src/pages/DatasetDetailPage.module.css`:
```css
.backLink { color: #818cf8; text-decoration: none; font-size: 0.9rem; }
.backLink:hover { text-decoration: underline; }
.desc { color: #94a3b8; }
.meta { color: #64748b; font-size: 0.85rem; }
.actions { display: flex; gap: 0.5rem; margin: 1rem 0; }
.btn { background: #6366f1; color: white; border: none; padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; font-size: 0.9rem; text-decoration: none; display: inline-block; }
.btn:hover { background: #818cf8; }
.btnDanger { background: #dc2626; color: white; border: none; padding: 0.3rem 0.7rem; border-radius: 4px; cursor: pointer; font-size: 0.8rem; }
.table { width: 100%; border-collapse: collapse; margin-top: 0.5rem; }
.table th, .table td { text-align: left; padding: 0.6rem 0.8rem; border-bottom: 1px solid #1e293b; }
.table th { color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; }
.jsonCell { font-family: 'SF Mono', monospace; font-size: 0.8rem; color: #94a3b8; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.empty { color: #64748b; text-align: center; padding: 2rem; }
```

- [ ] **Step 4: Add routes in App.tsx**

Update `App.tsx` to import and route these pages (replace the placeholder routes for `/datasets`):

```tsx
import DatasetsPage from './pages/DatasetsPage'
import DatasetDetailPage from './pages/DatasetDetailPage'

// In Routes:
<Route path="/datasets" element={<DatasetsPage />} />
<Route path="/datasets/:id" element={<DatasetDetailPage />} />
```

- [ ] **Step 5: Verify in browser**

```bash
cd F:/AgenticEval/frontend && npm run dev
```
Navigate to http://localhost:3000/datasets — should show the datasets page.

- [ ] **Step 6: Commit**

```bash
cd F:/AgenticEval && git add frontend/src/ && git commit -m "feat(frontend): add Datasets and DatasetDetail pages"
```

---

### Task 5: Scorers page + Templates page

**Files:**
- Create: `frontend/src/pages/ScorersPage.tsx`
- Create: `frontend/src/pages/ScorersPage.module.css`
- Create: `frontend/src/pages/TemplatesPage.tsx`
- Create: `frontend/src/pages/TemplatesPage.module.css`
- Modify: `frontend/src/App.tsx` (add routes)

- [ ] **Step 1: Create ScorersPage**

`frontend/src/pages/ScorersPage.tsx`:
```tsx
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listScorers, createScorer, deleteScorer } from '../api/scorers'
import type { ScorerCreate } from '../types'
import styles from './ScorersPage.module.css'

export default function ScorersPage() {
  const queryClient = useQueryClient()
  const { data: scorers, isLoading } = useQuery({ queryKey: ['scorers'], queryFn: listScorers })
  const createMut = useMutation({
    mutationFn: createScorer,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['scorers'] }); setShowForm(false) },
  })
  const deleteMut = useMutation({
    mutationFn: deleteScorer,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['scorers'] }),
  })

  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<ScorerCreate>({
    name: '', description: '', output_format: 'binary', eval_prompt: '', criteria: {}, tags: [],
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    createMut.mutate(form)
  }

  if (isLoading) return <div>Loading...</div>

  return (
    <div>
      <div className={styles.header}>
        <h1>Scorers</h1>
        <button className={styles.btn} onClick={() => setShowForm(!showForm)}>
          {showForm ? 'Cancel' : '+ New Scorer'}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className={styles.form}>
          <input placeholder="Name" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required />
          <input placeholder="Description" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
          <select value={form.output_format} onChange={e => setForm({ ...form, output_format: e.target.value })}>
            <option value="binary">Binary</option>
            <option value="numeric">Numeric</option>
            <option value="rubric">Rubric</option>
          </select>
          <textarea placeholder="Eval prompt..." value={form.eval_prompt} onChange={e => setForm({ ...form, eval_prompt: e.target.value })} required rows={3} />
          <button type="submit" className={styles.btn} disabled={createMut.isPending}>Create</button>
        </form>
      )}

      <table className={styles.table}>
        <thead>
          <tr><th>ID</th><th>Name</th><th>Format</th><th>Threshold</th><th>Tags</th><th>Actions</th></tr>
        </thead>
        <tbody>
          {scorers?.map(s => (
            <tr key={s.id}>
              <td>{s.id}</td>
              <td>{s.name}</td>
              <td>{s.output_format}</td>
              <td>{s.pass_threshold ?? 'default'}</td>
              <td>{s.tags.join(', ')}</td>
              <td>
                <button className={styles.btnDanger} onClick={() => { if (confirm('Delete?')) deleteMut.mutate(s.id) }}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {scorers?.length === 0 && <p className={styles.empty}>No scorers yet. Create one or use a template.</p>}
    </div>
  )
}
```

`frontend/src/pages/ScorersPage.module.css` — use same styles as DatasetsPage.module.css (copy the same CSS content).

- [ ] **Step 2: Create TemplatesPage with copy-to-clipboard**

`frontend/src/pages/TemplatesPage.tsx`:
```tsx
import { useQuery } from '@tanstack/react-query'
import { listTemplates } from '../api/templates'
import styles from './TemplatesPage.module.css'

export default function TemplatesPage() {
  const { data: templates, isLoading } = useQuery({ queryKey: ['templates'], queryFn: listTemplates })

  function copyPrompt(text: string) {
    navigator.clipboard.writeText(text)
    alert('Prompt copied to clipboard!')
  }

  if (isLoading) return <div>Loading...</div>

  return (
    <div>
      <h1>Scorer Templates</h1>
      <p className={styles.subtitle}>Copy a template prompt, paste it into your coding agent to generate a scorer.</p>

      <div className={styles.grid}>
        {templates?.map(t => (
          <div key={t.id} className={styles.card}>
            <div className={styles.cardHeader}>
              <h3>{t.name}</h3>
              <span className={styles.badge}>{t.output_format}</span>
            </div>
            <p className={styles.category}>{t.category}</p>
            <p className={styles.desc}>{t.description}</p>
            <button className={styles.copyBtn} onClick={() => copyPrompt(t.template_prompt)}>
              Copy Prompt
            </button>
            {t.usage_instructions && (
              <details className={styles.details}>
                <summary>Usage Instructions</summary>
                <p>{t.usage_instructions}</p>
              </details>
            )}
          </div>
        ))}
      </div>
      {templates?.length === 0 && <p className={styles.empty}>No templates available.</p>}
    </div>
  )
}
```

`frontend/src/pages/TemplatesPage.module.css`:
```css
.subtitle { color: #94a3b8; margin-bottom: 1.5rem; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 1rem; }
.card { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 1.2rem; }
.cardHeader { display: flex; justify-content: space-between; align-items: center; }
.cardHeader h3 { margin: 0; color: #e2e8f0; font-size: 1rem; }
.badge { background: #3b0764; color: #c084fc; padding: 0.15rem 0.5rem; border-radius: 10px; font-size: 0.7rem; }
.category { color: #64748b; font-size: 0.8rem; margin: 0.3rem 0; }
.desc { color: #94a3b8; font-size: 0.9rem; }
.copyBtn { background: #22c55e; color: white; border: none; padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; font-size: 0.85rem; width: 100%; margin-top: 0.5rem; }
.copyBtn:hover { background: #16a34a; }
.details { margin-top: 0.5rem; color: #94a3b8; font-size: 0.85rem; }
.details summary { cursor: pointer; color: #818cf8; }
.empty { color: #64748b; text-align: center; padding: 2rem; }
```

- [ ] **Step 3: Update App.tsx with routes**

Import and add routes for ScorersPage and TemplatesPage.

- [ ] **Step 4: Commit**

```bash
cd F:/AgenticEval && git add frontend/src/ && git commit -m "feat(frontend): add Scorers and Templates pages"
```

---

### Task 6: Adapters page

**Files:**
- Create: `frontend/src/pages/AdaptersPage.tsx`
- Create: `frontend/src/pages/AdaptersPage.module.css`
- Modify: `frontend/src/App.tsx` (add route)

- [ ] **Step 1: Create AdaptersPage with health check**

`frontend/src/pages/AdaptersPage.tsx`:
```tsx
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listAdapters, createAdapter, deleteAdapter, healthCheckAdapter } from '../api/adapters'
import type { AdapterCreate } from '../types'
import styles from './AdaptersPage.module.css'

export default function AdaptersPage() {
  const queryClient = useQueryClient()
  const { data: adapters, isLoading } = useQuery({ queryKey: ['adapters'], queryFn: listAdapters })
  const createMut = useMutation({
    mutationFn: createAdapter,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['adapters'] }); setShowForm(false) },
  })
  const deleteMut = useMutation({
    mutationFn: deleteAdapter,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['adapters'] }),
  })
  const [healthResults, setHealthResults] = useState<Record<number, { healthy: boolean; error?: string }>>({})
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<AdapterCreate & { configStr: string }>({
    name: '', adapter_type: 'http', config: {}, description: '', configStr: '{}',
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    try {
      const config = JSON.parse(form.configStr)
      createMut.mutate({ name: form.name, adapter_type: form.adapter_type, config, description: form.description })
    } catch { alert('Invalid JSON in config') }
  }

  async function runHealthCheck(id: number) {
    const result = await healthCheckAdapter(id)
    setHealthResults(prev => ({ ...prev, [id]: result }))
  }

  if (isLoading) return <div>Loading...</div>

  return (
    <div>
      <div className={styles.header}>
        <h1>Adapters</h1>
        <button className={styles.btn} onClick={() => setShowForm(!showForm)}>
          {showForm ? 'Cancel' : '+ New Adapter'}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className={styles.form}>
          <input placeholder="Name" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required />
          <select value={form.adapter_type} onChange={e => setForm({ ...form, adapter_type: e.target.value })}>
            <option value="http">HTTP</option>
            <option value="python">Python</option>
            <option value="stdio">Stdio</option>
          </select>
          <textarea placeholder='Config JSON, e.g. {"base_url": "http://localhost:5000"}' value={form.configStr} onChange={e => setForm({ ...form, configStr: e.target.value })} rows={3} required />
          <input placeholder="Description" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
          <button type="submit" className={styles.btn} disabled={createMut.isPending}>Create</button>
        </form>
      )}

      <table className={styles.table}>
        <thead>
          <tr><th>ID</th><th>Name</th><th>Type</th><th>Description</th><th>Health</th><th>Actions</th></tr>
        </thead>
        <tbody>
          {adapters?.map(a => (
            <tr key={a.id}>
              <td>{a.id}</td>
              <td>{a.name}</td>
              <td>{a.adapter_type}</td>
              <td>{a.description}</td>
              <td>
                <button className={styles.btnSmall} onClick={() => runHealthCheck(a.id)}>Check</button>
                {healthResults[a.id] && (
                  <span className={healthResults[a.id].healthy ? styles.healthy : styles.unhealthy}>
                    {healthResults[a.id].healthy ? ' ✓' : ` ✗ ${healthResults[a.id].error || ''}`}
                  </span>
                )}
              </td>
              <td>
                <button className={styles.btnDanger} onClick={() => { if (confirm('Delete?')) deleteMut.mutate(a.id) }}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {adapters?.length === 0 && <p className={styles.empty}>No adapters configured.</p>}
    </div>
  )
}
```

`frontend/src/pages/AdaptersPage.module.css`:
```css
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
.header h1 { margin: 0; color: #e2e8f0; }
.btn { background: #6366f1; color: white; border: none; padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; font-size: 0.9rem; }
.btn:hover { background: #818cf8; }
.btn:disabled { opacity: 0.5; }
.btnSmall { background: #334155; color: #e2e8f0; border: none; padding: 0.2rem 0.6rem; border-radius: 4px; cursor: pointer; font-size: 0.8rem; }
.btnDanger { background: #dc2626; color: white; border: none; padding: 0.3rem 0.7rem; border-radius: 4px; cursor: pointer; font-size: 0.8rem; }
.form { display: flex; gap: 0.5rem; margin-bottom: 1.5rem; flex-wrap: wrap; }
.form input, .form select, .form textarea { background: #1e293b; color: #e2e8f0; border: 1px solid #334155; padding: 0.5rem; border-radius: 4px; }
.form textarea { min-width: 300px; }
.table { width: 100%; border-collapse: collapse; }
.table th, .table td { text-align: left; padding: 0.6rem 0.8rem; border-bottom: 1px solid #1e293b; }
.table th { color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; }
.healthy { color: #4ade80; font-size: 0.85rem; }
.unhealthy { color: #f87171; font-size: 0.85rem; }
.empty { color: #64748b; text-align: center; padding: 2rem; }
```

- [ ] **Step 2: Update App.tsx with route**

- [ ] **Step 3: Commit**

```bash
cd F:/AgenticEval && git add frontend/src/ && git commit -m "feat(frontend): add Adapters page with health check"
```

---

### Task 7: Runs page (run history + new run form)

**Files:**
- Create: `frontend/src/pages/RunsPage.tsx`
- Create: `frontend/src/pages/RunsPage.module.css`
- Modify: `frontend/src/App.tsx` (update route)

- [ ] **Step 1: Create RunsPage**

`frontend/src/pages/RunsPage.tsx`:
```tsx
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { listRuns, createRun, startRun } from '../api/runs'
import { listDatasets } from '../api/datasets'
import { listScorers } from '../api/scorers'
import { listAdapters } from '../api/adapters'
import StatusBadge from '../components/StatusBadge'
import type { EvalRunCreate } from '../types'
import styles from './RunsPage.module.css'

export default function RunsPage() {
  const queryClient = useQueryClient()
  const { data: runs, isLoading } = useQuery({ queryKey: ['runs'], queryFn: listRuns })
  const { data: datasets } = useQuery({ queryKey: ['datasets'], queryFn: listDatasets })
  const { data: scorers } = useQuery({ queryKey: ['scorers'], queryFn: listScorers })
  const { data: adapters } = useQuery({ queryKey: ['adapters'], queryFn: listAdapters })

  const createMut = useMutation({
    mutationFn: async (data: EvalRunCreate) => {
      const run = await createRun(data)
      return run
    },
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['runs'] }); setShowForm(false) },
  })

  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<EvalRunCreate>({
    name: '', dataset_id: 0, scorer_id: 0, adapter_id: 0,
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    createMut.mutate(form)
  }

  if (isLoading) return <div>Loading...</div>

  return (
    <div>
      <div className={styles.header}>
        <h1>Eval Runs</h1>
        <div className={styles.headerActions}>
          <Link to="/runs/compare" className={styles.btnOutline}>Compare Runs</Link>
          <button className={styles.btn} onClick={() => setShowForm(!showForm)}>
            {showForm ? 'Cancel' : '+ New Run'}
          </button>
        </div>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className={styles.form}>
          <input placeholder="Run name (optional)" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
          <select value={form.dataset_id} onChange={e => setForm({ ...form, dataset_id: Number(e.target.value) })} required>
            <option value={0} disabled>Select Dataset</option>
            {datasets?.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
          <select value={form.scorer_id} onChange={e => setForm({ ...form, scorer_id: Number(e.target.value) })} required>
            <option value={0} disabled>Select Scorer</option>
            {scorers?.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          <select value={form.adapter_id} onChange={e => setForm({ ...form, adapter_id: Number(e.target.value) })} required>
            <option value={0} disabled>Select Adapter</option>
            {adapters?.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
          <button type="submit" className={styles.btn} disabled={createMut.isPending}>Create Run</button>
        </form>
      )}

      <table className={styles.table}>
        <thead>
          <tr><th>ID</th><th>Name</th><th>Status</th><th>Dataset</th><th>Scorer</th><th>Adapter</th><th>Created</th><th>Actions</th></tr>
        </thead>
        <tbody>
          {runs?.map(r => (
            <tr key={r.id}>
              <td>{r.id}</td>
              <td><Link to={`/runs/${r.id}`}>{r.name || `Run #${r.id}`}</Link></td>
              <td><StatusBadge status={r.status} /></td>
              <td>{r.dataset_id}</td>
              <td>{r.scorer_id}</td>
              <td>{r.adapter_id}</td>
              <td>{r.created_at.slice(0, 10)}</td>
              <td>
                {r.status === 'pending' && (
                  <Link to={`/runs/${r.id}`} className={styles.btnSmall}>Start</Link>
                )}
                {r.status === 'completed' && (
                  <Link to={`/runs/${r.id}`} className={styles.btnSmall}>View</Link>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {runs?.length === 0 && <p className={styles.empty}>No eval runs yet. Create one to start evaluating.</p>}
    </div>
  )
}
```

`frontend/src/pages/RunsPage.module.css`:
```css
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
.header h1 { margin: 0; color: #e2e8f0; }
.headerActions { display: flex; gap: 0.5rem; }
.btn { background: #6366f1; color: white; border: none; padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; font-size: 0.9rem; }
.btn:hover { background: #818cf8; }
.btn:disabled { opacity: 0.5; }
.btnOutline { background: transparent; color: #818cf8; border: 1px solid #818cf8; padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; font-size: 0.9rem; text-decoration: none; }
.btnOutline:hover { background: #1e1b4b; }
.btnSmall { background: #334155; color: #e2e8f0; border: none; padding: 0.2rem 0.6rem; border-radius: 4px; cursor: pointer; font-size: 0.8rem; text-decoration: none; }
.form { display: flex; gap: 0.5rem; margin-bottom: 1.5rem; flex-wrap: wrap; align-items: flex-start; }
.form input, .form select { background: #1e293b; color: #e2e8f0; border: 1px solid #334155; padding: 0.5rem; border-radius: 4px; }
.table { width: 100%; border-collapse: collapse; }
.table th, .table td { text-align: left; padding: 0.6rem 0.8rem; border-bottom: 1px solid #1e293b; }
.table th { color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; }
.table a { color: #818cf8; text-decoration: none; }
.table a:hover { text-decoration: underline; }
.empty { color: #64748b; text-align: center; padding: 2rem; }
```

- [ ] **Step 2: Update App.tsx**

- [ ] **Step 3: Commit**

```bash
cd F:/AgenticEval && git add frontend/src/ && git commit -m "feat(frontend): add Runs page with create form and run history"
```

---

### Task 8: Run detail page (results table + start + SSE progress)

**Files:**
- Create: `frontend/src/pages/RunDetailPage.tsx`
- Create: `frontend/src/pages/RunDetailPage.module.css`
- Modify: `frontend/src/App.tsx` (add route)

- [ ] **Step 1: Create RunDetailPage**

`frontend/src/pages/RunDetailPage.tsx`:
```tsx
import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getRun, getRunResults, startRun, streamRun, exportRunUrl } from '../api/runs'
import StatusBadge from '../components/StatusBadge'
import PassFailIcon from '../components/PassFailIcon'
import styles from './RunDetailPage.module.css'

export default function RunDetailPage() {
  const { id } = useParams<{ id: string }>()
  const runId = Number(id)
  const queryClient = useQueryClient()

  const { data: run, refetch: refetchRun } = useQuery({ queryKey: ['run', runId], queryFn: () => getRun(runId) })
  const { data: results } = useQuery({
    queryKey: ['results', runId],
    queryFn: () => getRunResults(runId),
    enabled: run?.status === 'completed' || run?.status === 'failed',
  })

  const [isRunning, setIsRunning] = useState(false)
  const [progress, setProgress] = useState<string[]>([])
  const [expandedRow, setExpandedRow] = useState<number | null>(null)

  async function handleStart() {
    setIsRunning(true)
    setProgress([])
    try {
      const cleanup = streamRun(
        runId,
        (event) => setProgress(prev => [...prev, JSON.stringify(event)]),
        () => {
          setIsRunning(false)
          refetchRun()
          queryClient.invalidateQueries({ queryKey: ['results', runId] })
        },
      )
      // Fallback: if SSE doesn't connect, use direct start
      setTimeout(async () => {
        if (progress.length === 0) {
          cleanup()
          await startRun(runId)
          setIsRunning(false)
          refetchRun()
          queryClient.invalidateQueries({ queryKey: ['results', runId] })
        }
      }, 3000)
    } catch {
      await startRun(runId)
      setIsRunning(false)
      refetchRun()
      queryClient.invalidateQueries({ queryKey: ['results', runId] })
    }
  }

  const passedCount = results?.filter(r => r.passed).length ?? 0
  const totalCount = results?.length ?? 0

  return (
    <div>
      <Link to="/" className={styles.backLink}>← Back to Runs</Link>
      <div className={styles.header}>
        <h1>Run #{runId}: {run?.name || '(unnamed)'}</h1>
        <StatusBadge status={run?.status || 'pending'} />
      </div>

      <div className={styles.meta}>
        <span>Dataset: {run?.dataset_id}</span>
        <span>Scorer: {run?.scorer_id}</span>
        <span>Adapter: {run?.adapter_id}</span>
        {run?.started_at && <span>Started: {run.started_at}</span>}
        {run?.finished_at && <span>Finished: {run.finished_at}</span>}
      </div>

      {run?.status === 'pending' && (
        <button className={styles.startBtn} onClick={handleStart} disabled={isRunning}>
          {isRunning ? 'Running...' : 'Start Run'}
        </button>
      )}

      {isRunning && progress.length > 0 && (
        <div className={styles.progressLog}>
          <h3>Progress</h3>
          {progress.map((p, i) => <div key={i} className={styles.logLine}>{p}</div>)}
        </div>
      )}

      {results && results.length > 0 && (
        <>
          <div className={styles.summary}>
            <h2>Results: {passedCount}/{totalCount} passed ({totalCount > 0 ? ((passedCount / totalCount) * 100).toFixed(1) : 0}%)</h2>
            <a href={exportRunUrl(runId)} download className={styles.exportBtn}>Export CSV</a>
          </div>

          <table className={styles.table}>
            <thead>
              <tr><th>Test Case</th><th>Passed</th><th>Duration</th><th>Reasoning</th></tr>
            </thead>
            <tbody>
              {results.map(r => (
                <>
                  <tr key={r.id} className={styles.resultRow} onClick={() => setExpandedRow(expandedRow === r.id ? null : r.id)}>
                    <td>{r.test_case_id}</td>
                    <td><PassFailIcon passed={r.passed} /></td>
                    <td>{r.duration_ms}ms</td>
                    <td className={styles.reasoning}>{r.judge_reasoning.slice(0, 80)}...</td>
                  </tr>
                  {expandedRow === r.id && (
                    <tr key={`${r.id}-detail`} className={styles.expandedRow}>
                      <td colSpan={4}>
                        <div className={styles.detail}>
                          <h4>Full Reasoning</h4>
                          <p>{r.judge_reasoning}</p>
                          <h4>Score</h4>
                          <pre>{JSON.stringify(r.score, null, 2)}</pre>
                          <h4>Agent Messages</h4>
                          <pre>{JSON.stringify(r.agent_messages, null, 2)}</pre>
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  )
}
```

`frontend/src/pages/RunDetailPage.module.css`:
```css
.backLink { color: #818cf8; text-decoration: none; font-size: 0.9rem; }
.header { display: flex; align-items: center; gap: 1rem; margin: 1rem 0; }
.header h1 { margin: 0; color: #e2e8f0; }
.meta { display: flex; gap: 1.5rem; color: #64748b; font-size: 0.85rem; margin-bottom: 1rem; flex-wrap: wrap; }
.startBtn { background: #22c55e; color: white; border: none; padding: 0.7rem 1.5rem; border-radius: 6px; cursor: pointer; font-size: 1rem; }
.startBtn:hover { background: #16a34a; }
.startBtn:disabled { opacity: 0.5; cursor: not-allowed; }
.progressLog { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 1rem; margin: 1rem 0; max-height: 200px; overflow-y: auto; }
.progressLog h3 { margin: 0 0 0.5rem; color: #fbbf24; }
.logLine { font-family: monospace; font-size: 0.8rem; color: #94a3b8; margin-bottom: 0.2rem; }
.summary { display: flex; justify-content: space-between; align-items: center; margin: 1.5rem 0 0.5rem; }
.summary h2 { margin: 0; color: #e2e8f0; }
.exportBtn { background: #6366f1; color: white; border: none; padding: 0.4rem 1rem; border-radius: 6px; text-decoration: none; font-size: 0.85rem; }
.table { width: 100%; border-collapse: collapse; }
.table th, .table td { text-align: left; padding: 0.6rem 0.8rem; border-bottom: 1px solid #1e293b; }
.table th { color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; }
.resultRow { cursor: pointer; }
.resultRow:hover { background: #1e293b; }
.reasoning { font-size: 0.85rem; color: #94a3b8; max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.expandedRow td { background: #0f172a; }
.detail { padding: 1rem; }
.detail h4 { color: #a5b4fc; margin: 0.5rem 0 0.3rem; }
.detail p { color: #e2e8f0; white-space: pre-wrap; }
.detail pre { background: #1e293b; padding: 0.5rem; border-radius: 4px; font-size: 0.8rem; color: #94a3b8; overflow-x: auto; }
```

- [ ] **Step 2: Update App.tsx with route**

Add: `<Route path="/runs/:id" element={<RunDetailPage />} />`

- [ ] **Step 3: Commit**

```bash
cd F:/AgenticEval && git add frontend/src/ && git commit -m "feat(frontend): add RunDetail page with results, SSE progress, and expandable reasoning"
```

---

### Task 9: Compare page

**Files:**
- Create: `frontend/src/pages/ComparePage.tsx`
- Create: `frontend/src/pages/ComparePage.module.css`
- Modify: `frontend/src/App.tsx` (add route)

- [ ] **Step 1: Create ComparePage**

`frontend/src/pages/ComparePage.tsx`:
```tsx
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { listRuns, compareRuns } from '../api/runs'
import PassFailIcon from '../components/PassFailIcon'
import styles from './ComparePage.module.css'

export default function ComparePage() {
  const { data: runs } = useQuery({ queryKey: ['runs'], queryFn: listRuns })
  const [run1, setRun1] = useState<number>(0)
  const [run2, setRun2] = useState<number>(0)

  const { data: comparison, isLoading, refetch } = useQuery({
    queryKey: ['compare', run1, run2],
    queryFn: () => compareRuns(run1, run2),
    enabled: false,
  })

  function handleCompare() {
    if (run1 && run2 && run1 !== run2) refetch()
  }

  const completedRuns = runs?.filter(r => r.status === 'completed') || []

  return (
    <div>
      <Link to="/" className={styles.backLink}>← Back to Runs</Link>
      <h1>Compare Runs</h1>

      <div className={styles.selectors}>
        <select value={run1} onChange={e => setRun1(Number(e.target.value))}>
          <option value={0} disabled>Select Run 1</option>
          {completedRuns.map(r => <option key={r.id} value={r.id}>#{r.id}: {r.name || 'unnamed'}</option>)}
        </select>
        <span className={styles.vs}>vs</span>
        <select value={run2} onChange={e => setRun2(Number(e.target.value))}>
          <option value={0} disabled>Select Run 2</option>
          {completedRuns.map(r => <option key={r.id} value={r.id}>#{r.id}: {r.name || 'unnamed'}</option>)}
        </select>
        <button className={styles.btn} onClick={handleCompare} disabled={!run1 || !run2 || run1 === run2}>Compare</button>
      </div>

      {isLoading && <div>Loading comparison...</div>}

      {comparison && (
        <>
          <div className={styles.summaryRow}>
            <div className={styles.summaryCard}>
              <h3>Run #{comparison.run1.id}</h3>
              <p>{comparison.run1.summary.passed}/{comparison.run1.summary.total} passed</p>
              <p className={styles.rate}>{(comparison.run1.summary.pass_rate * 100).toFixed(1)}%</p>
            </div>
            <div className={styles.summaryCard}>
              <h3>Run #{comparison.run2.id}</h3>
              <p>{comparison.run2.summary.passed}/{comparison.run2.summary.total} passed</p>
              <p className={styles.rate}>{(comparison.run2.summary.pass_rate * 100).toFixed(1)}%</p>
            </div>
          </div>

          <table className={styles.table}>
            <thead>
              <tr><th>Test Case</th><th>Run 1</th><th>Run 2</th><th>Changed</th></tr>
            </thead>
            <tbody>
              {comparison.comparisons.map(c => (
                <tr key={c.test_case_id} className={c.changed ? styles.changed : ''}>
                  <td>{c.test_case_id}</td>
                  <td><PassFailIcon passed={c.run1_passed} /></td>
                  <td><PassFailIcon passed={c.run2_passed} /></td>
                  <td>{c.changed ? <span className={styles.changedLabel}>CHANGED</span> : ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  )
}
```

`frontend/src/pages/ComparePage.module.css`:
```css
.backLink { color: #818cf8; text-decoration: none; font-size: 0.9rem; }
.selectors { display: flex; align-items: center; gap: 0.75rem; margin: 1.5rem 0; }
.selectors select { background: #1e293b; color: #e2e8f0; border: 1px solid #334155; padding: 0.5rem; border-radius: 4px; min-width: 200px; }
.vs { color: #64748b; font-weight: bold; }
.btn { background: #6366f1; color: white; border: none; padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; }
.btn:hover { background: #818cf8; }
.btn:disabled { opacity: 0.5; }
.summaryRow { display: flex; gap: 1.5rem; margin: 1.5rem 0; }
.summaryCard { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 1.2rem; flex: 1; text-align: center; }
.summaryCard h3 { margin: 0; color: #a5b4fc; }
.summaryCard p { color: #94a3b8; margin: 0.3rem 0; }
.rate { font-size: 1.5rem; font-weight: bold; color: #e2e8f0; }
.table { width: 100%; border-collapse: collapse; }
.table th, .table td { text-align: left; padding: 0.6rem 0.8rem; border-bottom: 1px solid #1e293b; }
.table th { color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; }
.changed { background: #1a1a0a; }
.changedLabel { color: #fbbf24; font-size: 0.8rem; font-weight: bold; }
```

- [ ] **Step 2: Add route in App.tsx**

Add: `<Route path="/runs/compare" element={<ComparePage />} />`

**Important:** Place this BEFORE `/runs/:id` to avoid matching "compare" as an ID.

- [ ] **Step 3: Commit**

```bash
cd F:/AgenticEval && git add frontend/src/ && git commit -m "feat(frontend): add Compare page for side-by-side run comparison"
```

---

### Task 10: Final App.tsx integration and verification

**Files:**
- Modify: `frontend/src/App.tsx` (final version with all routes)

- [ ] **Step 1: Write final App.tsx**

Ensure all imports and routes are correctly wired:

```tsx
import { Routes, Route, Link, useLocation } from 'react-router-dom'
import styles from './App.module.css'

import DatasetsPage from './pages/DatasetsPage'
import DatasetDetailPage from './pages/DatasetDetailPage'
import ScorersPage from './pages/ScorersPage'
import TemplatesPage from './pages/TemplatesPage'
import AdaptersPage from './pages/AdaptersPage'
import RunsPage from './pages/RunsPage'
import RunDetailPage from './pages/RunDetailPage'
import ComparePage from './pages/ComparePage'

export default function App() {
  const location = useLocation()

  function isActive(path: string) {
    return location.pathname === path || location.pathname.startsWith(path + '/')
  }

  return (
    <div className={styles.layout}>
      <nav className={styles.sidebar}>
        <h2 className={styles.logo}>AgenticEval</h2>
        <ul className={styles.navList}>
          <li><Link to="/" className={isActive('/runs') || location.pathname === '/' ? styles.active : ''}>Runs</Link></li>
          <li><Link to="/datasets" className={isActive('/datasets') ? styles.active : ''}>Datasets</Link></li>
          <li><Link to="/scorers" className={isActive('/scorers') ? styles.active : ''}>Scorers</Link></li>
          <li><Link to="/templates" className={isActive('/templates') ? styles.active : ''}>Templates</Link></li>
          <li><Link to="/adapters" className={isActive('/adapters') ? styles.active : ''}>Adapters</Link></li>
        </ul>
      </nav>
      <main className={styles.content}>
        <Routes>
          <Route path="/" element={<RunsPage />} />
          <Route path="/datasets" element={<DatasetsPage />} />
          <Route path="/datasets/:id" element={<DatasetDetailPage />} />
          <Route path="/scorers" element={<ScorersPage />} />
          <Route path="/templates" element={<TemplatesPage />} />
          <Route path="/adapters" element={<AdaptersPage />} />
          <Route path="/runs/compare" element={<ComparePage />} />
          <Route path="/runs/:id" element={<RunDetailPage />} />
        </Routes>
      </main>
    </div>
  )
}
```

- [ ] **Step 2: Add active nav style**

Add to `App.module.css`:
```css
.active {
  background: #16213e;
  color: #a78bfa !important;
}
```

- [ ] **Step 3: Clear default Vite styles**

Remove or replace `frontend/src/index.css` with minimal reset:
```css
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #0f0f23; color: #e0e0e0; }
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd F:/AgenticEval/frontend && npx tsc --noEmit
```

- [ ] **Step 5: Verify dev server and test all pages**

```bash
cd F:/AgenticEval/frontend && npm run dev
```
Visit all pages in the browser and verify they render.

- [ ] **Step 6: Build production bundle**

```bash
cd F:/AgenticEval/frontend && npm run build
```
Expected: Build succeeds without errors.

- [ ] **Step 7: Commit**

```bash
cd F:/AgenticEval && git add frontend/ && git commit -m "feat(frontend): finalize App with all routes, active nav, and production build"
```
