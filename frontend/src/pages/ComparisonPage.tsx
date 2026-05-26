import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { comparisonRun } from '../api/runs'
import type { ComparisonRunResponse } from '../types'
import styles from './ComparisonPage.module.css'

/**
 * AE-10: cold-vs-warm delta panel for paired runs.
 *
 * Wraps POST /api/runs/comparison (AE-5). Enter a baseline run id (cold)
 * and a warm run id; we render per-test-case delta rows. Highlights
 * n_reduction since that's the headline metric for EvoMem cases (CA-009 vs
 * CA-001 etc.).
 */
export default function ComparisonPage() {
  const [baseline, setBaseline] = useState('')
  const [warm, setWarm] = useState('')
  const [metrics, setMetrics] = useState('n_reduction,files_recall,trajectory_steps')

  const mutation = useMutation<ComparisonRunResponse>({
    mutationFn: () =>
      comparisonRun(
        Number(baseline),
        Number(warm),
        metrics.split(',').map(m => m.trim()).filter(Boolean),
      ),
  })

  const data = mutation.data
  const avgN = data?.pairs.length
    ? data.pairs.reduce(
        (acc, p) => acc + ((p.deltas.n_reduction as number | undefined) ?? 0), 0,
      ) / data.pairs.length
    : null

  return (
    <div>
      <Link to="/" className={styles.backLink}>← Back to Runs</Link>
      <h1>Cold-vs-Warm Comparison</h1>
      <p className={styles.lede}>
        Pair a baseline (cold) run with a warm run to see per-test-case
        deltas on numeric agent_metadata fields. Backed by{' '}
        <code>POST /api/runs/comparison</code> (AE-5).
      </p>

      <form
        className={styles.form}
        onSubmit={e => { e.preventDefault(); mutation.mutate() }}
      >
        <label>
          Baseline run id
          <input value={baseline} onChange={e => setBaseline(e.target.value)} />
        </label>
        <label>
          Warm run id
          <input value={warm} onChange={e => setWarm(e.target.value)} />
        </label>
        <label className={styles.metricsLabel}>
          Metrics (comma-sep)
          <input
            value={metrics}
            onChange={e => setMetrics(e.target.value)}
            placeholder="n_reduction,files_recall"
          />
        </label>
        <button type="submit" disabled={!baseline || !warm || mutation.isPending}>
          {mutation.isPending ? 'Computing…' : 'Compare'}
        </button>
      </form>

      {mutation.isError && (
        <div className={styles.error}>
          {(mutation.error as Error)?.message || 'Comparison failed'}
        </div>
      )}

      {data && (
        <>
          <div className={styles.headline}>
            {data.pairs.length} test case(s) paired ·{' '}
            <Link to={`/runs/${data.baseline_run_id}`}>run {data.baseline_run_id}</Link>{' '}
            vs <Link to={`/runs/${data.warm_run_id}`}>run {data.warm_run_id}</Link>
            {avgN !== null && (
              <span className={styles.avgN}>
                {' · avg N-reduction: '}
                <strong>{(avgN * 100).toFixed(1)}%</strong>
              </span>
            )}
          </div>

          <table className={styles.table}>
            <thead>
              <tr>
                <th>Test case</th>
                {data.metrics.map(m => <th key={m}>Δ {m}</th>)}
              </tr>
            </thead>
            <tbody>
              {data.pairs.map(p => (
                <tr key={p.test_case_id}>
                  <td>{p.test_case_id}</td>
                  {data.metrics.map(m => {
                    const v = p.deltas[m]
                    const cls =
                      m === 'n_reduction'
                        ? v !== undefined && v > 0 ? styles.good : v !== undefined && v < 0 ? styles.bad : ''
                        : v !== undefined && v > 0 ? styles.good : v !== undefined && v < 0 ? styles.bad : ''
                    return (
                      <td key={m} className={cls}>
                        {typeof v === 'number'
                          ? (m === 'n_reduction' ? `${(v * 100).toFixed(1)}%` : v.toFixed(3))
                          : '—'}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  )
}
