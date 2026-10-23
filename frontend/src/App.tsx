import { Link, Route, Routes } from 'react-router-dom'
import RunList from './pages/RunList'
import RunPage from './pages/RunPage'

export default function App() {
  return (
    <div className="app">
      <header>
        <Link to="/" className="brand">
          VisionOps
        </Link>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<RunList />} />
          <Route path="/runs/:id" element={<RunPage />} />
          <Route path="*" element={<p className="muted">Page not found.</p>} />
        </Routes>
      </main>
    </div>
  )
}