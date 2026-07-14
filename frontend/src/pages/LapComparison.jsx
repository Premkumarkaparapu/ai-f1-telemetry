import { useEffect, useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import { api } from '../api'
import { msToLapTime, CompoundBadge, compoundColor } from '../utils'

const CHANNELS = ['speed_kmh', 'throttle_pct', 'brake', 'drs', 'rpm', 'gear']
const CHANNEL_LABELS = {
  speed_kmh:    'Speed (km/h)',
  throttle_pct: 'Throttle (%)',
  brake:        'Brake',
  drs:          'DRS',
  rpm:          'RPM',
  gear:         'Gear',
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: 'var(--bg-2)', border: '1px solid var(--border-hi)', borderRadius: 6, padding: '8px 12px', fontSize: 12 }}>
      <div style={{ color: 'var(--text-2)', marginBottom: 6 }}>{label?.toFixed(0)} m</div>
      {payload.map(p => (
        <div key={p.dataKey} style={{ color: p.color, display: 'flex', gap: 12, justifyContent: 'space-between' }}>
          <span>{p.name}</span>
          <span style={{ fontFamily: 'JetBrains Mono', fontWeight: 600 }}>
            {typeof p.value === 'boolean' ? (p.value ? 'ON' : 'OFF') : p.value?.toFixed(1)}
          </span>
        </div>
      ))}
    </div>
  )
}

