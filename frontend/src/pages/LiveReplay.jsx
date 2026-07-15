import { useState, useEffect, useMemo } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, ScatterChart, Scatter,
} from 'recharts';
import { api } from '../api.js';
import { msToLapTime, CompoundBadge, compoundColor } from '../utils.jsx';

const COMPOUNDS = ['SOFT', 'MEDIUM', 'HARD'];
const COMPOUND_COLORS = { SOFT: '#e8002d', MEDIUM: '#fbbf24', HARD: '#f0f6fc' };

export default function LiveReplay() {
  const [sessions, setSessions] = useState([]);
  const [sessionId, setSessionId] = useState('1');
  const [drivers, setDrivers] = useState([]);
  const [driverId, setDriverId] = useState('');
  const [laps, setLaps] = useState([]);
  const [compound, setCompound] = useState('SOFT');
  const [tyreLife, setTyreLife] = useState(10);
  const [lapNumber, setLapNumber] = useState(20);
  const [predicted, setPredicted] = useState(null);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([]);
  const [degradationData, setDegradationData] = useState(null);

  useEffect(() => {
    api.getSessions().then(s => { setSessions(s); if (s.length) setSessionId(String(s[0].session_id)); }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!sessionId) return;
    api.getDrivers(sessionId).then(d => {
      setDrivers(d);
      if (d.length) setDriverId(String(d[0].driver_id));
    }).catch(() => {});
  }, [sessionId]);

  useEffect(() => {
    if (!driverId) return;
    api.getLaps(driverId).then(l => {
      const valid = l.filter(x => x.is_valid && x.lap_time_ms);
      setLaps(valid);
    }).catch(() => {});
    // Fetch prediction history
    api.getPredictionHistory(sessionId).then(setHistory).catch(() => setHistory([]));
  }, [driverId, sessionId]);

  // Load degradation curve whenever compound changes
  useEffect(() => {
    api.getDegradation(compound, 50).then(setDegradationData).catch(() => setDegradationData(null));
  }, [compound]);

  async function runPrediction() {
    setLoading(true);
    try {
      const result = await api.predict({ session_id: +sessionId, driver_id: +driverId, prediction_type: 'lap_time' });
      setPredicted(result);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  // Actual laps scatter data grouped by compound
  const actualScatter = useMemo(() => {
    const byCompound = {};
    laps.forEach(l => {
      if (!l.tyre_life || !l.lap_time_ms) return;
      const c = l.compound ?? 'HARD';
      if (!byCompound[c]) byCompound[c] = [];
      byCompound[c].push({ tyre_life: l.tyre_life, lap_time_s: +(l.lap_time_ms / 1000).toFixed(3) });
    });
    return byCompound;
  }, [laps]);

  // ML prediction line for selected compound
  const predLine = useMemo(() => {
    if (!degradationData) return [];
    return (degradationData.tyre_life_values ?? []).map((life, i) => ({
      tyre_life: life,
      predicted_s: +((degradationData.predicted_lap_times_ms?.[i] ?? 0) / 1000).toFixed(3),
    }));
  }, [degradationData]);

  // Merge for combo chart
  const comboData = useMemo(() => {
    const all = {};
    predLine.forEach(p => { all[p.tyre_life] = { tyre_life: p.tyre_life, predicted_s: p.predicted_s }; });
    (actualScatter[compound] ?? []).forEach(p => {
      if (!all[p.tyre_life]) all[p.tyre_life] = { tyre_life: p.tyre_life };
      all[p.tyre_life].actual_s = p.lap_time_s;
    });
    return Object.values(all).sort((a, b) => a.tyre_life - b.tyre_life);
  }, [predLine, actualScatter, compound]);

  const drv = useMemo(() => drivers.find(d => String(d.driver_id) === driverId), [drivers, driverId]);
  const bestLap = useMemo(() => {
    if (!laps.length) return null;
    return laps.reduce((a, b) => a.lap_time_ms < b.lap_time_ms ? a : b);
  }, [laps]);

  return (
    <div className="content-area">
      <div className="page-header">
        <div>
          <div className="page-title">🤖 Lap Time Predictor</div>
          <div className="page-desc">ML-powered lap time prediction using XGBoost model — actual vs predicted comparison</div>
        </div>
      </div>

      {/* Session / Driver / Controls */}
      <div className="card" style={{ marginBottom: 10 }}>
        <div className="card-header"><span className="card-title">Model Inputs</span></div>
        <div className="card-body" style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'flex-end' }}>
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
          <div>
            <div style={{ fontSize: 9, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 4 }}>Compound</div>
            <div style={{ display: 'flex', gap: 6 }}>
              {COMPOUNDS.map(c => (
                <button key={c} onClick={() => setCompound(c)}
                  style={{ padding: '4px 10px', borderRadius: 4, border: `1px solid ${compound === c ? COMPOUND_COLORS[c] : 'rgba(48,54,61,0.8)'}`,
                    background: compound === c ? `${COMPOUND_COLORS[c]}22` : 'transparent',
                    color: compound === c ? COMPOUND_COLORS[c] : 'var(--text-muted)',
                    cursor: 'pointer', fontSize: 11, fontWeight: 600 }}>
                  {c}
                </button>
              ))}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 9, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 4 }}>Tyre Life: <span style={{ color: 'var(--text-primary)', fontFamily: 'monospace' }}>{tyreLife}</span></div>
            <input type="range" min={1} max={50} value={tyreLife} onChange={e => setTyreLife(+e.target.value)}
              style={{ width: 120, accentColor: COMPOUND_COLORS[compound] }} />
          </div>
          <div>
            <div style={{ fontSize: 9, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 4 }}>Lap #</div>
            <input type="number" min={1} max={57} value={lapNumber} onChange={e => setLapNumber(+e.target.value)}
              style={{ width: 60, background: 'rgba(22,27,34,0.8)', border: '1px solid rgba(48,54,61,0.8)',
                borderRadius: 4, padding: '4px 8px', color: 'var(--text-primary)', fontSize: 12, fontFamily: 'monospace' }} />
          </div>
          <button className="btn btn-primary" onClick={runPrediction} disabled={loading}>
            {loading ? '⏳…' : '🤖 Predict Lap Time'}
          </button>
        </div>
      </div>

      {/* Predicted value display */}
      <div className="grid-2" style={{ marginBottom: 10 }}>
        <div className="card" style={{ background: 'linear-gradient(135deg, rgba(192,132,252,0.08) 0%, rgba(22,27,34,0) 100%)', border: '1px solid rgba(192,132,252,0.2)' }}>
          <div className="card-header"><span className="card-title">🤖 ML Prediction</span></div>
          <div className="card-body" style={{ textAlign: 'center', padding: '20px 16px' }}>
            {predicted ? (
              <>
                <div style={{ fontSize: 42, fontWeight: 900, fontFamily: 'monospace', color: '#c084fc', letterSpacing: '-1px' }}>
                  {msToLapTime(predicted.predicted_value)}
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>
                  Model: {predicted.model_name} · v{predicted.model_version ?? '1.0'}
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
                  Type: {predicted.prediction_type ?? 'lap_time'}
                </div>
              </>
            ) : (
              <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>
                Press <strong>Predict Lap Time</strong> to run the XGBoost model
              </div>
            )}
          </div>
        </div>

        <div className="card">
          <div className="card-header"><span className="card-title">📊 Driver Reference</span></div>
          <div className="card-body">
            {drv && (
              <>
                {[
                  ['Driver', `${drv.code} — ${drv.team}`],
                  ['Best Actual Lap', msToLapTime(bestLap?.lap_time_ms)],
                  ['Best Lap Number', bestLap ? `Lap ${bestLap.lap_number}` : '—'],
                  ['Compound (Best)', bestLap?.compound ?? '—'],
                  ['Tyre Age (Best)', bestLap ? `${bestLap.tyre_life} laps` : '—'],
                  ['Total Valid Laps', laps.length],
                ].map(([k, v]) => (
                  <div key={k} className="lap-info-row">
                    <span className="lap-info-label">{k}</span>
                    <span className="lap-info-value">{v}</span>
                  </div>
                ))}
              </>
            )}
          </div>
        </div>
      </div>

      {/* Actual vs Predicted chart */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Actual vs ML Predicted — {compound}</span>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <span style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
              <div style={{ width: 10, height: 10, borderRadius: '50%', background: COMPOUND_COLORS[compound], opacity: 0.7 }} />
              <span style={{ fontSize: 9, color: 'var(--text-muted)' }}>Actual laps</span>
            </span>
            <span style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
              <div style={{ width: 14, height: 2, background: '#c084fc' }} />
              <span style={{ fontSize: 9, color: 'var(--text-muted)' }}>ML prediction</span>
            </span>
          </div>
        </div>
        <div className="card-body">
          {!comboData.length
            ? <div className="empty-state">No data for {compound} compound</div>
            : (
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={comboData} margin={{ top: 8, right: 12, bottom: 20, left: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(48,54,61,0.45)" vertical={false} />
                  <XAxis dataKey="tyre_life" tick={{ fontSize: 8, fill: '#6e7681', fontFamily: 'monospace' }} tickLine={false}
                    label={{ value: 'Tyre Life (laps)', position: 'insideBottom', offset: -12, fontSize: 9, fill: '#6e7681' }} />
                  <YAxis tick={{ fontSize: 8, fill: '#6e7681', fontFamily: 'monospace' }} tickLine={false} axisLine={false} width={32}
                    label={{ value: 'Lap Time (s)', angle: -90, position: 'insideLeft', offset: 12, fontSize: 9, fill: '#6e7681' }}
                    domain={['auto', 'auto']} />
                  <Tooltip formatter={(v, name) => [`${v}s`, name]}
                    contentStyle={{ background: 'rgba(22,27,34,0.97)', border: '1px solid rgba(48,54,61,0.9)', borderRadius: 4, fontSize: 10 }} />
                  <Legend wrapperStyle={{ fontSize: 9 }} />
                  <Line type="monotone" dataKey="predicted_s" stroke="#c084fc" strokeWidth={2} dot={false} name="ML Predicted (s)" />
                  <Line type="monotone" dataKey="actual_s" stroke={COMPOUND_COLORS[compound]}
                    strokeWidth={0} dot={{ r: 3, fill: COMPOUND_COLORS[compound], opacity: 0.8 }}
                    activeDot={{ r: 4 }} name="Actual (s)" connectNulls={false} />
                </LineChart>
              </ResponsiveContainer>
            )}
        </div>
      </div>
    </div>
  );
}
