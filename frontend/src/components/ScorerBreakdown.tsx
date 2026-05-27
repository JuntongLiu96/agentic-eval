import type { ScorerSummary, Scorer } from '../types'
import styles from './QuadrantBreakdown.module.css'

interface Props {
  byScorer: Record<string, ScorerSummary>
  scorers?: Scorer[]
}

/**
 * AE-13: per-scorer pass-rate breakdown for multi-scorer runs.
 */
export default function ScorerBreakdown({ byScorer, scorers }: Props) {
  const entries = Object.entries(byScorer).sort((a, b) => b[1].total - a[1].total)
  if (entries.length === 0) return null

  return (
    <div className={styles.panel}>
      <h3 className={styles.title}>Per-Scorer Aggregates</h3>
      <div className={styles.rows}>
        {entries.map(([label, s]) => {
          const named = scorers?.find(x => x.id === s.scorer_id)?.name ?? label
          return (
            <div key={label} className={styles.row}>
              <div className={styles.label}>{named}</div>
              <div className={styles.barTrack}>
                <div className={styles.barFill} style={{ width: `${s.pass_rate}%` }} />
                <span className={styles.barText}>
                  {s.passed}/{s.total} ({s.pass_rate.toFixed(0)}%)
                  {s.avg_score !== undefined && ` · avg ${s.avg_score}`}
                </span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
