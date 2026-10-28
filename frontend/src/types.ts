export type RunStatus = 'running' | 'done' | 'failed'

export interface Run {
  id: number
  source: string
  status: RunStatus
  started_at: string
  finished_at: string | null
  fps: number | null
  width: number | null
  height: number | null
  frame_count: number | null
}

export type Point = [number, number]

export interface ZoneCfg {
  name: string
  points: Point[]
}

export interface LineCfg {
  name: string
  points: [Point, Point]
  pos_label: string
  neg_label: string
}

export interface RunDetail extends Run {
  config: {
    zones?: { zones: ZoneCfg[] }
    lines?: { lines: LineCfg[] }
  } | null
  has_video?: boolean
}

export type EventType = 'line_cross' | 'zone_enter' | 'zone_exit'

export interface RunEvent {
  id: number
  type: EventType
  track_id: number
  time_s: number
  frame: number
  zone: string | null
  line: string | null
  direction: string | null
  x: number | null
  y: number | null
  start_s: number | null
  dwell_s: number | null
}

export interface Summary {
  events: Partial<Record<EventType, number>>
  line_crossings: { line: string; direction: string; count: number }[]
  zones: {
    zone: string
    visits: number
    avg_dwell_s: number | null
    max_dwell_s: number | null
  }[]
}

export type LiveMessage =
  | { kind: 'event'; event: RunEvent }
  | { kind: 'run_done'; status: RunStatus }