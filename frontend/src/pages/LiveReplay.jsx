import { useEffect, useRef, useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import { api } from '../api'
import { msToLapTime, compoundColor, CompoundBadge } from '../utils'

export default function LiveReplay() {
  const [sessions, setSessions]   = useState([])
  const [selSess, setSelSess]     = useState(null)
  const [drivers, setDrivers]     = useState([])
  const [selDriver, setSelDriver] = useState(null)
  const [laps, setLaps]           = useState([])
  const [selLap, setSelLap]       = useState(null)
  const [telemetry, setTelemetry] = useState([])
  const [loading, setLoading]     = useState(false)
  const [playing, setPlaying]     = useState(false)
  const [progress, setProgress]   = useState(0)   // 0–1
  const [speed, setSpeed]         = useState(8)    // playback multiplier
  const animRef = useRef(null)
  const lastRef = useRef(null)

  useEffect(() => {
    api.sessions().then(s => { setSessions(s); if (s.length) setSelSess(s[0].session_id) }).catch(() => {})
  }, [])

  useEffect(() => {
    if (!selSess) return
    api.drivers(selSess).then(d => { setDrivers(d); if (d.length) setSelDriver(d[0].driver_id) }).catch(() => {})
  }, [selSess])

  useEffect(() => {
    if (!selDriver) return
    api.laps(selDriver, true).then(l => { setLaps(l); if (l.length) setSelLap(l[0].lap_id) }).catch(() => {})
  }, [selDriver])

  useEffect(() => {
    if (!selLap) return
    setLoading(true)
    setPlaying(false)
    setProgress(0)
    api.telemetry(selLap)
      .then(t => { setTelemetry(t); setLoading(false) })
      .catch(() => setLoading(false))
  }, [selLap])

  // Animation loop
  useEffect(() => {
    if (!playing) { cancelAnimationFrame(animRef.current); return }
    function tick(ts) {
      if (!lastRef.current) lastRef.current = ts
      const dt = (ts - lastRef.current) / 1000
      lastRef.current = ts
      setProgress(p => {
        const next = p + (dt * speed) / (telemetry.length || 1) * 5
        if (next >= 1) { setPlaying(false); return 1 }
        return next
      })
      animRef.current = requestAnimationFrame(tick)
    }
    lastRef.current = null
    animRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(animRef.current)
  }, [playing, speed, telemetry.length])

  const currentIdx = Math.min(
    Math.floor(progress * telemetry.length),
    telemetry.length - 1
  )
  const currentPt  = telemetry[currentIdx] || {}
  const visibleData = telemetry.slice(0, currentIdx + 1)

  // Track map path — normalise X/Y to 0-100 viewport
  const hasXY = telemetry.some(p => p.x != null)
  let trackPath = null
  let carPos = null
  if (hasXY) {
    const xs = telemetry.map(p => p.x).filter(Boolean)
    const ys = telemetry.map(p => p.y).filter(Boolean)
    const minX = Math.min(...xs), maxX = Math.max(...xs)
    const minY = Math.min(...ys), maxY = Math.max(...ys)
    const norm = (v, mn, mx) => ((v - mn) / (mx - mn || 1)) * 90 + 5

    const pts = telemetry
      .filter(p => p.x != null && p.y != null)
      .map(p => `${norm(p.x, minX, maxX).toFixed(2)},${norm(p.y, minY, maxY).toFixed(2)}`)
    trackPath = `M ${pts.join(' L ')}`

    if (currentPt.x != null) {
      carPos = {
        x: norm(currentPt.x, minX, maxX),
        y: norm(currentPt.y, minY, maxY),
      }
    }
  }

  const lap = laps.find(l => l.lap_id === selLap)

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Live Replay</h1>
          <p className="page-subtitle">Scrub through real telemetry data lap-by-lap</p>
        </div>
      </div>

      <div className="page-body">
        {/* Controls */}
        <div className="card" style={{ marginBottom: 20 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 16 }}>
            <div>
              <label>Session</label>
              <select value={selSess || ''} onChange={e => setSelSess(Number(e.target.value))}>
                {sessions.map(s => <option key={s.session_id} value={s.session_id}>{s.year} {s.event_name}</option>)}
              </select>
            </div>
            <div>
              <label>Driver</label>
              <select value={selDriver || ''} onChange={e => setSelDriver(Number(e.target.value))}>
                {drivers.map(d => <option key={d.driver_id} value={d.driver_id}>{d.code} — {d.team}</option>)}
              </select>
            </div>
            <div>
              <label>Lap</label>
              <select value={selLap || ''} onChange={e => setSelLap(Number(e.target.value))}>
                {laps.map(l => (
                  <option key={l.lap_id} value={l.lap_id}>
                    Lap {l.lap_number} — {msToLapTime(l.lap_time_ms)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label>Playback Speed</label>
              <select value={speed} onChange={e => setSpeed(Number(e.target.value))}>
                {[1, 2, 4, 8, 16, 32].map(s => <option key={s} value={s}>{s}×</option>)}
              </select>
            </div>
          </div>
        </div>

        {loading && <div className="loading"><div className="spinner" /> Loading telemetry…</div>}

        {!loading && telemetry.length > 0 && (
          <>
            {/* Live metric gauges */}
            <div className="grid-4" style={{ marginBottom: 20 }}>
              {[
                { label: 'Speed', value: currentPt.speed_kmh?.toFixed(0), unit: 'km/h', color: currentPt.speed_kmh > 280 ? 'var(--green)' : 'var(--text-0)' },
                { label: 'Throttle', value: currentPt.throttle_pct?.toFixed(1), unit: '%', color: 'var(--green)' },
                { label: 'Brake', value: currentPt.brake ? 'ON' : 'OFF', unit: '', color: currentPt.brake ? 'var(--red)' : 'var(--text-2)' },
                { label: 'Gear', value: currentPt.gear, unit: '', color: 'var(--text-0)' },
              ].map(g => (
                <div key={g.label} className="card">
                  <div className="card-title">{g.label}</div>
                  <div className="card-value" style={{ color: g.color, fontSize: 30 }}>
                    {g.value ?? '—'}
                    {g.unit && <span className="card-unit">{g.unit}</span>}
                  </div>
                </div>
              ))}
            </div>

            <div className="grid-2">
              {/* Speed trace */}
              <div className="chart-wrap" style={{ marginTop: 0 }}>
                <div className="chart-title">Speed Trace</div>
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={visibleData} margin={{ top: 4, right: 4, bottom: 4, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                    <XAxis dataKey="distance_m" tick={false} stroke="var(--border)" />
                    <YAxis domain={[0, 380]} tick={{ fill: 'var(--text-2)', fontSize: 10 }} stroke="var(--border)" />
                    <Tooltip formatter={v => [`${v?.toFixed(1)} km/h`, 'Speed']} contentStyle={{ background: 'var(--bg-2)', border: '1px solid var(--border-hi)', borderRadius: 6, fontSize: 12 }} />
                    <Line dataKey="speed_kmh" stroke="var(--green)" dot={false} strokeWidth={1.5} isAnimationActive={false} />
                    {currentPt.distance_m && (
                      <ReferenceLine x={currentPt.distance_m} stroke="white" strokeDasharray="3 2" />
                    )}
                  </LineChart>
                </ResponsiveContainer>
              </div>

              {/* Track map */}
              <div className="chart-wrap" style={{ marginTop: 0 }}>
                <div className="chart-title">Track Position</div>
                <div className="track-canvas">
                  {hasXY ? (
                    <svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet">
                      {/* Full track outline */}
                      <path
                        d={trackPath}
                        fill="none"
                        stroke="rgba(255,255,255,0.12)"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                      {/* Completed portion */}
                      {visibleData.length > 1 && (() => {
                        const xs = telemetry.map(p => p.x).filter(Boolean)
                        const ys = telemetry.map(p => p.y).filter(Boolean)
                        const minX = Math.min(...xs), maxX = Math.max(...xs)
                        const minY = Math.min(...ys), maxY = Math.max(...ys)
                        const norm = (v, mn, mx) => ((v - mn) / (mx - mn || 1)) * 90 + 5
                        const pts = visibleData.filter(p => p.x != null).map(p => `${norm(p.x, minX, maxX).toFixed(2)},${norm(p.y, minY, maxY).toFixed(2)}`)
                        return <path d={`M ${pts.join(' L ')}`} fill="none" stroke="var(--red)" strokeWidth="1.8" strokeLinecap="round" />
                      })()}
                      {/* Car dot */}
                      {carPos && (
                        <circle cx={carPos.x} cy={carPos.y} r="2.5" fill="white">
                          <animate attributeName="r" values="2;3.5;2" dur="1s" repeatCount="indefinite" />
                        </circle>
                      )}
                    </svg>
                  ) : (
                    <div className="empty" style={{ padding: 20 }}>
                      <span style={{ color: 'var(--text-3)', fontSize: 12 }}>No position data for this lap</span>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Playback controls */}
            <div className="replay-controls" style={{ marginTop: 20 }}>
              <button
                className={`control-btn ${playing ? 'active' : ''}`}
                onClick={() => { setProgress(0); setPlaying(false) }}
                title="Reset"
              >⏮</button>
              <button
                className={`control-btn ${playing ? 'active' : ''}`}
                onClick={() => setPlaying(p => !p)}
                title={playing ? 'Pause' : 'Play'}
              >
                {playing ? '⏸' : '▶'}
              </button>

              <div
                className="replay-progress"
                onClick={e => {
                  const rect = e.currentTarget.getBoundingClientRect()
                  setProgress((e.clientX - rect.left) / rect.width)
                }}
              >
                <div className="replay-progress-fill" style={{ width: `${progress * 100}%` }} />
                <div className="replay-progress-thumb" style={{ left: `${progress * 100}%` }} />
              </div>

              <span style={{ fontSize: 12, fontFamily: 'JetBrains Mono', color: 'var(--text-2)', whiteSpace: 'nowrap' }}>
                {currentPt.distance_m ? `${(currentPt.distance_m / 1000).toFixed(2)} km` : '—'}
              </span>
            </div>

            {/* Lap info footer */}
            {lap && (
              <div style={{ display: 'flex', gap: 16, marginTop: 16, flexWrap: 'wrap' }}>
                <div style={{ color: 'var(--text-2)', fontSize: 12 }}>
                  Lap {lap.lap_number} ·{' '}
                  <span className="mono" style={{ color: 'var(--green)' }}>{msToLapTime(lap.lap_time_ms)}</span>
                  {' '}· <CompoundBadge compound={lap.compound} /> · Tyre age: {lap.tyre_life} laps
                </div>
                {currentPt.drs && (
                  <span style={{ color: 'var(--blue)', fontSize: 12, fontWeight: 600 }}>⚡ DRS OPEN</span>
                )}
              </div>
            )}
          </>
        )}

        {!loading && telemetry.length === 0 && (
          <div className="empty">
            <span className="empty-icon">▶</span>
            <span>Select a session, driver, and lap to begin replay</span>
          </div>
        )}
      </div>
    </>
  )
}
