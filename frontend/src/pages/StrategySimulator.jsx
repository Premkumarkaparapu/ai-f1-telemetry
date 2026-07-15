import { useState, useEffect, useMemo } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Legend,
} from 'recharts';
import { api } from '../api.js';
import { msToLapTime, formatRaceTime, CompoundBadge } from '../utils.jsx';

const COMPOUNDS = ['SOFT', 'MEDIUM', 'HARD'];
const COMPOUND_COLORS = { SOFT: '#e8002d', MEDIUM: '#fbbf24', HARD: '#f0f6fc' };
const TOTAL_LAPS = 57;

export default function StrategySimulator() {
  const [sessions, setSessions] = useState([]);
  const [sessionId, setSessionId] = useState('1');
  const [session, setSession] = useState(null);
  const [drivers, setDrivers] = useState([]);
  const [driverId, setDriverId] = useState('');
  const [pitLaps, setPitLaps] = useState([17, 37]);
  const [compounds, setCompounds] = useState(['SOFT', 'HARD', 'SOFT']);
  const [pitLossMs, setPitLossMs] = useState(25000);
  const [result, setResult] = useState(null);
  const [pitWindow, setPitWindow] = useState(null);
  const [loading, setLoading] = useState(false);
  const [simError, setSimError] = useState(null);

  useEffect(() => {
    api.getSessions().then(s => { setSessions(s); if (s.length) setSessionId(String(s[0].session_id)); }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!sessionId) return;
    Promise.allSettled([api.getSession(sessionId), api.getDrivers(sessionId)]).then(([sR, dR]) => {
      if (sR.status === 'fulfilled') setSession(sR.value);
      if (dR.status === 'fulfilled') {
        setDrivers(dR.value);
        if (dR.value.length) setDriverId(String(dR.value[0].driver_id));
      }
    });
  }, [sessionId]);

  const totalLaps = session?.total_laps ?? TOTAL_LAPS;
  const numStints = pitLaps.length + 1;

  function addPit() {
    if (pitLaps.length >= 4) return;
    const newLap = Math.round(totalLaps / (pitLaps.length + 2));
    const newPits = [...pitLaps, newLap].sort((a, b) => a - b);
    setPitLaps(newPits);
    setCompounds(Array(newPits.length + 1).fill('MEDIUM').map((_, i) => compounds[i] ?? 'MEDIUM'));
  }

  function removePit(idx) {
    const newPits = pitLaps.filter((_, i) => i !== idx);
    setPitLaps(newPits);
    setCompounds(compounds.filter((_, i) => i !== idx));
  }

  function updatePitLap(idx, val) {
    const updated = [...pitLaps];
    updated[idx] = Math.max(1, Math.min(totalLaps - 1, +val));
    setPitLaps(updated.sort((a, b) => a - b));
  }

  function updateCompound(stintIdx, compound) {
    const updated = [...compounds];
    updated[stintIdx] = compound;
    setCompounds(updated);
  }

  async function simulate() {
    setLoading(true); setSimError(null); setResult(null); setPitWindow(null);
    try {
      const [simResult] = await Promise.allSettled([
        api.simulateStrategy({ session_id: +sessionId, driver_id: +driverId, pit_laps: pitLaps, compounds, pit_time_loss_ms: pitLossMs }),
      ]);
      if (simResult.status === 'fulfilled') setResult(simResult.value);
      else setSimError(simResult.reason?.message ?? 'Simulation failed');

      // Pit window
      if (driverId) {
        const pwR = await api.getPitWindow(+sessionId, +driverId, pitLaps[0] ?? 10).catch(() => null);
        if (pwR) setPitWindow(pwR);
      }
    } finally {
      setLoading(false);
    }
  }

  const chartData = useMemo(() => {
    if (!result?.per_lap_times_ms) return [];
    return result.per_lap_times_ms.map((t, i) => ({
      lap: i + 1,
      time: +(t / 1000).toFixed(3),
    }));
  }, [result]);

  return (
    <div className="content-area">
      <div className="page-header">
        <div>
          <div className="page-title">🏁 Strategy Simulator</div>
          <div className="page-desc">Build race strategies and simulate total race time with ML lap time predictions</div>
        </div>
      </div>

      {/* Session / Driver */}
      <div className="card" style={{ marginBottom: 10 }}>
        <div className="card-body" style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'center' }}>
          <div className="filter-group">
            <span className="filter-label">Event</span>
            <select className="filter-select" value={sessionId} onChange={e => setSessionId(e.target.value)}>
              {sessions.map(s => <option key={s.session_id} value={s.session_id}>{s.event_name} {s.year}</option>)}
            </select>
          </div>
          <div className="filter-group">
            <span className="filter-label">Driver</span>
            <select className="filter-select" value={driverId} onChange={e => setDriverId(e.target.value)}>
              {drivers.map(d => <option key={d.driver_id} value={d.driver_id}>{d.code} — {d.team}</option>)}
            </select>
          </div>
          <div className="filter-group">
            <span className="filter-label">Pit Loss: {(pitLossMs / 1000).toFixed(0)}s</span>
            <input type="range" min={18000} max={35000} step={500} value={pitLossMs}
              onChange={e => setPitLossMs(+e.target.value)}
              style={{ width: 130, accentColor: 'var(--f1-red)', marginTop: 4 }} />
          </div>
        </div>
      </div>

      {/* Strategy Builder */}
      <div className="card" style={{ marginBottom: 10 }}>
        <div className="card-header">
          <span className="card-title">Strategy Builder</span>
          <button onClick={addPit} disabled={pitLaps.length >= 4}
            style={{ padding: '4px 12px', borderRadius: 4, border: '1px solid var(--f1-red)', background: 'transparent',
              color: 'var(--f1-red)', cursor: 'pointer', fontSize: 11, fontWeight: 600 }}>
            + Add Pit Stop
          </button>
        </div>
        <div className="card-body">
          {/* Lap timeline */}
          <div style={{ position: 'relative', marginBottom: 20 }}>
            <div style={{ height: 12, background: 'rgba(48,54,61,0.6)', borderRadius: 6, overflow: 'visible', position: 'relative' }}>
              {/* Stint segments */}
              {[0, ...pitLaps, totalLaps].reduce((acc, lap, i, arr) => {
                if (i === 0) return acc;
                const prev = arr[i - 1];
                const compound = compounds[i - 1] ?? 'MEDIUM';
                const left = ((prev) / totalLaps * 100).toFixed(2) + '%';
                const width = ((lap - prev) / totalLaps * 100).toFixed(2) + '%';
                acc.push(
                  <div key={i} style={{
                    position: 'absolute', left, width, height: '100%', borderRadius: i === 1 ? '6px 0 0 6px' : i === arr.length - 1 ? '0 6px 6px 0' : '0',
                    background: COMPOUND_COLORS[compound] ?? '#888', opacity: 0.7, top: 0,
                  }} />
                );
                return acc;
              }, [])}
              {/* Pit markers */}
              {pitLaps.map((lap, idx) => (
                <div key={idx} style={{
                  position: 'absolute', left: `${(lap / totalLaps * 100).toFixed(2)}%`,
                  width: 2, height: '100%', background: 'white', top: 0, transform: 'translateX(-50%)',
                }} />
              ))}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
              <span style={{ fontSize: 8, color: 'var(--text-muted)', fontFamily: 'monospace' }}>Lap 1</span>
              <span style={{ fontSize: 8, color: 'var(--text-muted)', fontFamily: 'monospace' }}>Lap {totalLaps}</span>
            </div>
          </div>

          {/* Stint rows */}
          {Array.from({ length: numStints }, (_, i) => {
            const startLap = i === 0 ? 1 : pitLaps[i - 1];
            const endLap = i === numStints - 1 ? totalLaps : pitLaps[i];
            const stintLen = endLap - startLap;
            return (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8, padding: '8px 10px',
                background: 'rgba(22,27,34,0.5)', borderRadius: 6, border: '1px solid rgba(48,54,61,0.5)' }}>
                <CompoundBadge compound={compounds[i]} size={22} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Stint {i + 1}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-primary)', fontFamily: 'monospace' }}>
                    Laps {startLap} – {endLap} <span style={{ color: 'var(--text-muted)', fontSize: 10 }}>({stintLen} laps)</span>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 4 }}>
                  {COMPOUNDS.map(c => (
                    <button key={c} onClick={() => updateCompound(i, c)}
                      style={{ padding: '3px 8px', borderRadius: 3, border: `1px solid ${compounds[i] === c ? COMPOUND_COLORS[c] : 'rgba(48,54,61,0.8)'}`,
                        background: compounds[i] === c ? `${COMPOUND_COLORS[c]}22` : 'transparent',
                        color: compounds[i] === c ? COMPOUND_COLORS[c] : 'var(--text-muted)',
                        cursor: 'pointer', fontSize: 10, fontWeight: 600 }}>
                      {c[0]}
                    </button>
                  ))}
                </div>
                {i > 0 && i < numStints - 1 && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <span style={{ fontSize: 9, color: 'var(--text-muted)' }}>Pit Lap:</span>
                    <input type="number" min={1} max={totalLaps} value={pitLaps[i - 1]}
                      onChange={e => updatePitLap(i - 1, e.target.value)}
                      style={{ width: 52, background: 'rgba(22,27,34,0.8)', border: '1px solid rgba(48,54,61,0.8)',
                        borderRadius: 3, padding: '2px 6px', color: 'var(--text-primary)', fontSize: 11, fontFamily: 'monospace' }} />
                    <button onClick={() => removePit(i - 1)}
                      style={{ padding: '2px 6px', borderRadius: 3, border: '1px solid rgba(248,113,113,0.4)', background: 'transparent',
                        color: '#f87171', cursor: 'pointer', fontSize: 11 }}>✕</button>
                  </div>
                )}
              </div>
            );
          })}

          <button className="btn btn-primary" style={{ marginTop: 8, width: '100%' }} onClick={simulate} disabled={loading}>
            {loading ? '⏳ Simulating…' : '▶ Simulate Race Strategy'}
          </button>
          {simError && <div style={{ marginTop: 8, padding: 8, background: 'rgba(248,113,113,0.1)', border: '1px solid rgba(248,113,113,0.3)', borderRadius: 4, color: '#f87171', fontSize: 11 }}>{simError}</div>}
        </div>
      </div>

      {/* Results */}
      {result && (
        <>
          {/* KPI row */}
          <div className="kpi-row" style={{ marginBottom: 10 }}>
            <div className="kpi-card">
              <div className="kpi-label">Total Race Time</div>
              <div className="kpi-value purple" style={{ fontSize: 20 }}>{formatRaceTime(result.total_race_time_ms)}</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">Pit Stops</div>
              <div className="kpi-value">{result.pit_stops}</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">vs No-Strategy</div>
              <div className="kpi-value" style={{ color: result.vs_baseline_ms <= 0 ? '#34d399' : '#f87171' }}>
                {result.vs_baseline_ms != null ? (result.vs_baseline_ms <= 0 ? '' : '+') + formatRaceTime(Math.abs(result.vs_baseline_ms)) : '—'}
              </div>
              <div className="kpi-sub" style={{ color: result.vs_baseline_ms <= 0 ? '#34d399' : '#f87171' }}>
                {result.vs_baseline_ms != null ? (result.vs_baseline_ms <= 0 ? '✅ Faster' : '❌ Slower') : ''}
              </div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">Compounds Used</div>
              <div style={{ display: 'flex', gap: 4, marginTop: 6 }}>
                {result.compounds_used?.map((c, i) => <CompoundBadge key={i} compound={c} size={22} />) ??
                  compounds.map((c, i) => <CompoundBadge key={i} compound={c} size={22} />)}
              </div>
            </div>
          </div>

          {/* Lap time chart */}
          <div className="card" style={{ marginBottom: 10 }}>
            <div className="card-header">
              <span className="card-title">Simulated Lap Times</span>
              <span style={{ fontSize: 9, color: 'var(--text-muted)' }}>||| = pit stops</span>
            </div>
            <div className="card-body">
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={chartData} margin={{ top: 4, right: 12, bottom: 20, left: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(48,54,61,0.45)" vertical={false} />
                  <XAxis dataKey="lap" tick={{ fontSize: 8, fill: '#6e7681', fontFamily: 'monospace' }} tickLine={false}
                    label={{ value: 'Lap Number', position: 'insideBottom', offset: -12, fontSize: 9, fill: '#6e7681' }} />
                  <YAxis tick={{ fontSize: 8, fill: '#6e7681', fontFamily: 'monospace' }} tickLine={false} axisLine={false} width={32}
                    label={{ value: 'Lap Time (s)', angle: -90, position: 'insideLeft', offset: 12, fontSize: 9, fill: '#6e7681' }}
                    domain={['auto', 'auto']} />
                  <Tooltip formatter={v => [`${v}s`, 'Lap Time']} labelFormatter={l => `Lap ${l}`}
                    contentStyle={{ background: 'rgba(22,27,34,0.97)', border: '1px solid rgba(48,54,61,0.9)', borderRadius: 4, fontSize: 10 }} />
                  {pitLaps.map(pl => (
                    <ReferenceLine key={pl} x={pl} stroke="rgba(232,0,45,0.6)" strokeDasharray="4 3"
                      label={{ value: 'Pit', position: 'top', fontSize: 8, fill: '#e8002d' }} />
                  ))}
                  <Line type="monotone" dataKey="time" stroke="#60a5fa" strokeWidth={1.5}
                    dot={{ r: 1.5, fill: '#60a5fa' }} activeDot={{ r: 3 }} name="Lap Time (s)" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </>
      )}

      {/* Pit Window */}
      {pitWindow && (
        <div className="card">
          <div className="card-header"><span className="card-title">🪟 Optimal Pit Window</span></div>
          <div className="card-body">
            <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', alignItems: 'center' }}>
              {[
                ['Earliest', pitWindow.earliest_lap, '#8b949e'],
                ['Optimal', pitWindow.optimal_lap, '#34d399'],
                ['Latest', pitWindow.latest_lap, '#f87171'],
              ].map(([label, lap, color]) => (
                <div key={label} style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 9, color: 'var(--text-muted)', textTransform: 'uppercase' }}>{label}</div>
                  <div style={{ fontSize: 28, fontWeight: 800, fontFamily: 'monospace', color }}>Lap {lap}</div>
                </div>
              ))}
              <div style={{ flex: 1, padding: '8px 12px', background: 'rgba(52,211,153,0.08)', border: '1px solid rgba(52,211,153,0.2)', borderRadius: 6, fontSize: 11, color: '#34d399' }}>
                💡 {pitWindow.reasoning}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
