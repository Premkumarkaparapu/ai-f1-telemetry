import { useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { api } from '../api'
import { msToLapTime, compoundColor } from '../utils'

const COMPOUNDS = ['SOFT', 'MEDIUM', 'HARD', 'INTERMEDIATE', 'WET']

function DegradationTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: 'var(--bg-2)', border: '1px solid var(--border-hi)', borderRadius: 6, padding: '8px 12px', fontSize: 12 }}>
      <div style={{ color: 'var(--text-2)', marginBottom: 4 }}>Tyre Age: {label} laps</div>
      {payload.map(p => (
        <div key={p.name} style={{ color: p.color, display: 'flex', gap: 12, justifyContent: 'space-between' }}>
          <span>{p.name}</span>
          <span style={{ fontFamily: 'JetBrains Mono' }}>{msToLapTime(p.value)}</span>
        </div>
      ))}
    </div>
  )
}

export default function Degradation() {
  const [selected, setSelected] = useState(['SOFT', 'MEDIUM', 'HARD'])
  const [maxLife, setMaxLife]   = useState(40)
  const [data, setData]         = useState(null)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(null)

  function toggleCompound(c) {
    setSelected(prev =>
      prev.includes(c) ? prev.filter(x => x !== c) : [...prev, c]
    )
  }

  async function loadCurves() {
    if (!selected.length) return
    setLoading(true)
    setError(null)
    try {
      const results = await Promise.all(
        selected.map(c => api.degradation(c, maxLife))
      )
      // Merge into [{ tyre_life, SOFT: ms, MEDIUM: ms, ... }]
      const map = {}
      results.forEach(r => {
        r.tyre_life_values.forEach((life, i) => {
          if (!map[life]) map[life] = { tyre_life: life }
          map[life][r.compound] = r.predicted_lap_times_ms[i]
        })
      })
      const modelTypes = [...new Set(results.map(r => r.model_type))]
      setData({ rows: Object.values(map).sort((a, b) => a.tyre_life - b.tyre_life), modelTypes, results })
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Tyre Degradation</h1>
          <p className="page-subtitle">ML-predicted lap time vs tyre age per compound</p>
        </div>
      </div>

      <div className="page-body">
        <div className="card" style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', gap: 24, alignItems: 'flex-end', flexWrap: 'wrap' }}>
            <div>
              <label>Compounds</label>
              <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
                {COMPOUNDS.map(c => (
                  <button
                    key={c}
                    onClick={() => toggleCompound(c)}
                    style={{
                      padding: '5px 12px',
                      borderRadius: 6,
                      border: `2px solid ${selected.includes(c) ? compoundColor(c) : 'var(--border)'}`,
                      background: selected.includes(c) ? compoundColor(c) + '22' : 'var(--bg-3)',
                      color: selected.includes(c) ? compoundColor(c) : 'var(--text-2)',
                      fontWeight: 700,
                      fontSize: 12,
                      cursor: 'pointer',
                      fontFamily: 'JetBrains Mono',
                      transition: 'all 0.15s',
                    }}
                  >
                    {c}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label>Max Tyre Life</label>
              <input
                type="number"
                min={5} max={80}
                value={maxLife}
                onChange={e => setMaxLife(Number(e.target.value))}
                style={{ width: 80 }}
              />
            </div>
            <button className="btn btn-primary" onClick={loadCurves} disabled={loading || !selected.length}>
              {loading ? '⟳ Loading…' : '📉 Load Curves'}
            </button>
          </div>
        </div>

        {error && <div className="empty"><span className="empty-icon">⚠️</span>{error}</div>}

        {data && (
          <>
            {/* Model type badge */}
            <div style={{ marginBottom: 12, display: 'flex', gap: 8, alignItems: 'center' }}>
              <span style={{ color: 'var(--text-2)', fontSize: 12 }}>Model:</span>
              {data.modelTypes.map(t => (
                <span key={t} style={{
                  background: 'var(--bg-2)', border: '1px solid var(--border-hi)',
                  borderRadius: 4, padding: '2px 8px', fontSize: 11,
                  color: 'var(--green)', fontFamily: 'JetBrains Mono',
                }}>
                  {t}
                </span>
              ))}
            </div>

            <div className="chart-wrap">
              <div className="chart-title">⏱ Predicted Lap Time vs Tyre Age</div>
              <ResponsiveContainer width="100%" height={380}>
                <LineChart data={data.rows} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis
                    dataKey="tyre_life"
                    label={{ value: 'Tyre Age (laps)', position: 'insideBottom', offset: -4, fill: 'var(--text-2)', fontSize: 11 }}
                    tick={{ fill: 'var(--text-2)', fontSize: 11 }}
                    stroke="var(--border)"
                  />
                  <YAxis
                    tickFormatter={v => msToLapTime(v)}
                    tick={{ fill: 'var(--text-2)', fontSize: 10 }}
                    stroke="var(--border)"
                    width={68}
                  />
                  <Tooltip content={<DegradationTooltip />} />
                  <Legend formatter={v => <span style={{ color: 'var(--text-1)', fontSize: 12 }}>{v}</span>} />
                  {selected.map(c => (
                    <Line
                      key={c}
                      dataKey={c}
                      stroke={compoundColor(c)}
                      dot={false}
                      strokeWidth={2.5}
                      connectNulls
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Summary table */}
            <div className="section-title" style={{ marginTop: 24 }}>Degradation Summary</div>
            <div className="card" style={{ padding: 0 }}>
              <table>
                <thead>
                  <tr>
                    <th>Compound</th>
                    <th>Lap 1 Time</th>
                    <th>Lap 10 Time</th>
                    <th>Lap 20 Time</th>
                    <th>Lap 30 Time</th>
                    <th>Δ per lap (est.)</th>
                    <th>Model</th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map(r => {
                    const getPred = (lap) => r.predicted_lap_times_ms[Math.min(lap - 1, r.predicted_lap_times_ms.length - 1)]
                    const t1 = getPred(1)
                    const t10 = getPred(Math.min(10, r.tyre_life_values.length))
                    const t20 = getPred(Math.min(20, r.tyre_life_values.length))
                    const t30 = getPred(Math.min(30, r.tyre_life_values.length))
                    const slope = ((t30 - t1) / 29).toFixed(0)
                    return (
                      <tr key={r.compound}>
                        <td>
                          <span style={{ color: compoundColor(r.compound), fontFamily: 'JetBrains Mono', fontWeight: 700 }}>
                            {r.compound}
                          </span>
                        </td>
                        <td className="mono">{msToLapTime(Math.round(t1))}</td>
                        <td className="mono">{msToLapTime(Math.round(t10))}</td>
                        <td className="mono">{msToLapTime(Math.round(t20))}</td>
                        <td className="mono">{msToLapTime(Math.round(t30))}</td>
                        <td className="mono" style={{ color: 'var(--red)' }}>+{slope} ms</td>
                        <td style={{ color: 'var(--text-2)', fontSize: 11 }}>{r.model_type}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}

        {!data && !loading && (
          <div className="empty">
            <span className="empty-icon">📉</span>
            <span>Select compounds and click Load Curves</span>
          </div>
        )}
      </div>
    </>
  )
}
