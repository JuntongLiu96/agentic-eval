import { Routes, Route, Link } from 'react-router-dom'
import styles from './App.module.css'

export default function App() {
  return (
    <div className={styles.layout}>
      <nav className={styles.sidebar}>
        <h2 className={styles.logo}>AgenticEval</h2>
        <ul className={styles.navList}>
          <li><Link to="/">Runs</Link></li>
          <li><Link to="/datasets">Datasets</Link></li>
          <li><Link to="/scorers">Scorers</Link></li>
          <li><Link to="/templates">Templates</Link></li>
          <li><Link to="/adapters">Adapters</Link></li>
        </ul>
      </nav>
      <main className={styles.content}>
        <Routes>
          <Route path="/" element={<div>Runs page coming soon</div>} />
          <Route path="/datasets" element={<div>Datasets page coming soon</div>} />
          <Route path="/scorers" element={<div>Scorers page coming soon</div>} />
          <Route path="/templates" element={<div>Templates page coming soon</div>} />
          <Route path="/adapters" element={<div>Adapters page coming soon</div>} />
        </Routes>
      </main>
    </div>
  )
}
