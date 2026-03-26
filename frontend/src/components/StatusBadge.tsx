import styles from './StatusBadge.module.css'

interface Props { status: string }

export default function StatusBadge({ status }: Props) {
  const cls = styles[status] || styles.default
  return <span className={`${styles.badge} ${cls}`}>{status}</span>
}
