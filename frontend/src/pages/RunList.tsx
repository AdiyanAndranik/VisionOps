import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listRuns } from '../api'
import type { Run } from '../types'
import { basename } from '../format'

function duration(run: Run): string {
  if (!run.finished_at) return '–'
  const ms = Date.parse(run.finished_at) - Date.parse(run.started_at)
  return Number.isFinite(ms) ? `${(ms / 1000).toFixed(1)} s` : '–'
}

export default function RunList() {
  const [runs, setRuns] = useState<Run[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    listRuns(50, 0, controller.signal)
      .then(setRuns)
      .catch((err) => {
        if (err.name !== 'AbortError') setError(String(err.message ?? err))
      })
    return () => controller.abort()
  }, [])

  if (error) return <p className="error">Could not load runs: {error}</p>
  if (!runs) return <p className="muted">Loading…</p>
  if (runs.length === 0) {
    return <p className="muted">No runs yet. Start the worker with --db.</p>
  }

  return (
    <table>
      <thead>
        <tr>
          <th>Run</th>
          <th>Source</th>
          <th>Status</th>
          <th>Started</th>
          <th>Took</th>
          <th>Video</th>
          <th>Frames</th>
        </tr>
      </thead>
      <tbody>
        {runs.map((run) => (
          <tr key={run.id}>
            <td>
              <Link to={`/runs/${run.id}`}>#{run.id}</Link>
            </td>
            <td>{basename(run.source)}</td>
            <td>
              <span className={`badge ${run.status}`}>{run.status}</span>
            </td>
            <td>{new Date(run.started_at).toLocaleString()}</td>
            <td>{duration(run)}</td>
            <td>
              {run.width && run.height ? `${run.width}×${run.height}` : '–'}
              {run.fps ? ` @ ${run.fps} fps` : ''}
            </td>
            <td>{run.frame_count ?? '–'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}