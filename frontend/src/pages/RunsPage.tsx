import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { listRuns, createRun, deleteRun } from '../api/runs'
import { listDatasets } from '../api/datasets'
import { listScorers } from '../api/scorers'
import { listAdapters } from '../api/adapters'
import StatusBadge from '../components/StatusBadge'
import type { EvalRunCreate } from '../types'
import styles from './RunsPage.module.css'

export default function RunsPage() {
  const queryClient = useQueryClient()
  const { data: runs, isLoading } = useQuery({
    queryKey: ['runs'],
    queryFn: listRuns,
    refetchInterval: runs?.some(r => r.status === 'running') ? 10000 : false,
  })
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
  const deleteMut = useMutation({
    mutationFn: deleteRun,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['runs'] }),
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
          <button type="submit" className={styles.btn} disabled={createMut.isPending || form.dataset_id === 0 || form.scorer_id === 0 || form.adapter_id === 0}>Create Run</button>
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
              <td>{datasets?.find(d => d.id === r.dataset_id)?.name ?? r.dataset_id}</td>
              <td>{scorers?.find(s => s.id === r.scorer_id)?.name ?? r.scorer_id}</td>
              <td>{adapters?.find(a => a.id === r.adapter_id)?.name ?? r.adapter_id}</td>
              <td>{r.created_at.slice(0, 10)}</td>
              <td>
                {r.status === 'pending' && (
                  <Link to={`/runs/${r.id}`} className={styles.btnSmall}>Start</Link>
                )}
                {r.status === 'completed' && (
                  <Link to={`/runs/${r.id}`} className={styles.btnSmall}>View</Link>
                )}
                {' '}
                <button className={styles.btnDanger} onClick={() => { if (confirm(`Delete run #${r.id} and all its results?`)) deleteMut.mutate(r.id) }}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {runs?.length === 0 && <p className={styles.empty}>No eval runs yet. Create one to start evaluating.</p>}
    </div>
  )
}
