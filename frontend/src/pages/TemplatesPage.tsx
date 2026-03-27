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
              <span className={styles.badge}>{t.category}</span>
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
