import { Routes, Route, Link, useLocation } from 'react-router-dom'
import styles from './App.module.css'

import DatasetsPage from './pages/DatasetsPage'
import DatasetDetailPage from './pages/DatasetDetailPage'
import ScorersPage from './pages/ScorersPage'
import AdaptersPage from './pages/AdaptersPage'
import RunsPage from './pages/RunsPage'
import RunDetailPage from './pages/RunDetailPage'
import ComparePage from './pages/ComparePage'

export default function App() {
  const location = useLocation()

  function isActive(path: string) {
    return location.pathname === path || location.pathname.startsWith(path + '/')
  }

  return (
    <div className={styles.layout}>
      <nav className={styles.sidebar}>
        <h2 className={styles.logo}>AgenticEval</h2>
        <ul className={styles.navList}>
          <li><Link to="/" className={isActive('/runs') || location.pathname === '/' ? styles.active : ''}>Runs</Link></li>
          <li><Link to="/datasets" className={isActive('/datasets') ? styles.active : ''}>Datasets</Link></li>
          <li><Link to="/scorers" className={isActive('/scorers') ? styles.active : ''}>Scorers</Link></li>
          <li><Link to="/adapters" className={isActive('/adapters') ? styles.active : ''}>Adapters</Link></li>
        </ul>
      </nav>
      <main className={styles.content}>
        <Routes>
          <Route path="/" element={<RunsPage />} />
          <Route path="/datasets" element={<DatasetsPage />} />
          <Route path="/datasets/:id" element={<DatasetDetailPage />} />
          <Route path="/scorers" element={<ScorersPage />} />
          <Route path="/adapters" element={<AdaptersPage />} />
          <Route path="/runs/compare" element={<ComparePage />} />
          <Route path="/runs/:id" element={<RunDetailPage />} />
        </Routes>
      </main>
    </div>
  )
}
