import { useEffect, useState } from 'react'
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer,
  ReferenceLine, Cell,
} from 'recharts'
import { api } from '../api'
import { msToLapTime, formatRaceTime, deltaMs, compoundColor } from '../utils'

const COMPOUND_OPTIONS = ['SOFT', 'MEDIUM', 'HARD']

export default function StrategySimulator() {
  const [sessions, setSessions]   = useState([])
  const [selSess, setSelSess]     = useState(null)
  const [drivers, setDrivers]     = useState([])
  const [selDriver, setSelDriver] = useState(null)
  const [pitLaps, setPitLaps]     = useState('28,52')
  const [compounds, setCompounds] = useState(['SOFT', 'MEDIUM', 'HARD'])
  const [pitLoss, setPitLoss]     = useState(25000)
  const [result, setResult]       = useState(null)
  const [pitWindow, setPitWindow] = useState(null)
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState(null)
  const [currentLap, setCurrentLap] = useState(30)

  useEffect(() => {
    api.sessions().then(s => { setSessions(s); if (s.length) setSelSess(s[0].session_id) }).catch(() => {})
  }, [])

  useEffect(() => {
    if (!selSess) return
    api.drivers(selSess).then(d => { setDrivers(d); if (d.length) setSelDriver(d[0].driver_id) }).catch(() => {})
  }, [selSess])

  function parsePitLaps() {
    return pitLaps.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n) && n > 0)
  }

  async function runSimulation() {
    const pits = parsePitLaps()
    if (pits.length === 0) { setError('Enter at least one pit lap'); return }
    if (compounds.length !== pits.length + 1) {
      setError(`Need ${pits.length + 1} compounds for ${pits.length} pit stop(s). Got ${compounds.length}.`)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const r = await api.strategy({
        session_id: selSess,
        driver_id: selDriver,
        pit_laps: pits,
        compounds,
        pit_time_loss_ms: pitLoss,
      })
      setResult(r)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function loadPitWindow() {
    if (!selSess || !selDriver) return
    setLoading(true)
    try {
      const pw = await api.pitWindow(selSess, selDriver, currentLap)
      setPitWindow(pw)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  function updateCompound(idx, val) {
    setCompounds(prev => prev.map((c, i) => i === idx ? val : c))
  }

  function syncStints() {
    const pits = parsePitLaps()
    const needed = pits.length + 1
    setCompounds(prev => {
      const next = [...prev]
      while (next.length < needed) next.push('MEDIUM')
      return next.slice(0, needed)
    })
  }

  const chartData = result?.per_lap_times_ms.map((t, i) => ({
    lap: i + 1,
    time_ms: t,
    is_pit: result.pit_laps.includes(i + 1),
  })) || []

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Strategy Simulator</h1>
          <p className="page-subtitle">Model pit strategies and compare total race time</p>
        </div>
      </div>

      <div className="page-body">
        {/* Config card */}
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
              <label>Pit Laps (comma-separated)</label>
              <input
                type="text"
                value={pitLaps}
                onChange={e => { setPitLaps(e.target.value); syncStints() }}
                placeholder="e.g. 28,52"
                style={{ width: '100%' }}
              />
            </div>
            <div>
              <label>Pit Time Loss (ms)</label>
              <input
                type="number"
                value={pitLoss}
                onChange={e => setPitLoss(Number(e.target.value))}
                min={10000} max={40000} step={1000}
                style={{ width: '100%' }}
              />
            </div>
          </div>

          {/* Per-stint compound selectors */}
          <div style={{ marginTop: 16 }}>
            <label>Compounds per Stint</label>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 6 }}>
              {compounds.map((c, i) => (
                <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                  <span style={{ fontSize: 10, color: 'var(--text-3)', textTransform: 'uppercase' }}>
                    Stint {i + 1}
                  </span>
                  <select
                    value={c}
                    onChange={e => updateCompound(i, e.target.value)}
                    style={{ color: compoundColor(c), fontWeight: 700, fontFamily: 'JetBrains Mono' }}
                  >
                    {COMPOUND_OPTIONS.map(opt => <option key={opt} value={opt}>{opt}</option>)}
                  </select>
                </div>
              ))}
            </div>
          </div>

          <div style={{ marginTop: 16, display: 'flex', gap: 10 }}>
            <button className="btn btn-primary" onClick={runSimulation} disabled={loading}>
              {loading ? '⟳ Simulating…' : '🎯 Run Simulation'}
            </button>
          </div>
        </div>

        {error && <div className="empty" style={{ padding: 20 }}><span>⚠️ {error}</span></div>}

        {result && (
          <>
            {/* Summary stats */}
            <div className="strategy-summary">
              <div className="strategy-stat">
                <div className="strategy-stat-label">Total Race Time</div>
                <div className="strategy-stat-value">{formatRaceTime(result.total_race_time_ms)}</div>
              </div>
              <div className="strategy-stat">
                <div className="strategy-stat-label">vs Baseline</div>
                <div className="strategy-stat-value" style={{
                  color: result.vs_baseline_ms < 0 ? 'var(--green)' : 'var(--red)'
                }}>
                  {deltaMs(result.vs_baseline_ms)}
                </div>
              </div>
              <div className="strategy-stat">
                <div className="strategy-stat-label">Pit Stops</div>
                <div className="strategy-stat-value">{result.pit_stops}</div>
              </div>
              <div className="strategy-stat">
                <div className="strategy-stat-label">Pit Laps</div>
                <div className="strategy-stat-value" style={{ fontSize: 14 }}>
                  {result.pit_laps.join(', ')}
                </div>
              </div>
              <div className="strategy-stat">
                <div className="strategy-stat-label">Compounds</div>
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 4 }}>
                  {result.compounds.map((c, i) => (
                    <span key={i} style={{ color: compoundColor(c), fontFamily: 'JetBrains Mono', fontWeight: 700, fontSize: 13 }}>
                      {c}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* Per-lap chart */}
            <div className="chart-wrap">
              <div className="chart-title">⏱ Per-Lap Time (red bars = pit lap)</div>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={chartData} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                  <XAxis dataKey="lap" tick={{ fill: 'var(--text-2)', fontSize: 11 }} stroke="var(--border)" label={{ value: 'Lap', position: 'insideBottom', offset: -2, fill: 'var(--text-2)', fontSize: 11 }} />
                  <YAxis tickFormatter={v => msToLapTime(v)} tick={{ fill: 'var(--text-2)', fontSize: 10 }} stroke="var(--border)" width={68} />
                  <Tooltip
                    content={({ active, payload, label }) => active && payload?.length ? (
                      <div style={{ background: 'var(--bg-2)', border: '1px solid var(--border-hi)', borderRadius: 6, padding: '8px 12px', fontSize: 12 }}>
                        <div style={{ color: 'var(--text-2)', marginBottom: 4 }}>Lap {label}</div>
                        <div style={{ fontFamily: 'JetBrains Mono', color: payload[0]?.payload.is_pit ? 'var(--red)' : 'var(--text-0)' }}>
                          {msToLapTime(Math.round(payload[0]?.value))}
                          {payload[0]?.payload.is_pit && ' 🔧 PIT'}
                        </div>
                      </div>
                    ) : null}
                  />
                  <Bar dataKey="time_ms">
                    {chartData.map((entry, i) => (
                      <Cell
                        key={i}
                        fill={entry.is_pit ? '#E8002D' : 'rgba(0, 210, 190, 0.6)'}
                      />
                    ))}
                  </Bar>
                  {result.pit_laps.map(lap => (
                    <ReferenceLine key={lap} x={lap} stroke="var(--red)" strokeDasharray="4 2" label={{ value: 'PIT', fill: 'var(--red)', fontSize: 10 }} />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </>
        )}

        {/* Pit Window section */}
        <div className="section-title" style={{ marginTop: 28 }}>Pit Window Advisor</div>
        <div className="card">
          <div style={{ display: 'flex', gap: 16, alignItems: 'flex-end', flexWrap: 'wrap' }}>
            <div>
              <label>Current Lap</label>
              <input
                type="number"
                value={currentLap}
                min={1} max={100}
                onChange={e => setCurrentLap(Number(e.target.value))}
                style={{ width: 80 }}
              />
            </div>
            <button className="btn btn-ghost" onClick={loadPitWindow} disabled={loading || !selDriver}>
              🔮 Get Recommendation
            </button>
          </div>

          {pitWindow && (
            <div style={{ marginTop: 16, padding: 16, background: 'var(--bg-2)', borderRadius: 10, border: '1px solid var(--border-hi)' }}>
              <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', marginBottom: 12 }}>
                {[
                  { label: 'Earliest', val: pitWindow.earliest_lap, color: 'var(--text-2)' },
                  { label: 'Optimal', val: pitWindow.optimal_lap, color: 'var(--green)' },
                  { label: 'Latest', val: pitWindow.latest_lap, color: 'var(--red)' },
                ].map(({ label, val, color }) => (
                  <div key={label}>
                    <div style={{ fontSize: 11, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 2 }}>{label}</div>
                    <div style={{ fontSize: 26, fontWeight: 800, color, fontFamily: 'JetBrains Mono' }}>Lap {val}</div>
                  </div>
                ))}
              </div>
              <p style={{ fontSize: 13, color: 'var(--text-1)', lineHeight: 1.6 }}>{pitWindow.reasoning}</p>
            </div>
          )}
        </div>
      </div>
    </>
  )
}
