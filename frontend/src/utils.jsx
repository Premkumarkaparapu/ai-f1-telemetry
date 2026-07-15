/** Format milliseconds → m:ss.mmm */
export function msToLapTime(ms) {
  if (ms == null || isNaN(ms)) return '—';
  const totalSec = ms / 1000;
  const mins = Math.floor(totalSec / 60);
  const secs = (totalSec % 60).toFixed(3).padStart(6, '0');
  return mins > 0 ? `${mins}:${secs}` : `${secs}`;
}

/** Format milliseconds → +/-s.mmm delta string */
export function msToDelta(ms) {
  if (ms == null || isNaN(ms)) return '—';
  const sign = ms >= 0 ? '+' : '-';
  const abs = Math.abs(ms) / 1000;
  return `${sign}${abs.toFixed(3)}`;
}

/** Map compound string to CSS class */
export function compoundClass(compound) {
  const c = (compound || '').toUpperCase();
  if (c === 'SOFT') return 'soft';
  if (c === 'MEDIUM') return 'medium';
  if (c === 'HARD') return 'hard';
  if (c.includes('INTER')) return 'inter';
  if (c === 'WET') return 'wet';
  return 'hard';
}

/** Single-letter compound abbreviation */
export function compoundLetter(compound) {
  const c = (compound || '').toUpperCase();
  if (c === 'SOFT') return 'S';
  if (c === 'MEDIUM') return 'M';
  if (c === 'HARD') return 'H';
  if (c.includes('INTER')) return 'I';
  if (c === 'WET') return 'W';
  return '?';
}

/** Team name → hex colour */
export function teamColor(team) {
  const t = (team || '').toLowerCase();
  if (t.includes('red bull') || t.includes('redbull')) return '#3671C6';
  if (t.includes('ferrari')) return '#E8002D';
  if (t.includes('mercedes')) return '#27F4D2';
  if (t.includes('mclaren')) return '#FF8000';
  if (t.includes('aston')) return '#229971';
  if (t.includes('alpine')) return '#FF87BC';
  if (t.includes('williams')) return '#64C4FF';
  if (t.includes('haas')) return '#B6BABD';
  if (t.includes('alfa') || t.includes('sauber') || t.includes('kick')) return '#C92D4B';
  if (t.includes('rb') || t.includes('racing bulls') || t.includes('visa')) return '#6692FF';
  return '#8b949e';
}

/** Compound Badge component */
export function CompoundBadge({ compound, size = 22 }) {
  const cls = compoundClass(compound);
  const letter = compoundLetter(compound);
  return (
    <span
      className={`compound-badge ${cls}`}
      style={{ width: size, height: size, fontSize: size * 0.42 }}
      title={compound}
    >
      {letter}
    </span>
  );
}

/** Compound name → hex colour (alias kept for backward compat) */
export function compoundColor(compound) {
  const c = (compound || '').toUpperCase();
  if (c === 'SOFT') return '#e8002d';
  if (c === 'MEDIUM') return '#fbbf24';
  if (c === 'HARD') return '#f0f6fc';
  if (c.includes('INTER')) return '#34d399';
  if (c === 'WET') return '#60a5fa';
  return '#8b949e';
}

/** Format total race milliseconds → h:mm:ss.mmm */
export function formatRaceTime(ms) {
  if (ms == null || isNaN(ms)) return '—';
  const totalSec = ms / 1000;
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = (totalSec % 60).toFixed(3).padStart(6, '0');
  return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${s}` : `${m}:${s}`;
}

/** Delta milliseconds → +/-s.mmm string */
export function deltaMs(ms) { return msToDelta(ms); }

/** Speed → colour for track map (blue → cyan → green → yellow → orange → red) */
export function speedToColor(speed, minSpeed, maxSpeed) {
  const t = Math.max(0, Math.min(1, (speed - minSpeed) / (maxSpeed - minSpeed)));
  const stops = [
    [0, 0, 255],
    [0, 200, 255],
    [0, 255, 128],
    [255, 255, 0],
    [255, 140, 0],
    [255, 0, 0],
  ];
  const idx = t * (stops.length - 1);
  const lo = Math.floor(idx);
  const hi = Math.min(lo + 1, stops.length - 1);
  const frac = idx - lo;
  const r = Math.round(stops[lo][0] + frac * (stops[hi][0] - stops[lo][0]));
  const g = Math.round(stops[lo][1] + frac * (stops[hi][1] - stops[lo][1]));
  const b = Math.round(stops[lo][2] + frac * (stops[hi][2] - stops[lo][2]));
  return `rgb(${r},${g},${b})`;
}
