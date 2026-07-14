import { useEffect, useState } from 'react'
import { api } from '../api'
import { msToLapTime, CompoundBadge } from '../utils'

export default function Dashboard() {
  const [sessions, setSessions]     = useState([])
  const [selSession, setSelSession] = useState(null)
  const [standings, setStandings]   = useState([])
  const [weather, setWeather]       = useState([])
  const [loading, setLoading]       = useState(false)
  const [error, setError]           = useState(null)

  useEffect(() => {
    api.sessions()
      .then(s => { setSessions(s); if (s.length) setSelSession(s[0].session_id) })
      .catch(e => setError(e.message))
  }, [])

  useEffect(() => {
    if (!selSession) return
    setLoading(true)
    Promise.all([
      api.sessionStandings(selSession).catch(() => []),
      api.sessionWeather(selSession).catch(() => []),
    ]).then(([st, wx]) => {
      setStandings(st)
      setWeather(wx)
      setLoading(false)
    })
  }, [selSession])

  const sel = sessions.find(s => s.session_id === selSession)
  const latestWeather = weather.at(-1)

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Race Dashboard</h1>
          <p className="page-subtitle">Session overview — standings, telemetry, weather</p>
        </div>
        <select
          value={selSession || ''}
          onChange={e => setSelSession(Number(e.target.value))}
        >
          {sessions.map(s => (
            <option key={s.session_id} value={s.session_id}>
              {s.year} {s.event_name} — {s.session_type}
            </option>
          ))}
        </select>
      </div>

      <div className="page-body">
        {error && <div className="empty"><span className="empty-icon">⚠️</span>{error}</div>}

        {/* KPI Row */}
        {sel && (
          <div className="grid-4" style={{ marginBottom: 20 }}>
            <div className="card">
              <div className="card-title">Circuit</div>
              <div className="card-value" style={{ fontSize: 18 }}>{sel.track || '—'}</div>
              <div style={{ color: 'var(--text-2)', fontSize: 12, marginTop: 4 }}>{sel.country}</div>
            </div>
            <div className="card">
              <div className="card-title">Total Laps</div>
              <div className="card-value">{sel.total_laps || '—'}</div>
            </div>
            <div className="card">
              <div className="card-title">Air / Track Temp</div>
              <div className="card-value" style={{ fontSize: 20 }}>
                {latestWeather ? `${latestWeather.air_temp?.toFixed(0)}°` : '—'}
                <span className="card-unit">air</span>
              </div>
              {latestWeather && (
                <div style={{ color: 'var(--text-2)', fontSize: 12, marginTop: 4 }}>
                  Track: {latestWeather.track_temp?.toFixed(0)}°C
                  {latestWeather.rainfall ? '  🌧 Rain' : ''}
                </div>
              )}
            </div>
            <div className="card">
              <div className="card-title">Drivers</div>
              <div className="card-value">{standings.length || '—'}</div>
            </div>
          </div>
        )}

        {/* Standings table */}
        <div className="section-title">Driver Standings</div>

        {loading ? (
          <div className="loading"><div className="spinner" /> Loading standings…</div>
        ) : standings.length === 0 ? (
          <div className="empty">
            <span className="empty-icon">🏎️</span>
            <span>No data yet — run the data pipeline first</span>
            <code style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 8 }}>
              python -m data_pipeline.load_db
            </code>
          </div>
        ) : (
          <div className="card" style={{ padding: 0 }}>
            <table>
              <thead>
                <tr>
                  <th>Pos</th>
                  <th>Driver</th>
                  <th>Team</th>
                  <th>Fastest Lap</th>
                  <th>Avg Lap</th>
                  <th>Total Laps</th>
                  <th>Pit Stops</th>
                </tr>
              </thead>
              <tbody>
                {standings.map(d => (
                  <tr key={d.driver_id}>
                    <td>
                      <span style={{
                        color: d.position === 1 ? 'var(--gold)' :
                               d.position <= 3  ? 'var(--text-0)' : 'var(--text-2)',
                        fontWeight: d.position <= 3 ? 700 : 400,
                      }}>
                        P{d.position}
                      </span>
                    </td>
                    <td>
                      <span style={{
                        fontWeight: 700,
                        color: d.team_color || 'var(--text-0)',
                        fontFamily: 'JetBrains Mono',
                      }}>
                        {d.driver_code}
                      </span>
                    </td>
                    <td style={{ color: 'var(--text-2)' }}>{d.team || '—'}</td>
                    <td className="mono val-green">{msToLapTime(d.fastest_lap_ms)}</td>
                    <td className="mono">{msToLapTime(Math.round(d.avg_lap_time_ms))}</td>
                    <td>{d.total_laps}</td>
                    <td>{d.pit_stop_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  )
}
