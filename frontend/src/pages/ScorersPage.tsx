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
    name: '', description: '', eval_prompt: '', pass_threshold: 60, tags: [],
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
          <textarea placeholder="Eval prompt (include criteria, score range, and scoring rules)..." value={form.eval_prompt} onChange={e => setForm({ ...form, eval_prompt: e.target.value })} required rows={6} />
          <input type="number" placeholder="Pass threshold" value={form.pass_threshold ?? 60} onChange={e => setForm({ ...form, pass_threshold: Number(e.target.value) })} />
          <button type="submit" className={styles.btn} disabled={createMut.isPending}>Create</button>
        </form>
      )}

      <table className={styles.table}>
        <thead>
          <tr><th>ID</th><th>Name</th><th>Threshold</th><th>Tags</th><th>Actions</th></tr>
        </thead>
        <tbody>
          {scorers?.map(s => (
            <tr key={s.id}>
              <td>{s.id}</td>
              <td>{s.name}</td>
              <td>{s.pass_threshold ?? 60}</td>
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
