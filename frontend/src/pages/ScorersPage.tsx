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
