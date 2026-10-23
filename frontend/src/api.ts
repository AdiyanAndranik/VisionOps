import type { Run, RunDetail, RunEvent, Summary } from './types'

const BASE = '/api'

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { signal })
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

export function listRuns(limit = 50, offset = 0, signal?: AbortSignal) {
  return get<Run[]>(`/runs?limit=${limit}&offset=${offset}`, signal)
}

export function getRun(id: number, signal?: AbortSignal) {
  return get<RunDetail>(`/runs/${id}`, signal)
}

export function getSummary(id: number, signal?: AbortSignal) {
  return get<Summary>(`/runs/${id}/summary`, signal)
}

export const EVENTS_LIMIT = 5000

export function listEvents(id: number, signal?: AbortSignal) {
  return get<RunEvent[]>(`/runs/${id}/events?limit=${EVENTS_LIMIT}`, signal)
}