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
