import type { QuadrantSummary } from '../types'
import styles from './QuadrantBreakdown.module.css'

interface Props {
  byQuadrant: Record<string, QuadrantSummary>
}

/**
 * AE-7/AE-8: per-quadrant pass-rate breakdown.
 *
 * Renders one row per quadrant tag (cross-episode / in-episode /
 * knowledge-oriented / execution-oriented) with a horizontal pass-rate bar
 * + counts. Cases without a quadrant tag fall into "unlabeled".
 */
export default function QuadrantBreakdown({ byQuadrant }: Props) {
  const entries = Object.entries(byQuadrant).sort((a, b) => b[1].total - a[1].total)
  if (entries.length === 0) return null

  return (
    <div className={styles.panel}>
      <h3 className={styles.title}>Per-Quadrant Coverage</h3>
      <div className={styles.rows}>
        {entries.map(([label, q]) => (
          <div key={label} className={styles.row}>
            <div className={styles.label}>{label}</div>
            <div className={styles.barTrack}>
              <div
                className={styles.barFill}
                style={{ width: `${q.pass_rate}%` }}
              />
              <span className={styles.barText}>
                {q.passed}/{q.total} ({q.pass_rate.toFixed(0)}%)
                {q.avg_score !== undefined && ` · avg ${q.avg_score}`}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
