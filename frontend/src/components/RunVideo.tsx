import type { RefObject } from 'react'
import type { RunDetail } from '../types'

export default function RunVideo({
  run,
  videoRef,
}: {
  run: RunDetail
  videoRef: RefObject<HTMLVideoElement | null>
}) {
  const w = run.width ?? 1920
  const h = run.height ?? 1080
  return (
    <section className="viewer-section">
      <h3>Annotated video</h3>
      <video
        ref={videoRef}
        className="run-video"
        src={`/api/runs/${run.id}/video`}
        controls
        preload="metadata"
        style={{ aspectRatio: `${w} / ${h}` }}
      />
      <p className="muted">
        Click an event row to jump there. The line and zone counters follow the confirmed events,
        so they change about half a second after the person actually crosses.
      </p>
    </section>
  )
}