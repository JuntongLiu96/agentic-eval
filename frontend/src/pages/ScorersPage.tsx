import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listScorers, createScorer, deleteScorer } from '../api/scorers'
import { listTemplates } from '../api/templates'
import type { ScorerCreate } from '../types'
import styles from './ScorersPage.module.css'

export default function ScorersPage() {
  const queryClient = useQueryClient()
  const { data: scorers, isLoading } = useQuery({ queryKey: ['scorers'], queryFn: listScorers })
  const { data: templates } = useQuery({ queryKey: ['templates'], queryFn: listTemplates })
  const createMut = useMutation({
    mutationFn: createScorer,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['scorers'] }); setShowForm(false) },
  })
  const deleteMut = useMutation({
    mutationFn: deleteScorer,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['scorers'] }),
  })

  const [showForm, setShowForm] = useState(false)
  const [showTemplates, setShowTemplates] = useState(false)
  const [form, setForm] = useState<ScorerCreate>({
    name: '', description: '', eval_prompt: '', pass_threshold: 60, tags: [],
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    createMut.mutate(form)
  }

  function copyPrompt(text: string) {
    navigator.clipboard.writeText(text)
    alert('Prompt copied to clipboard!')
  }

  if (isLoading) return <div>Loading...</div>

  return (
    <div>
      <div className={styles.header}>
        <h1>Scorers</h1>
        <div className={styles.headerActions}>
          <button className={styles.btnOutline} onClick={() => setShowTemplates(true)}>
            Templates
          </button>
          <button className={styles.btn} onClick={() => setShowForm(!showForm)}>
            {showForm ? 'Cancel' : '+ New Scorer'}
          </button>
        </div>
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

      {/* Templates Modal */}
      {showTemplates && (
        <div className={styles.modalOverlay} onClick={() => setShowTemplates(false)}>
          <div className={styles.modal} onClick={e => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <h2>Scorer Templates</h2>
              <button className={styles.modalClose} onClick={() => setShowTemplates(false)}>✕</button>
            </div>
            <p className={styles.modalSubtitle}>Copy a template prompt, paste it into your coding agent to generate a scorer.</p>
            <div className={styles.templateGrid}>
              {templates?.map(t => (
                <div key={t.id} className={styles.templateCard}>
                  <div className={styles.templateCardHeader}>
                    <h3>{t.name}</h3>
                    <span className={styles.templateBadge}>{t.category}</span>
                  </div>
                  <p className={styles.templateDesc}>{t.description}</p>
                  <button className={styles.copyBtn} onClick={() => copyPrompt(t.template_prompt)}>
                    Copy Prompt
                  </button>
                  {t.usage_instructions && (
                    <details className={styles.templateDetails}>
                      <summary>Usage Instructions</summary>
                      <p>{t.usage_instructions}</p>
                    </details>
                  )}
                  {t.example_scorer && (
                    <details className={styles.templateDetails}>
                      <summary>Example Scorer</summary>
                      <pre className={styles.templatePre}>{JSON.stringify(t.example_scorer, null, 2)}</pre>
                    </details>
                  )}
                </div>
              ))}
            </div>
            {templates?.length === 0 && <p className={styles.empty}>No templates available.</p>}
          </div>
        </div>
      )}
    </div>
  )
}
