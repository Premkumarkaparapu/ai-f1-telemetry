import { useState, useEffect, useMemo } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { api } from '../api.js';
import { msToLapTime, CompoundBadge, teamColor } from '../utils.jsx';

// Real lap fields: lap_id, driver_id, lap_number, lap_time_ms, fuel_corrected_lap_time_ms,
//   sector1_ms, sector2_ms, sector3_ms, compound, tyre_life, stint_number,
//   is_pit_lap, is_valid, track_status, air_temp, track_temp

export default function Laps() {
  const [sessions, setSessions] = useState([]);
  const [sessionId, setSessionId] = useState('1');
  const [drivers, setDrivers] = useState([]);
  const [standings, setStandings] = useState([]);
  const [driverId, setDriverId] = useState('');
  const [laps, setLaps] = useState([]);
  const [loading, setLoading] = useState(false);
  const [sortKey, setSortKey] = useState('lap_number');
  const [sortDir, setSortDir] = useState(1);
  const [filterValid, setFilterValid] = useState(false);

  useEffect(() => {
    api.getSessions()
      .then(s => { setSessions(s); if (s.length) setSessionId(String(s[0].session_id)); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!sessionId) return;
    Promise.allSettled([api.getDrivers(sessionId), api.getStandings(sessionId)]).then(([dR, sR]) => {
      const drvs = dR.status === 'fulfilled' ? dR.value : [];
      const stand = sR.status === 'fulfilled' ? sR.value : [];
      setDrivers(drvs);
      setStandings(stand);
      // Default to P1 driver
      if (stand.length) setDriverId(String(stand[0].driver_id));
      else if (drvs.length) setDriverId(String(drvs[0].driver_id));
    });
  }, [sessionId]);

  useEffect(() => {
    if (!driverId) return;
    setLoading(true);
    setLaps([]);
    api.getLaps(driverId)
      .then(setLaps)
      .catch(() => setLaps([]))
      .finally(() => setLoading(false));
  }, [driverId]);

  const toggleSort = (key) => {
    if (sortKey === key) setSortDir(d => -d);
    else { setSortKey(key); setSortDir(1); }
  };

  const displayLaps = useMemo(() => {
    let rows = filterValid ? laps.filter(l => l.is_valid && l.lap_time_ms) : laps;
    return [...rows].sort((a, b) => {
      const av = a[sortKey] ?? -Infinity;
      const bv = b[sortKey] ?? -Infinity;
      return (av < bv ? -1 : av > bv ? 1 : 0) * sortDir;
    });
  }, [laps, sortKey, sortDir, filterValid]);

  const validLaps = useMemo(() => laps.filter(l => l.is_valid && l.lap_time_ms), [laps]);
  const fastestLap = useMemo(() => validLaps.length ? validLaps.reduce((a, b) => a.lap_time_ms < b.lap_time_ms ? a : b) : null, [validLaps]);
  const avgTime = useMemo(() => validLaps.length ? validLaps.reduce((a, b) => a + b.lap_time_ms, 0) / validLaps.length : null, [validLaps]);

  // Evolution chart data
  const chartData = useMemo(() => validLaps.sort((a, b) => a.lap_number - b.lap_number).map(l => ({
    lap: l.lap_number,
    time: +(l.lap_time_ms / 1000).toFixed(3),
    fuel_corr: l.fuel_corrected_lap_time_ms ? +(l.fuel_corrected_lap_time_ms / 1000).toFixed(3) : null,
    pit: l.is_pit_lap,
  })), [validLaps]);

  const driverInfo = useMemo(() => {
    const d = drivers.find(d => String(d.driver_id) === driverId);
    const s = standings.find(s => String(s.driver_id) === driverId);
    return { driver: d, standing: s };
  }, [drivers, standings, driverId]);

  const sortIcon = (key) => sortKey === key ? (sortDir === 1 ? ' ↑' : ' ↓') : '';

  const COMPOUND_COLORS = { SOFT: '#e8002d', MEDIUM: '#fbbf24', HARD: '#e0e0e0', INTERMEDIATE: '#34d399', WET: '#60a5fa' };

  return (
    <div className="content-area">
      <div className="page-header">
        <div>
          <div className="page-title">Laps</div>
          <div className="page-desc">Lap-by-lap breakdown — times, sectors, compounds, stints</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <select className="filter-select" value={sessionId} onChange={e => setSessionId(e.target.value)}>
            {sessions.map(s => <option key={s.session_id} value={s.session_id}>{s.event_name} {s.year}</option>)}
          </select>
          <select className="filter-select" value={driverId} onChange={e => setDriverId(e.target.value)}>
            {standings.map(s => (
              <option key={s.driver_id} value={s.driver_id}>P{s.position} {s.driver_code}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Driver hero banner */}
      {driverInfo.driver && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 12, padding: '10px 14px', marginBottom: 10,
          background: `linear-gradient(135deg, ${driverInfo.driver.team_color || teamColor(driverInfo.driver.team)}14 0%, rgba(22,27,34,0.4) 100%)`,
          border: `1px solid ${driverInfo.driver.team_color || teamColor(driverInfo.driver.team)}33`,
          borderRadius: 8,
        }}>
          <div style={{ width: 4, height: 40, borderRadius: 2, background: driverInfo.driver.team_color || teamColor(driverInfo.driver.team) }} />
          <div>
            <span style={{ fontSize: 20, fontWeight: 900, color: 'var(--text-primary)' }}>{driverInfo.driver.code}</span>
            <span style={{ fontSize: 11, color: driverInfo.driver.team_color || teamColor(driverInfo.driver.team), fontWeight: 600, marginLeft: 8 }}>{driverInfo.driver.team}</span>
          </div>
          <div style={{ flex: 1 }} />
          {[
            ['Best Lap', msToLapTime(fastestLap?.lap_time_ms), '#c084fc'],
            ['Average', msToLapTime(avgTime ? Math.round(avgTime) : null), '#60a5fa'],
            ['Valid Laps', validLaps.length, '#34d399'],
            ['Total Laps', laps.length, 'var(--text-muted)'],
          ].map(([label, value, color]) => (
            <div key={label} style={{ textAlign: 'center', padding: '0 12px', borderLeft: '1px solid var(--border)' }}>
              <div style={{ fontSize: 8, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</div>
              <div style={{ fontSize: 14, fontFamily: 'monospace', fontWeight: 800, color, marginTop: 2 }}>{value ?? '—'}</div>
            </div>
          ))}
        </div>
      )}

      {/* Lap time evolution chart */}
      {chartData.length > 0 && (
        <div className="card" style={{ marginBottom: 10 }}>
          <div className="card-header">
            <span className="card-title">Lap Time Evolution</span>
            <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>Valid laps only · Pit laps marked</span>
          </div>
          <div className="card-body">
            <ResponsiveContainer width="100%" height={160}>
              <LineChart data={chartData} margin={{ top: 4, right: 16, bottom: 18, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(48,54,61,0.45)" vertical={false} />
                <XAxis dataKey="lap" tick={{ fontSize: 8, fill: '#6e7681', fontFamily: 'monospace' }} tickLine={false}
                  label={{ value: 'Lap Number', position: 'insideBottom', offset: -10, fontSize: 8, fill: '#6e7681' }} />
                <YAxis tick={{ fontSize: 8, fill: '#6e7681', fontFamily: 'monospace' }} tickLine={false} axisLine={false} width={32} domain={['auto', 'auto']}
                  tickFormatter={v => `${v}s`} />
                <Tooltip
                  formatter={(v, n) => [`${v}s`, n]}
                  labelFormatter={l => `Lap ${l}`}
                  contentStyle={{ background: 'rgba(22,27,34,0.97)', border: '1px solid rgba(48,54,61,0.9)', borderRadius: 4, fontSize: 10 }} />
                {chartData.filter(d => d.pit).map(d => (
                  <ReferenceLine key={d.lap} x={d.lap} stroke="rgba(248,113,113,0.4)" strokeDasharray="3 3"
                    label={{ value: 'Pit', position: 'top', fontSize: 7, fill: '#f87171' }} />
                ))}
                {fastestLap && (
                  <ReferenceLine y={+(fastestLap.lap_time_ms / 1000).toFixed(3)} stroke="rgba(52,211,153,0.4)" strokeDasharray="4 2"
                    label={{ value: 'FL', position: 'right', fontSize: 7, fill: '#34d399' }} />
                )}
                <Line type="monotone" dataKey="time" stroke="#60a5fa" strokeWidth={1.5} dot={{ r: 1.5, fill: '#60a5fa' }} activeDot={{ r: 3 }} name="Lap Time (s)" />
                <Line type="monotone" dataKey="fuel_corr" stroke="#c084fc" strokeWidth={1} strokeDasharray="3 2" dot={false} name="Fuel Corrected (s)" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Laps table */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Lap Data Table</span>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <label style={{ fontSize: 10, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer' }}>
              <input type="checkbox" checked={filterValid} onChange={e => setFilterValid(e.target.checked)}
                style={{ accentColor: 'var(--f1-red)' }} />
              Valid only
            </label>
            <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{displayLaps.length} rows</span>
          </div>
        </div>
        {loading && <div className="loading-state" style={{ height: 80 }}><div className="spinner" /><span>Loading laps...</span></div>}
        {!loading && (
          <div style={{ overflowX: 'auto', maxHeight: 400, overflowY: 'auto' }}>
            <table className="standings-table" style={{ width: '100%' }}>
              <thead style={{ position: 'sticky', top: 0 }}>
                <tr>
                  {[
                    ['lap_number', 'Lap'],
                    ['lap_time_ms', 'Lap Time'],
                    ['sector1_ms', 'S1'],
                    ['sector2_ms', 'S2'],
                    ['sector3_ms', 'S3'],
                    ['compound', 'Compound'],
                    ['tyre_life', 'Tyre Age'],
                    ['stint_number', 'Stint'],
                    ['is_pit_lap', 'Pit'],
                    ['is_valid', 'Valid'],
                  ].map(([key, label]) => (
                    <th key={key} onClick={() => toggleSort(key)}
                      style={{ cursor: 'pointer', userSelect: 'none', whiteSpace: 'nowrap' }}>
                      {label}{sortIcon(key)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {displayLaps.map(l => {
                  const isFastest = l.lap_id === fastestLap?.lap_id;
                  const cColor = COMPOUND_COLORS[l.compound] || '#888';
                  return (
                    <tr key={l.lap_id} style={{ background: isFastest ? 'rgba(52,211,153,0.06)' : undefined }}>
                      <td style={{ fontFamily: 'monospace', fontWeight: isFastest ? 700 : 400 }}>
                        {isFastest && <span style={{ color: '#34d399', marginRight: 4 }}>★</span>}
                        {l.lap_number}
                      </td>
                      <td style={{ fontFamily: 'monospace', fontWeight: 600, color: isFastest ? '#34d399' : 'var(--text-primary)' }}>
                        {msToLapTime(l.lap_time_ms)}
                      </td>
                      <td style={{ fontFamily: 'monospace', fontSize: 10, color: '#fbbf24' }}>{msToLapTime(l.sector1_ms)}</td>
                      <td style={{ fontFamily: 'monospace', fontSize: 10, color: '#60a5fa' }}>{msToLapTime(l.sector2_ms)}</td>
                      <td style={{ fontFamily: 'monospace', fontSize: 10, color: '#c084fc' }}>{msToLapTime(l.sector3_ms)}</td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                          <div style={{ width: 10, height: 10, borderRadius: '50%', background: cColor, border: '1px solid rgba(255,255,255,0.2)' }} />
                          <span style={{ fontSize: 10 }}>{l.compound || '—'}</span>
                        </div>
                      </td>
                      <td style={{ fontFamily: 'monospace', color: 'var(--text-muted)' }}>{l.tyre_life ?? '—'}</td>
                      <td style={{ fontFamily: 'monospace', color: 'var(--text-muted)' }}>{l.stint_number ?? '—'}</td>
                      <td>
                        {l.is_pit_lap && <span style={{ color: '#f87171', fontSize: 10, fontWeight: 700 }}>PIT</span>}
                      </td>
                      <td>
                        <span style={{ color: l.is_valid ? '#34d399' : '#f87171', fontSize: 10 }}>
                          {l.is_valid ? '✓' : '✗'}
                        </span>
                      </td>
                    </tr>
                  );
                })}
                {!displayLaps.length && !loading && (
                  <tr><td colSpan={10} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 32 }}>No laps found</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
