import { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { api } from '../api.js';

export default function Weather() {
  const [sessions, setSessions] = useState([]);
  const [sessionId, setSessionId] = useState('1');
  const [weather, setWeather] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.getSessions()
      .then(s => { setSessions(s); if (s.length) setSessionId(String(s[0].session_id)); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!sessionId) return;
    setLoading(true);
    api.getWeather(sessionId)
      .then(setWeather)
      .catch(() => setWeather([]))
      .finally(() => setLoading(false));
  }, [sessionId]);

  const latest = weather.length ? weather[Math.floor(weather.length / 2)] : null;

  const chartData = weather.filter((_, i) => i % 3 === 0).map((w, i) => ({
    t: i,
    air: w.air_temp ?? null,
    track: w.track_temp ?? null,
    humidity: w.humidity ?? null,
    wind: w.wind_speed ?? null,
  }));

  const kpis = latest ? [
    { label: 'Air Temp', value: latest.air_temp != null ? `${latest.air_temp.toFixed(1)} C` : '--', color: '#f87171' },
    { label: 'Track Temp', value: latest.track_temp != null ? `${latest.track_temp.toFixed(1)} C` : '--', color: '#fbbf24' },
    { label: 'Humidity', value: latest.humidity != null ? `${latest.humidity.toFixed(0)} %` : '--', color: '#60a5fa' },
    { label: 'Wind Speed', value: latest.wind_speed != null ? `${latest.wind_speed.toFixed(1)} km/h` : '--', color: '#34d399' },
    { label: 'Rainfall', value: latest.rainfall ? 'Wet' : 'Dry', color: latest.rainfall ? '#60a5fa' : '#34d399' },
    { label: 'Pressure', value: latest.pressure != null ? `${latest.pressure.toFixed(0)} hPa` : '--', color: '#c084fc' },
  ] : [];

  return (
    <div className="content-area">
      <div className="page-header">
        <div>
          <div className="page-title">Weather Conditions</div>
          <div className="page-desc">Race day weather — temperature, humidity, wind, rainfall</div>
        </div>
        <select className="filter-select" value={sessionId} onChange={e => setSessionId(e.target.value)}>
          {sessions.map(s => (
            <option key={s.session_id} value={s.session_id}>{s.event_name} {s.year}</option>
          ))}
        </select>
      </div>

      {loading && (
        <div className="loading-state">
          <div className="spinner" />
          <span>Loading weather data...</span>
        </div>
      )}

      {!loading && latest && (
        <>
          {/* KPI Row */}
          <div className="kpi-row" style={{ marginBottom: 12 }}>
            {kpis.map(({ label, value, color }) => (
              <div key={label} className="kpi-card">
                <div className="kpi-label">{label}</div>
                <div className="kpi-value" style={{ color, fontSize: 16 }}>{value}</div>
              </div>
            ))}
          </div>

          {/* Charts */}
          <div className="grid-2">
            <div className="card">
              <div className="card-header">
                <span className="card-title">Temperature Over Session</span>
              </div>
              <div className="card-body">
                <ResponsiveContainer width="100%" height={180}>
                  <LineChart data={chartData} margin={{ top: 4, right: 12, bottom: 16, left: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(48,54,61,0.45)" vertical={false} />
                    <XAxis dataKey="t" tick={{ fontSize: 8, fill: '#6e7681' }} tickLine={false}
                      label={{ value: 'Time', position: 'insideBottom', offset: -10, fontSize: 8, fill: '#6e7681' }} />
                    <YAxis tick={{ fontSize: 8, fill: '#6e7681', fontFamily: 'monospace' }} tickLine={false} axisLine={false} width={32} domain={['auto', 'auto']} />
                    <Tooltip contentStyle={{ background: 'rgba(22,27,34,0.97)', border: '1px solid rgba(48,54,61,0.9)', borderRadius: 4, fontSize: 10 }} />
                    <Line type="monotone" dataKey="air" stroke="#f87171" strokeWidth={1.5} dot={false} name="Air (C)" />
                    <Line type="monotone" dataKey="track" stroke="#fbbf24" strokeWidth={1.5} dot={false} name="Track (C)" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="card">
              <div className="card-header">
                <span className="card-title">Humidity & Wind Speed</span>
              </div>
              <div className="card-body">
                <ResponsiveContainer width="100%" height={180}>
                  <LineChart data={chartData} margin={{ top: 4, right: 12, bottom: 16, left: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(48,54,61,0.45)" vertical={false} />
                    <XAxis dataKey="t" tick={{ fontSize: 8, fill: '#6e7681' }} tickLine={false}
                      label={{ value: 'Time', position: 'insideBottom', offset: -10, fontSize: 8, fill: '#6e7681' }} />
                    <YAxis tick={{ fontSize: 8, fill: '#6e7681', fontFamily: 'monospace' }} tickLine={false} axisLine={false} width={32} domain={['auto', 'auto']} />
                    <Tooltip contentStyle={{ background: 'rgba(22,27,34,0.97)', border: '1px solid rgba(48,54,61,0.9)', borderRadius: 4, fontSize: 10 }} />
                    <Line type="monotone" dataKey="humidity" stroke="#60a5fa" strokeWidth={1.5} dot={false} name="Humidity (%)" />
                    <Line type="monotone" dataKey="wind" stroke="#34d399" strokeWidth={1.5} dot={false} name="Wind (km/h)" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* Full table */}
          <div className="card" style={{ marginTop: 10 }}>
            <div className="card-header">
              <span className="card-title">All Weather Readings</span>
              <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{weather.length} readings</span>
            </div>
            <div style={{ overflowX: 'auto', maxHeight: 260, overflowY: 'auto' }}>
              <table className="standings-table" style={{ width: '100%' }}>
                <thead style={{ position: 'sticky', top: 0 }}>
                  <tr>
                    <th>#</th>
                    <th>Air Temp (C)</th>
                    <th>Track Temp (C)</th>
                    <th>Humidity (%)</th>
                    <th>Wind (km/h)</th>
                    <th>Rainfall</th>
                  </tr>
                </thead>
                <tbody>
                  {weather.map((w, i) => (
                    <tr key={i}>
                      <td style={{ color: 'var(--text-muted)', fontFamily: 'monospace' }}>{i + 1}</td>
                      <td style={{ color: '#f87171', fontFamily: 'monospace' }}>{w.air_temp != null ? w.air_temp.toFixed(1) : '--'}</td>
                      <td style={{ color: '#fbbf24', fontFamily: 'monospace' }}>{w.track_temp != null ? w.track_temp.toFixed(1) : '--'}</td>
                      <td style={{ color: '#60a5fa', fontFamily: 'monospace' }}>{w.humidity != null ? w.humidity.toFixed(0) : '--'}</td>
                      <td style={{ color: '#34d399', fontFamily: 'monospace' }}>{w.wind_speed != null ? w.wind_speed.toFixed(1) : '--'}</td>
                      <td style={{ color: w.rainfall ? '#60a5fa' : '#34d399' }}>{w.rainfall ? 'Wet' : 'Dry'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {!loading && !latest && (
        <div className="empty-state" style={{ height: 200 }}>
          <span style={{ fontSize: 40 }}>🌤</span>
          <span>No weather data available for this session</span>
        </div>
      )}
    </div>
  );
}
