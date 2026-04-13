import { useState } from "react"
import type { BooleanRubricResult } from "../types"
import styles from "./BooleanRubricView.module.css"

interface Props {
  rubric: BooleanRubricResult
}

export default function BooleanRubricView({ rubric }: Props) {
  const [showItems, setShowItems] = useState(false)

  const criticalSet = new Set(rubric.critical_failures ?? [])

  return (
    <div className={styles.container}>
      {/* Verdict + Overall Pass Rate */}
      <div className={styles.header}>
        <span className={`${styles.verdict} ${verdictClass(rubric.verdict)}`}>
          {rubric.verdict.toUpperCase().replace(/_/g, " ")}
        </span>
        <span className={styles.passRate}>
          {(rubric.overall_pass_rate * 100).toFixed(0)}% overall
        </span>
      </div>

      {/* Dimensions summary table */}
      {rubric.dimensions && Object.keys(rubric.dimensions).length > 0 && (
        <table className={styles.dimTable}>
          <thead>
            <tr>
              <th>Dimension</th>
              <th>Passed</th>
              <th>Rate</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(rubric.dimensions).map(([name, dim]) => (
              <tr key={name}>
                <td>{formatDimensionName(name)}</td>
                <td>{dim.passed}/{dim.total}</td>
                <td>
                  <div className={styles.rateBarOuter}>
                    <div
                      className={styles.rateBarInner}
                      style={{
                        width: `${(dim.rate * 100).toFixed(0)}%`,
                        backgroundColor: rateColor(dim.rate),
                      }}
                    />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* Critical Failures */}
      {rubric.critical_failures?.length > 0 && (
        <div className={styles.criticalBox}>
          <strong>Critical failures:</strong>{" "}
          {rubric.critical_failures.join(", ")}
        </div>
      )}

      {/* Item-level details (collapsible) */}
      {rubric.items && Object.keys(rubric.items).length > 0 && (
        <div className={styles.itemsSection}>
          <button
            className={styles.toggleBtn}
            onClick={() => setShowItems((v) => !v)}
          >
            {showItems ? "\u25BE" : "\u25B8"} Items ({Object.keys(rubric.items).length})
          </button>

          {showItems && (
            <div className={styles.itemsList}>
              {Object.entries(rubric.items).map(([id, item]) => (
                <div
                  key={id}
                  className={`${styles.item} ${
                    criticalSet.has(id) ? styles.itemCritical : ""
                  }`}
                >
                  <span className={item.pass ? styles.iconPass : styles.iconFail}>
                    {item.pass ? "\u2713" : "\u2717"}
                  </span>
                  <span className={styles.itemId}>{id}</span>
                  <span className={styles.itemReason}>{item.reason}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function verdictClass(verdict: string): string {
  if (verdict === "pass") return styles.verdictPass
  if (verdict === "fail") return styles.verdictFail
  return styles.verdictWarn
}

function formatDimensionName(name: string): string {
  return name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
}

function rateColor(rate: number): string {
  if (rate >= 0.8) return "#4ade80"
  if (rate >= 0.5) return "#fbbf24"
  return "#f87171"
}
