import { useState } from 'react'
import type { RunDetail, RunEvent } from '../types'

type Mode = 'frame' | 'heatmap'

const ZONE_COLORS = ['#5b9cff', '#3fb68b', '#e0a93b', '#b48cff', '#e5645b']
const LINE_COLOR = '#ff4fd8'

const labelStyle = { paintOrder: 'stroke' } as const

export default function FrameView({ run, events }: { run: RunDetail; events: RunEvent[] }) {
  const [mode, setMode] = useState<Mode>('frame')
  const [showShapes, setShowShapes] = useState(true)
  const [showCrossings, setShowCrossings] = useState(false)
  const [failedSrc, setFailedSrc] = useState<string | null>(null)

  const w = run.width ?? 1920
  const h = run.height ?? 1080
  const zones = run.config?.zones?.zones ?? []
  const lines = run.config?.lines?.lines ?? []
  const crossings = events.filter((e) => e.type === 'line_cross' && e.x !== null && e.y !== null)

  const heatmapReady = run.status === 'done'
  const active: Mode = mode === 'heatmap' && !heatmapReady ? 'frame' : mode
  // the status in the query string makes the browser refetch when a run finishes
  const src = `/api/runs/${run.id}/${active === 'frame' ? 'frame' : 'heatmap'}?s=${run.status}`
  const missing = failedSrc === src

  return (
    <section className="viewer-section">
      <div className="toolbar">
        <button
          type="button"
          className={`chip${active === 'frame' ? ' active' : ''}`}
          onClick={() => setMode('frame')}
        >
          frame
        </button>
        <button
          type="button"
          className={`chip${active === 'heatmap' ? ' active' : ''}`}
          disabled={!heatmapReady}
          title={heatmapReady ? '' : 'available when the run is done'}
          onClick={() => setMode('heatmap')}
        >
          heatmap
        </button>
        <label className="check">
          <input
            type="checkbox"
            checked={showShapes}
            onChange={(e) => setShowShapes(e.target.checked)}
          />
          zones and lines
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={showCrossings}
            onChange={(e) => setShowCrossings(e.target.checked)}
          />
          crossings
        </label>
      </div>

      {missing ? (
        <p className="muted">No image for this run. Runs from before this feature have none.</p>
      ) : (
        <div className="viewer" style={{ aspectRatio: `${w} / ${h}` }}>
          <img src={src} alt="" onError={() => setFailedSrc(src)} />
          <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
            {showShapes &&
              zones.map((z, i) => {
                const color = ZONE_COLORS[i % ZONE_COLORS.length]
                const cx = z.points.reduce((s, p) => s + p[0], 0) / z.points.length
                const cy = z.points.reduce((s, p) => s + p[1], 0) / z.points.length
                return (
                  <g key={z.name}>
                    <polygon
                      points={z.points.map((p) => p.join(',')).join(' ')}
                      fill={color}
                      fillOpacity={0.15}
                      stroke={color}
                      strokeWidth={2}
                      vectorEffect="non-scaling-stroke"
                    />
                    <text
                      x={cx}
                      y={cy}
                      textAnchor="middle"
                      fill={color}
                      fontSize={30}
                      fontWeight={600}
                      stroke="#000"
                      strokeWidth={5}
                      style={labelStyle}
                    >
                      {z.name}
                    </text>
                  </g>
                )
              })}
            {showShapes &&
              lines.map((l) => (
                <g key={l.name}>
                  <line
                    x1={l.points[0][0]}
                    y1={l.points[0][1]}
                    x2={l.points[1][0]}
                    y2={l.points[1][1]}
                    stroke={LINE_COLOR}
                    strokeWidth={3}
                    vectorEffect="non-scaling-stroke"
                  />
                  <text
                    x={l.points[0][0] + 12}
                    y={l.points[0][1] - 12}
                    fill={LINE_COLOR}
                    fontSize={28}
                    fontWeight={600}
                    stroke="#000"
                    strokeWidth={5}
                    style={labelStyle}
                  >
                    {l.name}
                  </text>
                </g>
              ))}
            {showCrossings &&
              crossings.map((e) => (
                <circle
                  key={e.id}
                  cx={e.x as number}
                  cy={e.y as number}
                  r={12}
                  fill="#e5645b"
                  stroke="#fff"
                  strokeWidth={2}
                  vectorEffect="non-scaling-stroke"
                >
                  <title>{`track ${e.track_id}, ${e.direction}, ${e.time_s.toFixed(2)} s`}</title>
                </circle>
              ))}
          </svg>
        </div>
      )}

      {active === 'heatmap' && !missing && (
        <p className="muted">
          Presence time of confirmed tracks over the whole run, drawn on the first frame. There is
          no color scale yet.
        </p>
      )}
      {showCrossings && !missing && (
        <p className="muted">Crossing points are drawn on the first frame, not where the video was at that time.</p>
      )}
    </section>
  )
}