export default function LapComparison() {
  const [sessions, setSessions]   = useState([])
  const [selSess, setSelSess]     = useState(null)
  const [drivers, setDrivers]     = useState([])
  const [d1, setD1] = useState(null)
  const [d2, setD2] = useState(null)
  const [laps1, setLaps1]         = useState([])
  const [laps2, setLaps2]         = useState([])
  const [selLap1, setSelLap1]     = useState(null)
  const [selLap2, setSelLap2]     = useState(null)
  const [channel, setChannel]     = useState('speed_kmh')
  const [compareData, setCompare] = useState(null)
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState(null)

  useEffect(() => {
    api.sessions().then(s => { setSessions(s); if (s.length) setSelSess(s[0].session_id) }).catch(() => {})
  }, [])

  useEffect(() => {
    if (!selSess) return
    api.drivers(selSess).then(d => { setDrivers(d); setD1(d[0]?.driver_id); setD2(d[1]?.driver_id) }).catch(() => {})
  }, [selSess])

  useEffect(() => { if (d1) api.laps(d1, true).then(l => { setLaps1(l); setSelLap1(l[0]?.lap_id) }).catch(() => {}) }, [d1])
  useEffect(() => { if (d2) api.laps(d2, true).then(l => { setLaps2(l); setSelLap2(l[0]?.lap_id) }).catch(() => {}) }, [d2])

  function runComparison() {
    if (!selLap1 || !selLap2) return
    setLoading(true)
    setError(null)
    api.compareLaps(selLap1, selLap2)
      .then(data => {
        // Merge by distance
        const map = {}
        data.telemetry_1.forEach(p => {
          const d = Math.round(p.distance_m)
          map[d] = { distance: d, driver1: p[channel] }
        })
        data.telemetry_2.forEach(p => {
          const d = Math.round(p.distance_m)
          if (!map[d]) map[d] = { distance: d }
          map[d].driver2 = p[channel]
        })
        const merged = Object.values(map).sort((a, b) => a.distance - b.distance)
        setCompare({ merged, meta: data })
        setLoading(false)
      })
      .catch(e => { setError(e.message); setLoading(false) })
  }

  useEffect(() => {
    if (compareData) runComparison()
  }, [channel])

  const d1info = drivers.find(d => d.driver_id === d1)
  const d2info = drivers.find(d => d.driver_id === d2)
  const lap1info = laps1.find(l => l.lap_id === selLap1)
  const lap2info = laps2.find(l => l.lap_id === selLap2)

  const color1 = d1info?.team_color || '#E8002D'
  const color2 = d2info?.team_color || '#00D2BE'

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Lap Comparison</h1>
          <p className="page-subtitle">Overlay telemetry traces for two laps</p>
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
              <label>Driver 1</label>
              <select value={d1 || ''} onChange={e => setD1(Number(e.target.value))}>
                {drivers.map(d => <option key={d.driver_id} value={d.driver_id}>{d.code} — {d.team}</option>)}
              </select>
            </div>
            <div>
              <label>Lap 1</label>
              <select value={selLap1 || ''} onChange={e => setSelLap1(Number(e.target.value))}>
                {laps1.map(l => (
                  <option key={l.lap_id} value={l.lap_id}>
                    Lap {l.lap_number} — {msToLapTime(l.lap_time_ms)} ({l.compound})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label>Driver 2</label>
              <select value={d2 || ''} onChange={e => setD2(Number(e.target.value))}>
                {drivers.map(d => <option key={d.driver_id} value={d.driver_id}>{d.code} — {d.team}</option>)}
              </select>
            </div>
            <div>
              <label>Lap 2</label>
              <select value={selLap2 || ''} onChange={e => setSelLap2(Number(e.target.value))}>
                {laps2.map(l => (
                  <option key={l.lap_id} value={l.lap_id}>
                    Lap {l.lap_number} — {msToLapTime(l.lap_time_ms)} ({l.compound})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label>Channel</label>
              <select value={channel} onChange={e => setChannel(e.target.value)}>
                {CHANNELS.map(c => <option key={c} value={c}>{CHANNEL_LABELS[c]}</option>)}
              </select>
            </div>
          </div>
          <div style={{ marginTop: 16 }}>
            <button className="btn btn-primary" onClick={runComparison} disabled={loading}>
              {loading ? '⟳ Loading…' : '⇌ Compare Laps'}
            </button>
          </div>
        </div>

        {error && <div className="empty"><span className="empty-icon">⚠️</span>{error}</div>}

        {/* Lap header */}
        {compareData && (
          <>
            <div className="grid-2" style={{ marginBottom: 20 }}>
              {[
                { info: d1info, lap: lap1info, color: color1 },
                { info: d2info, lap: lap2info, color: color2 },
              ].map(({ info, lap, color }, i) => (
                <div key={i} className="card" style={{ borderColor: color + '55' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div>
                      <div style={{ fontSize: 22, fontWeight: 800, color, fontFamily: 'JetBrains Mono' }}>
                        {info?.code || '???'}
                      </div>
                      <div style={{ color: 'var(--text-2)', fontSize: 12 }}>{info?.team}</div>
                    </div>
                    {lap && <CompoundBadge compound={lap.compound} />}
                  </div>
                  <div style={{ marginTop: 12, display: 'flex', gap: 20 }}>
                    <div>
                      <div style={{ color: 'var(--text-2)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Lap Time</div>
                      <div className="mono" style={{ fontSize: 18, fontWeight: 700 }}>{msToLapTime(lap?.lap_time_ms)}</div>
                    </div>
                    <div>
                      <div style={{ color: 'var(--text-2)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Tyre Age</div>
                      <div className="mono" style={{ fontSize: 18, fontWeight: 700 }}>{lap?.tyre_life ?? '—'} laps</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Chart */}
            <div className="chart-wrap">
              <div className="chart-title">
                📊 {CHANNEL_LABELS[channel]} vs Distance
              </div>
              <ResponsiveContainer width="100%" height={320}>
                <LineChart data={compareData.merged} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis
                    dataKey="distance"
                    tick={{ fill: 'var(--text-2)', fontSize: 11 }}
                    tickFormatter={v => `${(v / 1000).toFixed(1)}km`}
                    stroke="var(--border)"
                  />
                  <YAxis tick={{ fill: 'var(--text-2)', fontSize: 11 }} stroke="var(--border)" />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend
                    formatter={(v) => <span style={{ color: 'var(--text-1)', fontSize: 12 }}>{v}</span>}
                  />
                  <Line
                    dataKey="driver1"
                    name={d1info?.code || 'Driver 1'}
                    stroke={color1}
                    dot={false}
                    strokeWidth={2}
                    connectNulls
                  />
                  <Line
                    dataKey="driver2"
                    name={d2info?.code || 'Driver 2'}
                    stroke={color2}
                    dot={false}
                    strokeWidth={2}
                    strokeDasharray="6 3"
                    connectNulls
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </>
        )}

        {!compareData && !loading && !error && (
          <div className="empty">
            <span className="empty-icon">⇌</span>
            <span>Select two laps and click Compare</span>
          </div>
        )}
      </div>
    </>
  )
}
