import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listAdapters, createAdapter, updateAdapter, deleteAdapter, healthCheckAdapter } from '../api/adapters'
import type { Adapter, AdapterCreate } from '../types'
import styles from './AdaptersPage.module.css'

/** Generate a cryptographically random 32-byte hex token. */
function generateAuthToken(): string {
  const bytes = new Uint8Array(32)
  crypto.getRandomValues(bytes)
  return Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('')
}

export default function AdaptersPage() {
  const queryClient = useQueryClient()
  const { data: adapters, isLoading } = useQuery({ queryKey: ['adapters'], queryFn: listAdapters })
  const createMut = useMutation({
    mutationFn: createAdapter,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['adapters'] }); setShowForm(false) },
  })
  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<AdapterCreate> }) => updateAdapter(id, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['adapters'] }); setEditingId(null) },
  })
  const deleteMut = useMutation({
    mutationFn: deleteAdapter,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['adapters'] }),
  })
  const [healthResults, setHealthResults] = useState<Record<number, { healthy: boolean; error?: string }>>({})
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState<AdapterCreate & { configStr: string }>({
    name: '', adapter_type: 'http', config: {}, description: '', configStr: '{}',
  })
  const [editForm, setEditForm] = useState({ name: '', configStr: '', description: '' })
  const [copiedCreate, setCopiedCreate] = useState(false)
  const [copiedEdit, setCopiedEdit] = useState(false)

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    try {
      const config = JSON.parse(form.configStr)
      createMut.mutate({ name: form.name, adapter_type: form.adapter_type, config, description: form.description })
    } catch { alert('Invalid JSON in config') }
  }

  function startEdit(a: Adapter) {
    setEditingId(a.id)
    setEditForm({
      name: a.name,
      configStr: JSON.stringify(a.config, null, 2),
      description: a.description,
    })
  }

  function handleEditSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (editingId === null) return
    try {
      const config = JSON.parse(editForm.configStr)
      updateMut.mutate({ id: editingId, data: { name: editForm.name, config, description: editForm.description } })
    } catch { alert('Invalid JSON in config') }
  }

  async function runHealthCheck(id: number) {
    const result = await healthCheckAdapter(id)
    setHealthResults(prev => ({ ...prev, [id]: result }))
  }

  function handleGenerateToken(target: 'create' | 'edit') {
    const token = generateAuthToken()
    const configStr = target === 'create' ? form.configStr : editForm.configStr
    try {
      const config = JSON.parse(configStr)
      config.auth_token = token
      const newConfigStr = JSON.stringify(config, null, 2)
      if (target === 'create') {
        setForm({ ...form, configStr: newConfigStr })
      } else {
        setEditForm({ ...editForm, configStr: newConfigStr })
      }
    } catch {
      alert('Invalid JSON in config — cannot inject token. Fix the JSON and try again.')
    }
  }

  function handleCopyToken(target: 'create' | 'edit') {
    const configStr = target === 'create' ? form.configStr : editForm.configStr
    try {
      const config = JSON.parse(configStr)
      const token = config.auth_token
      if (!token) {
        alert('No auth_token found in config. Generate one first.')
        return
      }
      navigator.clipboard.writeText(token)
      if (target === 'create') {
        setCopiedCreate(true)
        setTimeout(() => setCopiedCreate(false), 2000)
      } else {
        setCopiedEdit(true)
        setTimeout(() => setCopiedEdit(false), 2000)
      }
    } catch {
      alert('Invalid JSON in config.')
    }
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
          {form.adapter_type === 'http' && (
            <div className={styles.tokenActions}>
              <button type="button" className={styles.btnSmall} onClick={() => handleGenerateToken('create')}>Generate Token</button>
              <button type="button" className={styles.btnSmall} onClick={() => handleCopyToken('create')}>{copiedCreate ? 'Copied!' : 'Copy Token'}</button>
              <span className={styles.tokenHint}>Set the auth_token in your target agent's eval server to match this value.</span>
            </div>
          )}
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
            editingId === a.id ? (
              <tr key={a.id}>
                <td>{a.id}</td>
                <td colSpan={5}>
                  <form onSubmit={handleEditSubmit} className={styles.editForm}>
                    <input value={editForm.name} onChange={e => setEditForm({ ...editForm, name: e.target.value })} placeholder="Name" />
                    <input value={editForm.description} onChange={e => setEditForm({ ...editForm, description: e.target.value })} placeholder="Description" />
                    <textarea value={editForm.configStr} onChange={e => setEditForm({ ...editForm, configStr: e.target.value })} rows={4} />
                    {adapters?.find(a => a.id === editingId)?.adapter_type === 'http' && (
                      <div className={styles.tokenActions}>
                        <button type="button" className={styles.btnSmall} onClick={() => handleGenerateToken('edit')}>Generate Token</button>
                        <button type="button" className={styles.btnSmall} onClick={() => handleCopyToken('edit')}>{copiedEdit ? 'Copied!' : 'Copy Token'}</button>
                        <span className={styles.tokenHint}>Set the auth_token in your target agent's eval server to match this value.</span>
                      </div>
                    )}
                    <div className={styles.editActions}>
                      <button type="submit" className={styles.btn} disabled={updateMut.isPending}>Save</button>
                      <button type="button" className={styles.btnSmall} onClick={() => setEditingId(null)}>Cancel</button>
                    </div>
                  </form>
                </td>
              </tr>
            ) : (
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
                  <button className={styles.btnSmall} onClick={() => startEdit(a)}>Edit</button>
                  {' '}
                  <button className={styles.btnDanger} onClick={() => { if (confirm('Delete?')) deleteMut.mutate(a.id) }}>Delete</button>
                </td>
              </tr>
            )
          ))}
        </tbody>
      </table>
      {adapters?.length === 0 && <p className={styles.empty}>No adapters configured.</p>}
    </div>
  )
}
