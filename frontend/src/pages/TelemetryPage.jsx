import { useState, useEffect, useMemo } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ComposedChart, Area, BarChart, Bar
} from 'recharts';
import { api } from '../api.js';
import { msToLapTime, speedToColor, teamColor } from '../utils.jsx';

// Real telemetry fields (after api.js normalization):
//   speed (from speed_kmh), throttle (from throttle_pct), brake (0 or 1),
//   drs (0 or 10), distance (from distance_m), rpm, gear, x, y, z

const CHANNELS = [
  { key: 'speed',    label: 'Speed (km/h)',   color: '#60a5fa', domain: [0, 360],   unit: 'km/h' },
  { key: 'throttle', label: 'Throttle (%)',   color: '#34d399', domain: [0, 100],   unit: '%' },
  { key: 'brake',    label: 'Brake',          color: '#f87171', domain: [0, 1],     unit: '' },
  { key: 'rpm',      label: 'RPM',            color: '#fbbf24', domain: [0, 15000], unit: 'rpm' },
  { key: 'gear',     label: 'Gear',           color: '#c084fc', domain: [0, 8],     unit: '' },
  { key: 'drs',      label: 'DRS',            color: '#818cf8', domain: [0, 12],    unit: '' },
];

function TrackMap({ telemetry }) {
  const segments = useMemo(() => {
    if (!telemetry?.length) return [];
    const pts = telemetry.filter(p => p.x != null && p.y != null && p.speed != null);
    if (pts.length < 2) return [];
    const speeds = pts.map(p => p.speed);
    const minS = Math.min(...speeds), maxS = Math.max(...speeds);
    const xs = pts.map(p => p.x), ys = pts.map(p => p.y);
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY = Math.min(...ys), maxY = Math.max(...ys);
    const W = 280, H = 200, PAD = 16;
    const sx = v => PAD + ((v - minX) / (maxX - minX || 1)) * (W - PAD * 2);
    const sy = v => H - PAD - ((v - minY) / (maxY - minY || 1)) * (H - PAD * 2);
    const step = Math.max(1, Math.floor(pts.length / 500));
    const sampled = pts.filter((_, i) => i % step === 0);
    return sampled.slice(0, -1).map((p, i) => {
      const next = sampled[i + 1];
      return { x1: sx(p.x), y1: sy(p.y), x2: sx(next.x), y2: sy(next.y), color: speedToColor(p.speed, minS, maxS) };
    });
  }, [telemetry]);

  if (!segments.length) {
    return (
      <div className="empty-state" style={{ height: 220 }}>
        <span>Select a lap to render track map</span>
      </div>
    );
  }

  return (
    <div style={{ position: 'relative', display: 'flex', justifyContent: 'center', alignItems: 'center', padding: '8px 40px 8px 8px' }}>
      <svg width={280} height={200} style={{ overflow: 'visible' }}>
        {segments.map((s, i) => (
          <line key={i} x1={s.x1} y1={s.y1} x2={s.x2} y2={s.y2}
            stroke={s.color} strokeWidth="2.5" strokeLinecap="round" />
        ))}
      </svg>
      {/* Speed legend bar */}
      <div style={{ position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)', display: 'flex', gap: 4 }}>
        <div style={{ width: 8, height: 120, borderRadius: 4, background: 'linear-gradient(to bottom,#ff0000,#ff8c00,#ffff00,#00ff80,#00bfff,#0000ff)' }} />
        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', height: 120 }}>
          {['320', '240', '160', '80', '0'].map(v => (
            <span key={v} style={{ fontSize: 7, color: '#6e7681', fontFamily: 'monospace' }}>{v}</span>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function TelemetryPage() {
  const [sessions, setSessions] = useState([]);
  const [sessionId, setSessionId] = useState('1');
  const [drivers, setDrivers] = useState([]);
  const [standings, setStandings] = useState([]);
  const [driverId, setDriverId] = useState('');
  const [laps, setLaps] = useState([]);
  const [lapId, setLapId] = useState('');
  const [telemetry, setTelemetry] = useState([]);
  const [activeChannel, setActiveChannel] = useState('speed');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.getSessions().then(s => { setSessions(s); if (s.length) setSessionId(String(s[0].session_id)); }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!sessionId) return;
    Promise.allSettled([api.getDrivers(sessionId), api.getStandings(sessionId)]).then(([dR, sR]) => {
      const drvs = dR.status === 'fulfilled' ? dR.value : [];
      const stand = sR.status === 'fulfilled' ? sR.value : [];
      setDrivers(drvs);
      setStandings(stand);
      if (stand.length) setDriverId(String(stand[0].driver_id));
      else if (drvs.length) setDriverId(String(drvs[0].driver_id));
    });
  }, [sessionId]);

  useEffect(() => {
    if (!driverId) return;
    api.getLaps(driverId).then(lapData => {
      setLaps(lapData);
      const valid = lapData.filter(l => l.is_valid && l.lap_time_ms);
      if (valid.length) {
        const fastest = valid.reduce((a, b) => a.lap_time_ms < b.lap_time_ms ? a : b);
        setLapId(String(fastest.lap_id));
      }
    }).catch(() => {});
  }, [driverId]);

  useEffect(() => {
    if (!lapId) { setTelemetry([]); return; }
    setLoading(true);
    api.getTelemetry(lapId).then(setTelemetry).catch(() => setTelemetry([])).finally(() => setLoading(false));
  }, [lapId]);

  const channel = CHANNELS.find(c => c.key === activeChannel) || CHANNELS[0];
  const selectedLap = laps.find(l => String(l.lap_id) === lapId);
  const selDriver = drivers.find(d => String(d.driver_id) === driverId);
  const selStanding = standings.find(s => String(s.driver_id) === driverId);

  const chartData = useMemo(() => {
    if (!telemetry.length) return [];
    const step = Math.max(1, Math.floor(telemetry.length / 350));
    return telemetry.filter((_, i) => i % step === 0).map(p => ({
      dist: Math.round(p.distance ?? 0),
      speed: +(p.speed ?? 0).toFixed(1),
      throttle: +(p.throttle ?? 0).toFixed(1),
      brake: +((p.brake ?? 0) * 100).toFixed(0),
      rpm: Math.round(p.rpm ?? 0),
      gear: p.gear ?? 0,
      drs: (p.drs ?? 0) > 8 ? 10 : 0,
    }));
  }, [telemetry]);

  // Stats from telemetry
  const telStats = useMemo(() => {
    if (!telemetry.length) return null;
    const speeds = telemetry.map(p => p.speed ?? 0).filter(s => s > 0);
    const throttles = telemetry.map(p => p.throttle ?? 0);
    const brakes = telemetry.filter(p => p.brake > 0.5);
    const drsZones = telemetry.filter(p => (p.drs ?? 0) > 8);
    return {
      topSpeed: speeds.length ? Math.max(...speeds) : 0,
      avgSpeed: speeds.length ? speeds.reduce((a, b) => a + b, 0) / speeds.length : 0,
      avgThrottle: throttles.length ? throttles.reduce((a, b) => a + b, 0) / throttles.length : 0,
      brakeZones: Math.round(brakes.length / (telemetry.length || 1) * 100),
      drsUsage: Math.round(drsZones.length / (telemetry.length || 1) * 100),
      points: telemetry.length,
    };
  }, [telemetry]);

  const validLaps = useMemo(() => laps.filter(l => l.is_valid && l.lap_time_ms).sort((a, b) => a.lap_number - b.lap_number), [laps]);
  const tColor = selDriver ? (selDriver.team_color || teamColor(selDriver.team)) : '#e8002d';

  return (
    <div className="content-area">
      {/* Controls */}
      <div className="filter-bar">
        <div className="filter-group">
          <span className="filter-label">Event</span>
          <select className="filter-select" value={sessionId} onChange={e => setSessionId(e.target.value)}>
            {sessions.map(s => <option key={s.session_id} value={s.session_id}>{s.event_name} {s.year}</option>)}
          </select>
        </div>
        <div className="filter-divider" />
        <div className="filter-group">
          <span className="filter-label">Driver</span>
          <select className="filter-select" value={driverId} onChange={e => setDriverId(e.target.value)}>
            {standings.map(s => <option key={s.driver_id} value={s.driver_id}>P{s.position} {s.driver_code}</option>)}
          </select>
        </div>
        <div className="filter-divider" />
        <div className="filter-group">
          <span className="filter-label">Lap</span>
          <select className="filter-select" value={lapId} onChange={e => setLapId(e.target.value)}>
            {validLaps.map(l => (
              <option key={l.lap_id} value={l.lap_id}>
                Lap {l.lap_number} — {msToLapTime(l.lap_time_ms)} {l.compound ? `(${l.compound[0]})` : ''}
              </option>
            ))}
          </select>
        </div>
        <div className="filter-spacer" />
        <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{telemetry.length} telemetry pts</span>
      </div>

      <div className="content-area" style={{ padding: 0 }}>
        {/* KPI row */}
        {telStats && (
          <div className="kpi-row" style={{ marginBottom: 10 }}>
            {[
              ['Top Speed', `${Math.round(telStats.topSpeed)} km/h`, '#60a5fa'],
              ['Avg Speed', `${telStats.avgSpeed.toFixed(1)} km/h`, '#34d399'],
              ['Avg Throttle', `${telStats.avgThrottle.toFixed(0)}%`, '#34d399'],
              ['Braking', `${telStats.brakeZones}% of lap`, '#f87171'],
              ['DRS Usage', `${telStats.drsUsage}%`, '#c084fc'],
              ['Data Points', telStats.points, 'var(--text-muted)'],
            ].map(([label, value, color]) => (
              <div key={label} className="kpi-card">
                <div className="kpi-label">{label}</div>
                <div className="kpi-value" style={{ color, fontSize: 14 }}>{value}</div>
              </div>
            ))}
          </div>
        )}

        {/* Row 1: Track Map + Multi-channel chart */}
        <div className="grid-2-5" style={{ marginBottom: 10 }}>
          <div className="card">
            <div className="card-header">
              <span className="card-title">Track Map — Speed</span>
              {selDriver && <span style={{ fontSize: 10, color: tColor, fontWeight: 700 }}>{selDriver.code}</span>}
            </div>
            <div className="card-body" style={{ padding: 8 }}>
              {loading ? <div className="loading-state" style={{ height: 200 }}><div className="spinner" /></div> : <TrackMap telemetry={telemetry} />}
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <span className="card-title">Speed / Throttle / Brake</span>
              <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>Lap {selectedLap?.lap_number} — {msToLapTime(selectedLap?.lap_time_ms)}</span>
            </div>
            <div className="card-body">
              {loading ? <div className="loading-state" style={{ height: 165 }}><div className="spinner" /></div> : (
                chartData.length ? (
                  <ResponsiveContainer width="100%" height={165}>
                    <ComposedChart data={chartData} margin={{ top: 4, right: 36, bottom: 16, left: 2 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(48,54,61,0.45)" vertical={false} />
                      <XAxis dataKey="dist" tick={{ fontSize: 8, fill: '#6e7681', fontFamily: 'monospace' }} tickLine={false}
                        label={{ value: 'Distance (m)', position: 'insideBottom', offset: -6, fontSize: 8, fill: '#6e7681' }} />
                      <YAxis yAxisId="spd" domain={[0, 360]} tick={{ fontSize: 8, fill: '#6e7681', fontFamily: 'monospace' }} tickLine={false} axisLine={false} width={24} />
                      <YAxis yAxisId="pct" orientation="right" domain={[0, 100]} tick={{ fontSize: 8, fill: '#6e7681', fontFamily: 'monospace' }} tickLine={false} axisLine={false} width={18} />
                      <Tooltip contentStyle={{ background: 'rgba(22,27,34,0.97)', border: '1px solid rgba(48,54,61,0.9)', borderRadius: 4, fontSize: 10 }} />
                      <Area yAxisId="pct" type="step" dataKey="drs" fill="rgba(129,140,248,0.18)" stroke="rgba(129,140,248,0.5)" strokeWidth={0.8} dot={false} name="DRS" />
                      <Line yAxisId="spd" type="monotone" dataKey="speed" stroke="#60a5fa" strokeWidth={1.5} dot={false} name="Speed (km/h)" />
                      <Line yAxisId="pct" type="monotone" dataKey="throttle" stroke="#34d399" strokeWidth={1.2} dot={false} name="Throttle (%)" />
                      <Line yAxisId="pct" type="step" dataKey="brake" stroke="#f87171" strokeWidth={1.2} dot={false} name="Brake (%)" />
                    </ComposedChart>
                  </ResponsiveContainer>
                ) : <div className="empty-state" style={{ height: 165 }}>No telemetry data</div>
              )}
            </div>
          </div>
        </div>

        {/* Channel selector + focused chart */}
        <div className="card" style={{ marginBottom: 10 }}>
          <div className="card-header">
            <span className="card-title">Channel Explorer</span>
            <div style={{ display: 'flex', gap: 4 }}>
              {CHANNELS.map(ch => (
                <button key={ch.key}
                  onClick={() => setActiveChannel(ch.key)}
                  style={{
                    padding: '2px 8px', borderRadius: 10, fontSize: 9, fontWeight: 600, border: 'none', cursor: 'pointer',
                    background: activeChannel === ch.key ? ch.color : 'var(--bg-card)',
                    color: activeChannel === ch.key ? '#0d1117' : 'var(--text-muted)',
                    transition: 'all 0.15s',
                  }}>
                  {ch.label}
                </button>
              ))}
            </div>
          </div>
          <div className="card-body">
            {loading ? <div className="loading-state" style={{ height: 130 }}><div className="spinner" /></div> : (
              chartData.length ? (
                <ResponsiveContainer width="100%" height={130}>
                  <LineChart data={chartData} margin={{ top: 4, right: 12, bottom: 16, left: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(48,54,61,0.45)" vertical={false} />
                    <XAxis dataKey="dist" tick={{ fontSize: 8, fill: '#6e7681', fontFamily: 'monospace' }} tickLine={false}
                      label={{ value: 'Distance (m)', position: 'insideBottom', offset: -10, fontSize: 8, fill: '#6e7681' }} />
                    <YAxis domain={channel.domain} tick={{ fontSize: 8, fill: '#6e7681', fontFamily: 'monospace' }} tickLine={false} axisLine={false} width={32} />
                    <Tooltip formatter={(v) => [`${v} ${channel.unit}`, channel.label]}
                      contentStyle={{ background: 'rgba(22,27,34,0.97)', border: '1px solid rgba(48,54,61,0.9)', borderRadius: 4, fontSize: 10 }} />
                    <Line type="monotone" dataKey={channel.key} stroke={channel.color} strokeWidth={1.5} dot={false} name={channel.label} />
                  </LineChart>
                </ResponsiveContainer>
              ) : <div className="empty-state" style={{ height: 130 }}>Select a lap to view telemetry</div>
            )}
          </div>
        </div>

        {/* Gear trace */}
        {chartData.length > 0 && (
          <div className="card">
            <div className="card-header"><span className="card-title">Gear Trace</span></div>
            <div className="card-body">
              <ResponsiveContainer width="100%" height={80}>
                <BarChart data={chartData} margin={{ top: 2, right: 12, bottom: 12, left: 8 }} barCategoryGap={0}>
                  <XAxis dataKey="dist" tick={{ fontSize: 7, fill: '#6e7681' }} tickLine={false}
                    label={{ value: 'Distance (m)', position: 'insideBottom', offset: -8, fontSize: 7, fill: '#6e7681' }} />
                  <YAxis domain={[0, 8]} tick={{ fontSize: 7, fill: '#6e7681' }} tickLine={false} axisLine={false} width={16} ticks={[0, 2, 4, 6, 8]} />
                  <Tooltip formatter={v => [`Gear ${v}`, '']}
                    contentStyle={{ background: 'rgba(22,27,34,0.97)', border: '1px solid rgba(48,54,61,0.9)', borderRadius: 4, fontSize: 10 }} />
                  <Bar dataKey="gear" fill="#c084fc" opacity={0.7} maxBarSize={4} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
