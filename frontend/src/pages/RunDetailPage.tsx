import React, { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getRun, getRunResults, getRunSummary, startRun, streamRun, exportRunUrl } from '../api/runs'
import { listTestCases, listDatasets } from '../api/datasets'
import { listScorers } from '../api/scorers'
import { listAdapters } from '../api/adapters'
import StatusBadge from '../components/StatusBadge'
import PassFailIcon from '../components/PassFailIcon'
import type { EvalResult } from '../types'
import styles from './RunDetailPage.module.css'

function formatScore(score: any): string {
  if (typeof score === 'number') return String(score)
  const val = score?.score
  if (typeof val === 'number') return String(val)
  return '—'
}

export default function RunDetailPage() {
  const { id } = useParams<{ id: string }>()
  const runId = Number(id)
  const queryClient = useQueryClient()

  const { data: run, refetch: refetchRun } = useQuery({
    queryKey: ['run', runId],
    queryFn: () => getRun(runId),
    refetchInterval: (query) => query.state.data?.status === 'running' ? 5000 : false,
  })

  const isMultiRound = (run?.num_rounds ?? 1) > 1
  const [activeTab, setActiveTab] = useState<'summary' | number>('summary')

  // For single-round: fetch all results. For multi-round: fetch by round or all.
  const roundToFetch = isMultiRound && typeof activeTab === 'number' ? activeTab : undefined
  const { data: results } = useQuery({
    queryKey: ['results', runId, roundToFetch ?? 'all'],
    queryFn: () => getRunResults(runId, roundToFetch),
    enabled: run?.status === 'completed' || run?.status === 'failed' || run?.status === 'running',
    refetchInterval: () => run?.status === 'running' ? 5000 : false,
  })

  const { data: summary } = useQuery({
    queryKey: ['summary', runId],
    queryFn: () => getRunSummary(runId),
    enabled: isMultiRound && (run?.status === 'completed' || run?.status === 'failed'),
  })

  const { data: testCases } = useQuery({
    queryKey: ['testCases', run?.dataset_id],
    queryFn: () => listTestCases(run!.dataset_id),
    enabled: !!run?.dataset_id,
  })
  const { data: datasets } = useQuery({ queryKey: ['datasets'], queryFn: listDatasets })
  const { data: scorers } = useQuery({ queryKey: ['scorers'], queryFn: listScorers })
  const { data: adapters } = useQuery({ queryKey: ['adapters'], queryFn: listAdapters })

  const datasetName = datasets?.find(d => d.id === run?.dataset_id)?.name
  const scorerName = scorers?.find(s => s.id === run?.scorer_id)?.name
  const adapterName = adapters?.find(a => a.id === run?.adapter_id)?.name

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
          const type = (event as any).type
          const round = (event as any).round
          if (type === 'round_started' && round > 0) {
            setProgress(prev => [...prev, `--- Round ${round}/${(event as any).total_rounds} ---`])
          } else if (type === 'case_completed' && round > 0) {
            const name = (event as any).case_name || ''
            const passed = (event as any).passed ? '✓' : '✗'
            setProgress(prev => [...prev, `R${round} ${name}: ${passed}`])
          }
        },
        () => {
          setIsRunning(false)
          refetchRun()
          queryClient.invalidateQueries({ queryKey: ['results', runId] })
          queryClient.invalidateQueries({ queryKey: ['summary', runId] })
        },
      )
      setTimeout(async () => {
        if (!receivedEvents) {
          cleanup()
          try { await startRun(runId) } catch { /* run may already be started */ }
          setIsRunning(false)
          refetchRun()
          queryClient.invalidateQueries({ queryKey: ['results', runId] })
          queryClient.invalidateQueries({ queryKey: ['summary', runId] })
        }
      }, 5000)
    } catch {
      try { await startRun(runId) } catch { /* ignore */ }
      setIsRunning(false)
      refetchRun()
      queryClient.invalidateQueries({ queryKey: ['results', runId] })
      queryClient.invalidateQueries({ queryKey: ['summary', runId] })
    }
  }

  const displayResults = results ?? []
  const passedCount = displayResults.filter(r => r.passed).length
  const totalCount = displayResults.length

  return (
    <div>
      <Link to="/" className={styles.backLink}>← Back to Runs</Link>
      <div className={styles.header}>
        <h1>Run #{runId}: {run?.name || '(unnamed)'}</h1>
        <StatusBadge status={run?.status || 'pending'} />
      </div>

      <div className={styles.meta}>
        <span>Dataset: {datasetName ?? run?.dataset_id}</span>
        <span>Scorer: {scorerName ?? run?.scorer_id}</span>
        <span>Adapter: {adapterName ?? run?.adapter_id}</span>
        {isMultiRound && <span>Rounds: {run?.num_rounds} ({run?.round_mode} mode)</span>}
        {run?.started_at && <span>Started: {run.started_at}</span>}
        {run?.finished_at && <span>Finished: {run.finished_at}</span>}
      </div>

      {run?.status === 'pending' && (
        <button className={styles.startBtn} onClick={handleStart} disabled={isRunning}>
          {isRunning ? 'Running...' : `Start Run${isMultiRound ? ` (${run.num_rounds} rounds)` : ''}`}
        </button>
      )}

      {run?.status === 'running' && (
        <div className={styles.progressInfo}>
          {results ? results.length : 0}/{testCases ? testCases.length * (run?.num_rounds ?? 1) : '?'} results completed
        </div>
      )}

      {isRunning && progress.length > 0 && (
        <div className={styles.progressLog}>
          <h3>Progress</h3>
          {progress.map((p, i) => <div key={i} className={styles.logLine}>{p}</div>)}
        </div>
      )}

      {/* Tab bar for multi-round runs */}
      {isMultiRound && (run?.status === 'completed' || run?.status === 'failed') && (
        <div className={styles.tabBar}>
          <button
            className={`${styles.tab} ${activeTab === 'summary' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('summary')}
          >Summary</button>
          {Array.from({ length: run?.num_rounds ?? 1 }, (_, i) => i + 1).map(rnd => (
            <button
              key={rnd}
              className={`${styles.tab} ${activeTab === rnd ? styles.tabActive : ''}`}
              onClick={() => setActiveTab(rnd)}
            >Round {rnd}</button>
          ))}
        </div>
      )}

      {/* Summary tab for multi-round */}
      {isMultiRound && activeTab === 'summary' && summary && (
        <div className={styles.summaryCards}>
          <div className={styles.summaryCard}>
            <h3>Averaged</h3>
            <div>{summary.averaged.passed}/{summary.averaged.total} passed ({summary.averaged.pass_rate}%)</div>
            {summary.averaged.avg_score !== undefined && <div>Avg score: {summary.averaged.avg_score}</div>}
          </div>
          {summary.round_summaries.map(rs => (
            <div key={rs.round} className={styles.summaryCard}>
              <h3>Round {rs.round}</h3>
              <div>{rs.passed}/{rs.total} passed ({rs.pass_rate}%)</div>
              {rs.avg_score !== undefined && <div>Avg: {rs.avg_score}</div>}
            </div>
          ))}
        </div>
      )}

      {/* Results table */}
      {displayResults.length > 0 && (
        <>
          <div className={styles.summary}>
            <h2>
              {isMultiRound && typeof activeTab === 'number'
                ? `Round ${activeTab}: ${passedCount}/${totalCount} passed`
                : `Results: ${passedCount}/${totalCount} passed`}
              {' '}({totalCount > 0 ? ((passedCount / totalCount) * 100).toFixed(1) : 0}%)
            </h2>
            <a href={exportRunUrl(runId)} download className={styles.exportBtn}>Export CSV</a>
          </div>

          <ResultsTable
            results={displayResults}
            expandedRow={expandedRow}
            onToggleRow={(id) => setExpandedRow(expandedRow === id ? null : id)}
            showRoundColumn={isMultiRound && activeTab === 'summary'}
          />
        </>
      )}
    </div>
  )
}

function ResultsTable({ results, expandedRow, onToggleRow, showRoundColumn }: {
  results: EvalResult[]
  expandedRow: number | null
  onToggleRow: (id: number) => void
  showRoundColumn: boolean
}) {
  const colSpan = showRoundColumn ? 6 : 5
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th className={styles.colTc}>TC</th>
            {showRoundColumn && <th style={{ width: 60 }}>Round</th>}
            <th className={styles.colPass}>Pass</th>
            <th className={styles.colScore}>Score</th>
            <th className={styles.colDur}>Time</th>
            <th className={styles.colReason}>Justification</th>
          </tr>
        </thead>
        <tbody>
          {results.map(r => (
            <React.Fragment key={r.id}>
              <tr className={styles.resultRow} onClick={() => onToggleRow(r.id)}>
                <td>{r.test_case_name || r.test_case_id}</td>
                {showRoundColumn && <td>{r.round_number}</td>}
                <td><PassFailIcon passed={r.passed} /></td>
                <td>{formatScore(r.score)}</td>
                <td>{(r.duration_ms / 1000).toFixed(1)}s</td>
                <td className={styles.reasoning}>{r.judge_reasoning}</td>
              </tr>
              {expandedRow === r.id && (
                <tr className={styles.expandedRow}>
                  <td colSpan={colSpan}>
                    <div className={styles.detail}>
                      <h4>Justification</h4>
                      <p>{r.judge_reasoning}</p>
                      <h4>Score</h4>
                      <pre>{JSON.stringify(r.score, null, 2)}</pre>
                      {Array.isArray(r.agent_messages) ? (
                        <>
                          <h4>Agent Messages ({r.agent_messages.length})</h4>
                          <pre>{JSON.stringify(r.agent_messages, null, 2)}</pre>
                        </>
                      ) : (
                        <>
                          <h4>Main Agent Messages ({(r.agent_messages as any)?.main?.length ?? 0})</h4>
                          <pre>{JSON.stringify((r.agent_messages as any)?.main, null, 2)}</pre>
                          {(r.agent_messages as any)?.sub_agents?.length > 0 && (
                            <>
                              <h4>Sub-Agent Messages ({(r.agent_messages as any).sub_agents.length})</h4>
                              <pre>{JSON.stringify((r.agent_messages as any).sub_agents, null, 2)}</pre>
                            </>
                          )}
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              )}
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  )
}
