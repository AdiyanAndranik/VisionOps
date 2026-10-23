import { useEffect, useState } from 'react'
import { getRun, getSummary, listEvents } from './api'
import type { LiveMessage, RunDetail, RunEvent, Summary } from './types'

export type Conn = 'connecting' | 'live' | 'reconnecting' | 'closed'

// Arrival order is not time order, so keep the list unique by id and sorted by time.
function merge(prev: RunEvent[], incoming: RunEvent[]): RunEvent[] {
  const byId = new Map<number, RunEvent>()
  for (const e of prev) byId.set(e.id, e)
  for (const e of incoming) byId.set(e.id, e)
  return [...byId.values()].sort((a, b) => a.time_s - b.time_s || a.id - b.id)
}

function wsUrl(runId: number): string {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${location.host}/api/runs/${runId}/ws`
}

export function useRunLive(runId: number) {
  const [run, setRun] = useState<RunDetail | null>(null)
  const [summary, setSummary] = useState<Summary | null>(null)
  const [events, setEvents] = useState<RunEvent[]>([])
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [conn, setConn] = useState<Conn>('connecting')

  useEffect(() => {
    let disposed = false
    let finished = false
    let firstLoad = true
    let ws: WebSocket | null = null
    let retryTimer: number | undefined
    let summaryTimer: number | undefined
    const controller = new AbortController()
    const { signal } = controller

    // Full load over REST. Safe to repeat: events are merged by id.
    const loadAll = () => {
      const initial = firstLoad
      firstLoad = false
      Promise.all([getRun(runId, signal), getSummary(runId, signal), listEvents(runId, signal)])
        .then(([r, s, e]) => {
          if (disposed) return
          setRun(r)
          setSummary(s)
          setEvents((prev) => merge(prev, e))
          setLoaded(true)
        })
        .catch((err) => {
          if (disposed || err.name === 'AbortError') return
          if (initial) setError(String(err.message ?? err))
        })
    }

    // At most one summary refetch per 500 ms while events keep arriving.
    const scheduleSummary = () => {
      if (summaryTimer !== undefined) return
      summaryTimer = window.setTimeout(() => {
        summaryTimer = undefined
        getSummary(runId, signal)
          .then((s) => {
            if (!disposed) setSummary(s)
          })
          .catch(() => {})
      }, 500)
    }

    const connect = () => {
      const socket = new WebSocket(wsUrl(runId))
      ws = socket

      // Subscribed on the server once the socket is open, so load history now.
      socket.onopen = () => {
        if (disposed) return
        setConn('live')
        loadAll()
      }

      socket.onmessage = (m) => {
        if (disposed) return
        const msg = JSON.parse(m.data) as LiveMessage
        if (msg.kind === 'event') {
          setEvents((prev) => merge(prev, [msg.event]))
          scheduleSummary()
        } else if (msg.kind === 'run_done') {
          finished = true
          setConn('closed')
          loadAll() // final numbers and status
        }
      }

      socket.onclose = (ev) => {
        if (disposed) return
        if (finished || ev.code === 4404) {
          setConn('closed')
          return
        }
        setConn('reconnecting')
        retryTimer = window.setTimeout(connect, 2000)
      }
    }

    connect()

    return () => {
      disposed = true
      controller.abort()
      window.clearTimeout(retryTimer)
      window.clearTimeout(summaryTimer)
      ws?.close()
    }
  }, [runId])

  return { run, summary, events, loaded, error, conn }
}

