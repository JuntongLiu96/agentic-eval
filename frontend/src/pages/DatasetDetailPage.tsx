import { useRef, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getDataset, listTestCases, createTestCase, deleteTestCase, importCsv, exportCsvUrl } from '../api/datasets'
import styles from './DatasetDetailPage.module.css'

export default function DatasetDetailPage() {
  const { id } = useParams<{ id: string }>()
  const datasetId = Number(id)
  const queryClient = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)

  const { data: dataset } = useQuery({ queryKey: ['dataset', datasetId], queryFn: () => getDataset(datasetId) })
  const { data: testCases, isLoading } = useQuery({ queryKey: ['testcases', datasetId], queryFn: () => listTestCases(datasetId) })
  const createMut = useMutation({
    mutationFn: (data: { name: string; data: unknown; expected_result: unknown }) => createTestCase(datasetId, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['testcases', datasetId] }); setShowForm(false); resetForm() },
  })
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

  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ name: '', prompt: '', expectedStr: '' })

  function resetForm() { setForm({ name: '', prompt: '', expectedStr: '' }) }

  function handleImport() {
    const file = fileRef.current?.files?.[0]
    if (file) importMut.mutate(file)
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    let expected: unknown
    try {
      expected = JSON.parse(form.expectedStr)
    } catch {
      alert('Invalid JSON in expected result')
      return
    }
    createMut.mutate({ name: form.name, data: { prompt: form.prompt }, expected_result: expected })
  }

  if (isLoading) return <div>Loading...</div>

  return (
    <div>
      <Link to="/datasets" className={styles.backLink}>← Back to Datasets</Link>
      <h1>{dataset?.name || 'Dataset'}</h1>
      <p className={styles.desc}>{dataset?.description}</p>
      <p className={styles.meta}>Type: {dataset?.target_type} | Tags: {dataset?.tags.join(', ') || 'none'}</p>

      <div className={styles.actions}>
        <button className={styles.btn} onClick={() => setShowForm(!showForm)}>
          {showForm ? 'Cancel' : '+ Add Test Case'}
        </button>
        <input type="file" ref={fileRef} accept=".csv" style={{ display: 'none' }} onChange={handleImport} />
        <button className={styles.btnOutline} onClick={() => fileRef.current?.click()}>Import CSV</button>
        <a href={exportCsvUrl(datasetId)} download className={styles.btnOutline}>Export CSV</a>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className={styles.addForm}>
          <input placeholder="Test case name" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required />
          <textarea placeholder="User prompt (what to send to the agent)" value={form.prompt} onChange={e => setForm({ ...form, prompt: e.target.value })} required rows={3} />
          <textarea placeholder='Expected result as JSON, e.g. {"answer": "4"}' value={form.expectedStr} onChange={e => setForm({ ...form, expectedStr: e.target.value })} required rows={3} />
          <button type="submit" className={styles.btn} disabled={createMut.isPending}>Add</button>
        </form>
      )}

      <h2>Test Cases ({testCases?.length || 0})</h2>
      <table className={styles.table}>
        <thead>
          <tr><th>ID</th><th>Name</th><th>Prompt</th><th>Expected Result</th><th>Actions</th></tr>
        </thead>
        <tbody>
          {testCases?.map(tc => {
            const data = tc.data as Record<string, unknown>
            const promptStr = typeof data?.prompt === 'string' ? data.prompt : JSON.stringify(tc.data)
            return (
              <tr key={tc.id}>
                <td>{tc.id}</td>
                <td>{tc.name}</td>
                <td className={styles.jsonCell}>{promptStr.slice(0, 80)}{promptStr.length > 80 ? '...' : ''}</td>
                <td className={styles.jsonCell}>{JSON.stringify(tc.expected_result).slice(0, 80)}</td>
                <td>
                  <button className={styles.btnDanger} onClick={() => { if (confirm('Delete?')) deleteMut.mutate(tc.id) }}>Delete</button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      {testCases?.length === 0 && <p className={styles.empty}>No test cases yet. Add one above or import a CSV.</p>}
    </div>
  )
}
