import type { RoundSummary } from '../types'
import styles from './SeriesChart.module.css'

interface Props {
  rounds: RoundSummary[]
}

/**
 * AE-9: pass-rate + avg-score across rounds for multi-round runs.
 *
 * Tiny dependency-free SVG line chart. Two series — pass_rate (left axis,
 * 0-100) and avg_score (right axis, normalized). Use for reinforcement
 * cases (CA-003 confidence rise) and consistency runs.
 */
export default function SeriesChart({ rounds }: Props) {
  const points = rounds.filter(r => r.round > 0)
  if (points.length < 2) return null

  const W = 600, H = 200, PAD = 32
  const xs = (i: number) =>
    PAD + (i * (W - 2 * PAD)) / Math.max(1, points.length - 1)
  const ysRate = (v: number) => H - PAD - (v / 100) * (H - 2 * PAD)

  const hasScores = points.some(p => p.avg_score !== undefined)
  const scoreMax = hasScores
    ? Math.max(...points.map(p => p.avg_score ?? 0))
    : 1
  const ysScore = (v: number) =>
    H - PAD - (v / Math.max(scoreMax, 1)) * (H - 2 * PAD)

  const ratePath = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${xs(i)},${ysRate(p.pass_rate)}`)
    .join(' ')
  const scorePath = hasScores
    ? points
        .map((p, i) =>
          p.avg_score !== undefined
            ? `${i === 0 ? 'M' : 'L'}${xs(i)},${ysScore(p.avg_score)}`
            : ''
        )
        .filter(Boolean)
        .join(' ')
    : ''

  return (
    <div className={styles.panel}>
      <h3 className={styles.title}>Per-Round Series</h3>
      <svg viewBox={`0 0 ${W} ${H}`} className={styles.svg}>
        {/* axes */}
        <line x1={PAD} y1={H - PAD} x2={W - PAD} y2={H - PAD} stroke="#bbb" />
        <line x1={PAD} y1={PAD} x2={PAD} y2={H - PAD} stroke="#bbb" />
        {/* gridlines (25/50/75/100) */}
        {[25, 50, 75, 100].map(v => (
          <g key={v}>
            <line
              x1={PAD} x2={W - PAD}
              y1={ysRate(v)} y2={ysRate(v)}
              stroke="#eee"
            />
            <text x={4} y={ysRate(v) + 3} fontSize="10" fill="#888">{v}</text>
          </g>
        ))}
        {/* pass-rate line */}
        <path d={ratePath} fill="none" stroke="#1976d2" strokeWidth="2" />
        {points.map((p, i) => (
          <circle
            key={`r${i}`}
            cx={xs(i)} cy={ysRate(p.pass_rate)} r="3" fill="#1976d2"
          >
            <title>Round {p.round}: {p.pass_rate}% pass</title>
          </circle>
        ))}
        {/* score line (if present) */}
        {hasScores && scorePath && (
          <>
            <path d={scorePath} fill="none" stroke="#f57c00" strokeWidth="2" strokeDasharray="4 2" />
            {points.map((p, i) =>
              p.avg_score !== undefined ? (
                <circle
                  key={`s${i}`}
                  cx={xs(i)} cy={ysScore(p.avg_score)} r="3" fill="#f57c00"
                >
                  <title>Round {p.round}: avg score {p.avg_score}</title>
                </circle>
              ) : null
            )}
          </>
        )}
        {/* x-axis round labels */}
        {points.map((p, i) => (
          <text
            key={`x${i}`}
            x={xs(i)} y={H - PAD + 14}
            fontSize="10" fill="#666" textAnchor="middle"
          >R{p.round}</text>
        ))}
      </svg>
      <div className={styles.legend}>
        <span><span className={styles.swatchRate} /> pass rate (%)</span>
        {hasScores && <span><span className={styles.swatchScore} /> avg score</span>}
      </div>
    </div>
  )
}
