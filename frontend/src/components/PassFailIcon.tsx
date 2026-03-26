import styles from './PassFailIcon.module.css'

interface Props { passed: boolean }

export default function PassFailIcon({ passed }: Props) {
  return (
    <span className={passed ? styles.pass : styles.fail}>
      {passed ? '\u2713' : '\u2717'}
    </span>
  )
}
