import React, { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getRun, getRunResults, startRun, streamRun, exportRunUrl } from '../api/runs'
import StatusBadge from '../components/StatusBadge'
import PassFailIcon from '../components/PassFailIcon'
import styles from './RunDetailPage.module.css'

export default function RunDetailPage() {
  const { id } = useParams<{ id: string }>()
  const runId = Number(id)
  const queryClient = useQueryClient()

  const { data: run, refetch: refetchRun } = useQuery({ queryKey: ['run', runId], queryFn: () => getRun(runId) })
  const { data: results } = useQuery({
    queryKey: ['results', runId],
    queryFn: () => getRunResults(runId),
    enabled: run?.status === 'completed' || run?.status === 'failed',
  })

  const [isRunning, setIsRunning] = useState(false)
  const [progress, setProgress] = useState<string[]>([])
  const [expandedRow, setExpandedRow] = useState<number | null>(null)

  async function handleStart() {
    setIsRunning(true)
    setProgress([])
    try {
      let receivedEvents = false
      const cleanup = streamRun(
        runId,
        (event) => {
          receivedEvents = true
          setProgress(prev => [...prev, JSON.stringify(event)])
        },
        () => {
          setIsRunning(false)
          refetchRun()
          queryClient.invalidateQueries({ queryKey: ['results', runId] })
        },
      )
      // Fallback: if SSE doesn't connect after 5s, use direct start
      setTimeout(async () => {
        if (!receivedEvents) {
          cleanup()
          try {
            await startRun(runId)
          } catch { /* run may already be started by stream */ }
          setIsRunning(false)
          refetchRun()
          queryClient.invalidateQueries({ queryKey: ['results', runId] })
        }
      }, 5000)
    } catch {
      try {
        await startRun(runId)
      } catch { /* ignore */ }
      setIsRunning(false)
      refetchRun()
      queryClient.invalidateQueries({ queryKey: ['results', runId] })
    }
  }

  const passedCount = results?.filter(r => r.passed).length ?? 0
  const totalCount = results?.length ?? 0

  return (
    <div>
      <Link to="/" className={styles.backLink}>← Back to Runs</Link>
      <div className={styles.header}>
        <h1>Run #{runId}: {run?.name || '(unnamed)'}</h1>
        <StatusBadge status={run?.status || 'pending'} />
      </div>

      <div className={styles.meta}>
        <span>Dataset: {run?.dataset_id}</span>
        <span>Scorer: {run?.scorer_id}</span>
        <span>Adapter: {run?.adapter_id}</span>
        {run?.started_at && <span>Started: {run.started_at}</span>}
        {run?.finished_at && <span>Finished: {run.finished_at}</span>}
      </div>

      {run?.status === 'pending' && (
        <button className={styles.startBtn} onClick={handleStart} disabled={isRunning}>
          {isRunning ? 'Running...' : 'Start Run'}
        </button>
      )}

      {isRunning && progress.length > 0 && (
        <div className={styles.progressLog}>
          <h3>Progress</h3>
          {progress.map((p, i) => <div key={i} className={styles.logLine}>{p}</div>)}
        </div>
      )}

      {results && results.length > 0 && (
        <>
          <div className={styles.summary}>
            <h2>Results: {passedCount}/{totalCount} passed ({totalCount > 0 ? ((passedCount / totalCount) * 100).toFixed(1) : 0}%)</h2>
            <a href={exportRunUrl(runId)} download className={styles.exportBtn}>Export CSV</a>
          </div>

          <table className={styles.table}>
            <thead>
              <tr><th>Test Case</th><th>Passed</th><th>Duration</th><th>Reasoning</th></tr>
            </thead>
            <tbody>
              {results.map(r => (
                <React.Fragment key={r.id}>
                  <tr className={styles.resultRow} onClick={() => setExpandedRow(expandedRow === r.id ? null : r.id)}>
                    <td>{r.test_case_id}</td>
                    <td><PassFailIcon passed={r.passed} /></td>
                    <td>{r.duration_ms}ms</td>
                    <td className={styles.reasoning}>{r.judge_reasoning.slice(0, 80)}...</td>
                  </tr>
                  {expandedRow === r.id && (
                    <tr className={styles.expandedRow}>
                      <td colSpan={4}>
                        <div className={styles.detail}>
                          <h4>Full Reasoning</h4>
                          <p>{r.judge_reasoning}</p>
                          <h4>Score</h4>
                          <pre>{JSON.stringify(r.score, null, 2)}</pre>
                          <h4>Agent Messages</h4>
                          <pre>{JSON.stringify(r.agent_messages, null, 2)}</pre>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  )
}
