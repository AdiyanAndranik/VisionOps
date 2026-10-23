import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { EVENTS_LIMIT } from '../api'
import FrameView from '../components/FrameView'
import { basename, num } from '../format'
import type { EventType } from '../types'
import { useRunLive } from '../useRunLive'

type Filter = EventType | 'all'
type SortKey = 'time_s' | 'track_id' | 'dwell_s'

const FILTERS: Filter[] = ['all', 'line_cross', 'zone_enter', 'zone_exit']

const TYPE_LABEL: Record<EventType, string> = {
  line_cross: 'line cross',
  zone_enter: 'zone enter',
  zone_exit: 'zone exit',
}

export default function RunPage() {
  const { id } = useParams()
  const runId = Number(id)
  if (!Number.isInteger(runId) || runId < 1) {
    return <p className="error">Bad run id.</p>
  }
  // key resets all state when the id changes
  return <RunView key={runId} runId={runId} />
}

function RunView({ runId }: { runId: number }) {
  const { run, summary, events, loaded, error, conn } = useRunLive(runId)

  const [filter, setFilter] = useState<Filter>('all')
  const [trackQuery, setTrackQuery] = useState('')
  const [sortKey, setSortKey] = useState<SortKey>('time_s')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')

  const visible = useMemo(() => {
    const track = trackQuery.trim() === '' ? null : Number(trackQuery)
    const dir = sortDir === 'asc' ? 1 : -1
    return events
      .filter(
        (e) => (filter === 'all' || e.type === filter) && (track === null || e.track_id === track),
      )
      .sort((a, b) => {
        const av = a[sortKey]
        const bv = b[sortKey]
        if (av == null && bv == null) return a.id - b.id
        if (av == null) return 1 // nulls always last
        if (bv == null) return -1
        return (Number(av) - Number(bv)) * dir || a.id - b.id
      })
  }, [events, filter, trackQuery, sortKey, sortDir])

  const back = (
    <p>
      <Link to="/">← Runs</Link>
    </p>
  )

  if (error) {
    return (
      <>
        {back}
        <p className="error">
          Could not load run #{runId}: {error}
        </p>
      </>
    )
  }
  if (!run || !summary || !loaded) return <p className="muted">Loading…</p>

  const lineTotal = summary.line_crossings.reduce((s, l) => s + l.count, 0)
  const visitTotal = summary.zones.reduce((s, z) => s + z.visits, 0)
  const eventTotal = Object.values(summary.events).reduce((s, n) => s + (n ?? 0), 0)
  const lengthS = run.fps && run.frame_count ? run.frame_count / run.fps : null

  function toggleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  const header = (key: SortKey, label: string) => (
    <th className="sortable num" onClick={() => toggleSort(key)}>
      {label}
      {sortKey === key ? (sortDir === 'asc' ? ' ▲' : ' ▼') : ''}
    </th>
  )

  return (
    <>
      {back}
      <div className="page-head">
        <h2>Run #{run.id}</h2>
        <span className={`badge ${run.status}`}>{run.status}</span>
        {run.status === 'running' && (
          <span className={`live ${conn}`}>{conn === 'live' ? '● live' : '○ connecting…'}</span>
        )}
        <span className="muted">
          {basename(run.source)} · {new Date(run.started_at).toLocaleString()}
          {run.width && run.height ? ` · ${run.width}×${run.height}` : ''}
          {run.fps ? ` @ ${run.fps} fps` : ''}
        </span>
      </div>

      <div className="cards">
        <div className="card">
          <div className="label">Video length</div>
          <div className="value">{lengthS === null ? '–' : `${num(lengthS, 1)} s`}</div>
        </div>
        <div className="card">
          <div className="label">Line crossings</div>
          <div className="value">{lineTotal}</div>
        </div>
        <div className="card">
          <div className="label">Completed zone visits</div>
          <div className="value">{visitTotal}</div>
        </div>
        <div className="card">
          <div className="label">Events</div>
          <div className="value">{eventTotal}</div>
        </div>
      </div>

      <FrameView run={run} events={events} />

      <div className="grid2">
        <section>
          <h3>Lines</h3>
          <table>
            <thead>
              <tr>
                <th>Line</th>
                <th>Direction</th>
                <th className="num">Count</th>
              </tr>
            </thead>
            <tbody>
              {summary.line_crossings.length === 0 && (
                <tr>
                  <td colSpan={3} className="muted">
                    No crossings.
                  </td>
                </tr>
              )}
              {summary.line_crossings.map((l) => (
                <tr key={`${l.line}-${l.direction}`}>
                  <td>{l.line}</td>
                  <td>{l.direction}</td>
                  <td className="num">{l.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section>
          <h3>Zones</h3>
          <table>
            <thead>
              <tr>
                <th>Zone</th>
                <th className="num">Visits</th>
                <th className="num">Avg dwell</th>
                <th className="num">Max dwell</th>
              </tr>
            </thead>
            <tbody>
              {summary.zones.length === 0 && (
                <tr>
                  <td colSpan={4} className="muted">
                    No visits.
                  </td>
                </tr>
              )}
              {summary.zones.map((z) => (
                <tr key={z.zone}>
                  <td>{z.zone}</td>
                  <td className="num">{z.visits}</td>
                  <td className="num">{num(z.avg_dwell_s)} s</td>
                  <td className="num">{num(z.max_dwell_s)} s</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>

      <h3>Events</h3>
      <div className="toolbar">
        {FILTERS.map((f) => (
          <button
            key={f}
            type="button"
            className={`chip${filter === f ? ' active' : ''}`}
            onClick={() => setFilter(f)}
          >
            {f === 'all' ? 'all' : TYPE_LABEL[f]}
          </button>
        ))}
        <input
          type="text"
          inputMode="numeric"
          placeholder="track id"
          value={trackQuery}
          onChange={(e) => setTrackQuery(e.target.value)}
        />
        <span className="muted">
          {visible.length} of {events.length}
        </span>
      </div>
      {events.length >= EVENTS_LIMIT && (
        <p className="muted">Showing the first {EVENTS_LIMIT} events only.</p>
      )}

      <table>
        <thead>
          <tr>
            {header('time_s', 'Time (s)')}
            <th>Type</th>
            {header('track_id', 'Track')}
            <th>Zone / line</th>
            <th>Direction</th>
            {header('dwell_s', 'Dwell (s)')}
            <th className="num">Position</th>
          </tr>
        </thead>
        <tbody>
          {visible.length === 0 && (
            <tr>
              <td colSpan={7} className="muted">
                No events match.
              </td>
            </tr>
          )}
          {visible.map((e) => (
            <tr key={e.id}>
              <td className="num">{num(e.time_s)}</td>
              <td>
                <span className={`tag ${e.type}`}>{TYPE_LABEL[e.type]}</span>
              </td>
              <td className="num">{e.track_id}</td>
              <td>{e.zone ?? e.line ?? '–'}</td>
              <td>{e.direction ?? '–'}</td>
              <td className="num">{num(e.dwell_s)}</td>
              <td className="num">
                {e.x === null || e.y === null ? '–' : `${num(e.x, 0)}, ${num(e.y, 0)}`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  )
}