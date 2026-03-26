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
