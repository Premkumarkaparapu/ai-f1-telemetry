/* Shared utilities */

export function msToLapTime(ms) {
  if (!ms) return '—'
  const totalS = ms / 1000
  const m = Math.floor(totalS / 60)
  const s = (totalS % 60).toFixed(3).padStart(6, '0')
  return `${m}:${s}`
}

export function msToSectorTime(ms) {
  if (!ms) return '—'
  return (ms / 1000).toFixed(3) + 's'
}

export function formatRaceTime(ms) {
  if (!ms) return '—'
  const h = Math.floor(ms / 3_600_000)
  const m = Math.floor((ms % 3_600_000) / 60_000)
  const s = ((ms % 60_000) / 1000).toFixed(1)
  if (h > 0) return `${h}h ${m}m ${s}s`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

export function deltaMs(ms) {
  if (!ms) return '—'
  const sign = ms >= 0 ? '+' : ''
  return `${sign}${(ms / 1000).toFixed(3)}s`
}

const COMPOUND_COLORS = {
  SOFT:         '#FF3333',
  MEDIUM:       '#FFD700',
  HARD:         '#DDDDDD',
  INTERMEDIATE: '#39B54A',
  WET:          '#0067FF',
}

export function compoundColor(c) {
  return COMPOUND_COLORS[(c || '').toUpperCase()] || '#888'
}

export function CompoundBadge({ compound }) {
  const c = (compound || '').toUpperCase()
  return (
    <span className={`compound ${c}`}>
      <span className="compound-dot" style={{ background: compoundColor(c) }} />
      {c || '?'}
    </span>
  )
}
