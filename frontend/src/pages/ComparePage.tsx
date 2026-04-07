import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { listRuns, compareRuns } from '../api/runs'
import PassFailIcon from '../components/PassFailIcon'
import styles from './ComparePage.module.css'

export default function ComparePage() {
  const { data: runs } = useQuery({ queryKey: ['runs'], queryFn: listRuns })
  const [run1, setRun1] = useState<number>(0)
  const [run2, setRun2] = useState<number>(0)

  const { data: comparison, isLoading, refetch } = useQuery({
    queryKey: ['compare', run1, run2],
    queryFn: () => compareRuns(run1, run2),
    enabled: false,
  })

  function handleCompare() {
    if (run1 && run2 && run1 !== run2) refetch()
  }

  const completedRuns = runs?.filter(r => r.status === 'completed') || []

  return (
    <div>
      <Link to="/" className={styles.backLink}>← Back to Runs</Link>
      <h1>Compare Runs</h1>

      <div className={styles.selectors}>
        <select value={run1} onChange={e => setRun1(Number(e.target.value))}>
          <option value={0} disabled>Select Run 1</option>
          {completedRuns.map(r => <option key={r.id} value={r.id}>#{r.id}: {r.name || 'unnamed'}</option>)}
        </select>
        <span className={styles.vs}>vs</span>
        <select value={run2} onChange={e => setRun2(Number(e.target.value))}>
          <option value={0} disabled>Select Run 2</option>
          {completedRuns.map(r => <option key={r.id} value={r.id}>#{r.id}: {r.name || 'unnamed'}</option>)}
        </select>
        <button className={styles.btn} onClick={handleCompare} disabled={!run1 || !run2 || run1 === run2}>Compare</button>
      </div>

      {isLoading && <div>Loading comparison...</div>}

      {comparison && (
        <>
          <div className={styles.summaryRow}>
            <div className={styles.summaryCard}>
              <h3>Run #{comparison.run1.id}</h3>
              <p>{comparison.run1.summary.passed}/{comparison.run1.summary.total} passed</p>
              <p className={styles.rate}>{(comparison.run1.summary.pass_rate * 100).toFixed(1)}%</p>
              {comparison.run1.summary.avg_score != null && <p>Avg score: {comparison.run1.summary.avg_score.toFixed(2)}</p>}
            </div>
            <div className={styles.summaryCard}>
              <h3>Run #{comparison.run2.id}</h3>
              <p>{comparison.run2.summary.passed}/{comparison.run2.summary.total} passed</p>
              <p className={styles.rate}>{(comparison.run2.summary.pass_rate * 100).toFixed(1)}%</p>
              {comparison.run2.summary.avg_score != null && <p>Avg score: {comparison.run2.summary.avg_score.toFixed(2)}</p>}
            </div>
          </div>

          <table className={styles.table}>
            <thead>
              <tr><th>Test Case</th><th>Run 1</th><th>Run 2</th><th>Run 1 Score</th><th>Run 2 Score</th><th>Δ</th><th>Changed</th></tr>
            </thead>
            <tbody>
              {comparison.comparisons.map(c => (
                <tr key={c.test_case_id} className={c.changed ? styles.changed : ''}>
                  <td>{c.test_case_id}</td>
                  <td><PassFailIcon passed={c.run1_passed} /></td>
                  <td><PassFailIcon passed={c.run2_passed} /></td>
                  <td>{c.run1_score != null ? c.run1_score : '—'}</td>
                  <td>{c.run2_score != null ? c.run2_score : '—'}</td>
                  <td>{c.run1_score != null && c.run2_score != null ? (
                    <span style={{ color: c.run2_score - c.run1_score > 0 ? '#22c55e' : c.run2_score - c.run1_score < 0 ? '#ef4444' : '#94a3b8' }}>
                      {c.run2_score - c.run1_score > 0 ? '+' : ''}{(c.run2_score - c.run1_score).toFixed(2)}
                    </span>
                  ) : '—'}</td>
                  <td>{c.changed ? <span className={styles.changedLabel}>CHANGED</span> : ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  )
}
