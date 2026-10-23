export function basename(path: string): string {
  return path.split(/[\\/]/).pop() ?? path
}

export function num(v: number | string | null | undefined, digits = 2): string {
  if (v === null || v === undefined) return '–'
  const n = Number(v)
  return Number.isFinite(n) ? n.toFixed(digits) : '–'
}