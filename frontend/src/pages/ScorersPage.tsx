import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listScorers, createScorer, updateScorer, deleteScorer } from '../api/scorers'
import { listTemplates } from '../api/templates'
import type { Scorer, ScorerCreate } from '../types'
import styles from './ScorersPage.module.css'

export default function ScorersPage() {
  const queryClient = useQueryClient()
  const { data: scorers, isLoading } = useQuery({ queryKey: ['scorers'], queryFn: listScorers })
  const { data: templates } = useQuery({ queryKey: ['templates'], queryFn: listTemplates })
  const createMut = useMutation({
    mutationFn: createScorer,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['scorers'] }); setShowForm(false) },
  })
  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<ScorerCreate> }) => updateScorer(id, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['scorers'] }); setViewScorer(null) },
  })
  const deleteMut = useMutation({
    mutationFn: deleteScorer,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['scorers'] }),
  })

  const [showForm, setShowForm] = useState(false)
  const [showTemplates, setShowTemplates] = useState(false)
  const [viewScorer, setViewScorer] = useState<Scorer | null>(null)
  const [isEditing, setIsEditing] = useState(false)
  const [editForm, setEditForm] = useState({ name: '', description: '', eval_prompt: '', pass_threshold: 60 })
  const [form, setForm] = useState<ScorerCreate>({
    name: '', description: '', eval_prompt: '', pass_threshold: 60, tags: [],
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    createMut.mutate(form)
  }

  function openView(s: Scorer) {
    setViewScorer(s)
    setIsEditing(false)
    setEditForm({ name: s.name, description: s.description, eval_prompt: s.eval_prompt, pass_threshold: s.pass_threshold ?? 60 })
  }

  function handleEditSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!viewScorer) return
    updateMut.mutate({ id: viewScorer.id, data: editForm })
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
              <td><span className={styles.link} onClick={() => openView(s)}>{s.name}</span></td>
              <td>{s.pass_threshold ?? 60}</td>
              <td>{s.tags.join(', ')}</td>
              <td>
                <button className={styles.btnSmall} onClick={() => openView(s)}>View</button>
                {' '}
                <button className={styles.btnDanger} onClick={() => { if (confirm('Delete?')) deleteMut.mutate(s.id) }}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {scorers?.length === 0 && <p className={styles.empty}>No scorers yet. Create one or use a template.</p>}

      {/* Scorer Preview/Edit Modal */}
      {viewScorer && (
        <div className={styles.modalOverlay} onClick={() => setViewScorer(null)}>
          <div className={styles.modal} onClick={e => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <h2>{isEditing ? 'Edit Scorer' : `Scorer #${viewScorer.id}`}</h2>
              <div className={styles.modalHeaderActions}>
                {!isEditing && (
                  <button className={styles.btnOutline} onClick={() => setIsEditing(true)}>Edit</button>
                )}
                <button className={styles.modalClose} onClick={() => setViewScorer(null)}>✕</button>
              </div>
            </div>

            {isEditing ? (
              <form onSubmit={handleEditSubmit} className={styles.editFormModal}>
                <label className={styles.fieldLabel}>Name</label>
                <input value={editForm.name} onChange={e => setEditForm({ ...editForm, name: e.target.value })} required />
                <label className={styles.fieldLabel}>Description</label>
                <input value={editForm.description} onChange={e => setEditForm({ ...editForm, description: e.target.value })} />
                <label className={styles.fieldLabel}>Eval Prompt</label>
                <textarea value={editForm.eval_prompt} onChange={e => setEditForm({ ...editForm, eval_prompt: e.target.value })} rows={12} required />
                <label className={styles.fieldLabel}>Pass Threshold</label>
                <input type="number" value={editForm.pass_threshold} onChange={e => setEditForm({ ...editForm, pass_threshold: Number(e.target.value) })} />
                <div className={styles.editActions}>
                  <button type="submit" className={styles.btn} disabled={updateMut.isPending}>Save</button>
                  <button type="button" className={styles.btnOutline} onClick={() => setIsEditing(false)}>Cancel</button>
                </div>
              </form>
            ) : (
              <div className={styles.scorerPreview}>
                <div className={styles.previewField}>
                  <span className={styles.fieldLabel}>Name</span>
                  <span>{viewScorer.name}</span>
                </div>
                <div className={styles.previewField}>
                  <span className={styles.fieldLabel}>Description</span>
                  <span>{viewScorer.description || '—'}</span>
                </div>
                <div className={styles.previewField}>
                  <span className={styles.fieldLabel}>Pass Threshold</span>
                  <span>{viewScorer.pass_threshold ?? 60}</span>
                </div>
                <div className={styles.previewField}>
                  <span className={styles.fieldLabel}>Tags</span>
                  <span>{viewScorer.tags.length > 0 ? viewScorer.tags.join(', ') : '—'}</span>
                </div>
                <div className={styles.previewField}>
                  <span className={styles.fieldLabel}>Created</span>
                  <span>{viewScorer.created_at}</span>
                </div>
                <div className={styles.previewPrompt}>
                  <span className={styles.fieldLabel}>Eval Prompt</span>
                  <pre className={styles.promptPre}>{viewScorer.eval_prompt}</pre>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

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
