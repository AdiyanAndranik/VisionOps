import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { listRuns } from '../api'
import { basename } from '../format'
import type { Run } from '../types'

function videoSeconds(run: Run): number | null {
  return run.fps && run.frame_count ? run.frame_count / run.fps : null
}

function fmtDuration(s: number): string {
  return s >= 60 ? `${(s / 60).toFixed(1)} min` : `${s.toFixed(0)} s`
}

function RunCard({ run }: { run: Run }) {
  const [noThumb, setNoThumb] = useState(false)
  const lengthS = videoSeconds(run)
  const tookS = run.finished_at
    ? (new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()) / 1000
    : null
  return (
    <Link to={`/runs/${run.id}`} className="run-card">
      <div className="run-thumb-wrap">
        {noThumb ? (
          <div className="run-thumb empty">no preview</div>
        ) : (
          <img
            className="run-thumb"
            src={`/api/runs/${run.id}/frame`}
            alt=""
            loading="lazy"
            onError={() => setNoThumb(true)}
          />
        )}
        <span className={`badge ${run.status}`}>{run.status}</span>
        {lengthS !== null && <span className="dur">{lengthS.toFixed(1)} s</span>}
      </div>
      <div className="run-body">
        <div className="run-title">{basename(run.source)}</div>
        <div className="run-meta">
          Run #{run.id} · {new Date(run.started_at).toLocaleString()}
        </div>
        <div className="run-meta">
          {run.width && run.height ? `${run.width}×${run.height}` : ''}
          {run.fps ? ` @ ${run.fps} fps` : ''}
          {tookS !== null ? ` · processed in ${tookS.toFixed(1)} s` : ''}
        </div>
        <div className="run-stats">
          <div>
            <div className="v">{run.line_crossings ?? '–'}</div>
            <div className="l">crossings</div>
          </div>
          <div>
            <div className="v">{run.zone_visits ?? '–'}</div>
            <div className="l">zone visits</div>
          </div>
          <div>
            <div className="v">{run.events ?? '–'}</div>
            <div className="l">events</div>
          </div>
        </div>
      </div>
    </Link>
  )
}

export default function RunList() {
  const [runs, setRuns] = useState<Run[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const ctrl = new AbortController()
    listRuns(50, 0, ctrl.signal)
      .then(setRuns)
      .catch((e: unknown) => {
        if (ctrl.signal.aborted) return
        setError(e instanceof Error ? e.message : String(e))
      })
    return () => ctrl.abort()
  }, [])

  const totals = useMemo(() => {
    const list = runs ?? []
    return {
      runs: list.length,
      seconds: list.reduce((s, r) => s + (videoSeconds(r) ?? 0), 0),
      crossings: list.reduce((s, r) => s + (r.line_crossings ?? 0), 0),
      events: list.reduce((s, r) => s + (r.events ?? 0), 0),
    }
  }, [runs])

  if (error) return <p className="error">Could not load runs: {error}</p>
  if (!runs) return <p className="muted">Loading…</p>

  return (
    <>
      <section className="hero">
        <h1>Video analytics for CCTV</h1>
        <p>
          People tracking, line crossing counts and zone dwell time from camera footage. Open a
          run to watch the annotated video, jump to any event and see the heatmap.
        </p>
        <div className="hero-stats">
          <div>
            <div className="v">{totals.runs}</div>
            <div className="l">runs</div>
          </div>
          <div>
            <div className="v">{fmtDuration(totals.seconds)}</div>
            <div className="l">video analysed</div>
          </div>
          <div>
            <div className="v">{totals.crossings}</div>
            <div className="l">line crossings</div>
          </div>
          <div>
            <div className="v">{totals.events}</div>
            <div className="l">events</div>
          </div>
        </div>
      </section>

      <h3>Runs, newest first</h3>
      {runs.length === 0 ? (
        <p className="muted">
          No runs yet. Start the worker with{' '}
          <code>python -m src.worker.main --video data/demo1.mp4 --db --annotate</code>
        </p>
      ) : (
        <div className="run-grid">
          {runs.map((r) => (
            <RunCard key={r.id} run={r} />
          ))}
        </div>
      )}
    </>
  )
}