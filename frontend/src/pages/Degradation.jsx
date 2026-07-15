import { useState, useEffect, useMemo } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, BarChart, Bar,
} from 'recharts';
import { api } from '../api.js';
import { msToLapTime, compoundColor, CompoundBadge } from '../utils.jsx';

const COMPOUNDS = ['SOFT', 'MEDIUM', 'HARD', 'INTERMEDIATE'];
const COMPOUND_COLORS = { SOFT: '#e8002d', MEDIUM: '#fbbf24', HARD: '#f0f6fc', INTERMEDIATE: '#34d399' };

export default function Degradation() {
  const [selected, setSelected] = useState(['SOFT', 'MEDIUM', 'HARD']);
  const [maxLife, setMaxLife] = useState(40);
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  function toggle(c) {
    setSelected(prev => prev.includes(c) ? prev.filter(x => x !== c) : [...prev, c]);
  }

  async function loadCurves() {
    if (!selected.length) return;
    setLoading(true); setError(null);
    try {
      const results = await Promise.allSettled(selected.map(c => api.getDegradation(c, maxLife)));
      const map = {};
      results.forEach((r, i) => {
        if (r.status === 'fulfilled') map[selected[i]] = r.value;
      });
      setData(map);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  // Build chart data: [{tyre_life, SOFT: s, MEDIUM: m, HARD: h}]
  const chartData = useMemo(() => {
    const entries = Object.entries(data);
    if (!entries.length) return [];
    const maxLen = Math.max(...entries.map(([, v]) => v.tyre_life_values?.length ?? 0));
    return Array.from({ length: maxLen }, (_, i) => {
      const row = { tyre_life: i + 1 };
      entries.forEach(([compound, v]) => {
        if (v.predicted_lap_times_ms?.[i] != null) {
          row[compound] = +(v.predicted_lap_times_ms[i] / 1000).toFixed(3);
        }
      });
      return row;
    });
  }, [data]);

  // Bar chart: compare compounds at laps 5, 15, 25
  const barData = useMemo(() => {
    return [5, 15, 25, 35].map(life => {
      const row = { life: `Lap ${life}` };
      Object.entries(data).forEach(([compound, v]) => {
        const idx = (v.tyre_life_values ?? []).indexOf(life);
        if (idx >= 0 && v.predicted_lap_times_ms?.[idx] != null) {
          row[compound] = +(v.predicted_lap_times_ms[idx] / 1000).toFixed(3);
        }
      });
      return row;
    });
  }, [data]);

  // Stats per compound
  const stats = useMemo(() => {
    return Object.entries(data).map(([compound, v]) => {
      const times = v.predicted_lap_times_ms ?? [];
      if (!times.length) return null;
      const minTime = Math.min(...times);
      const maxTime = Math.max(...times);
      const degradation = maxTime - minTime;
      const optimalLap = v.tyre_life_values?.[times.indexOf(minTime)] ?? 1;
      return { compound, minTime, maxTime, degradation, optimalLap, modelType: v.model_type };
    }).filter(Boolean);
  }, [data]);

  return (
    <div className="content-area">
      <div className="page-header">
        <div>
          <div className="page-title">🏎️ Tyre Degradation Analysis</div>
          <div className="page-desc">ML-predicted degradation curves per compound — 2024 Bahrain GP</div>
        </div>
      </div>

      {/* Controls */}
      <div className="card" style={{ marginBottom: 10 }}>
        <div className="card-body" style={{ display: 'flex', alignItems: 'center', gap: 20, flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Compounds</div>
            <div style={{ display: 'flex', gap: 8 }}>
              {COMPOUNDS.map(c => (
                <button key={c} onClick={() => toggle(c)}
                  style={{ padding: '5px 14px', borderRadius: 4, border: `1px solid ${selected.includes(c) ? COMPOUND_COLORS[c] : 'rgba(48,54,61,0.8)'}`,
                    background: selected.includes(c) ? `${COMPOUND_COLORS[c]}22` : 'transparent',
                    color: selected.includes(c) ? COMPOUND_COLORS[c] : 'var(--text-muted)',
                    cursor: 'pointer', fontSize: 11, fontWeight: 600, transition: 'all 0.15s' }}>
                  {c}
                </button>
              ))}
            </div>
          </div>
          <div style={{ flex: 1, minWidth: 160 }}>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Max Tyre Life: <span style={{ color: 'var(--text-primary)', fontFamily: 'monospace' }}>{maxLife} laps</span>
            </div>
            <input type="range" min={10} max={60} value={maxLife} onChange={e => setMaxLife(+e.target.value)}
              style={{ width: '100%', accentColor: 'var(--f1-red)' }} />
          </div>
          <button className="btn btn-primary" onClick={loadCurves} disabled={loading}>
            {loading ? '⏳ Loading…' : '📈 Load Curves'}
          </button>
        </div>
      </div>

      {error && <div style={{ padding: '10px 14px', background: 'rgba(248,113,113,0.1)', border: '1px solid rgba(248,113,113,0.3)', borderRadius: 6, color: '#f87171', marginBottom: 10 }}>{error}</div>}

      {!chartData.length && !loading && (
        <div className="empty-state" style={{ height: 200 }}>
          <span style={{ fontSize: 40 }}>🏁</span>
          <span>Select compounds and click <strong>Load Curves</strong> to see ML predictions</span>
        </div>
      )}

      {loading && <div className="loading-state"><div className="spinner" /><span>Loading ML degradation models…</span></div>}

      {chartData.length > 0 && (
        <>
          {/* Main degradation chart */}
          <div className="card" style={{ marginBottom: 10 }}>
            <div className="card-header">
              <span className="card-title">Predicted Lap Time vs Tyre Life</span>
              <div style={{ display: 'flex', gap: 10 }}>
                {Object.keys(data).map(c => (
                  <span key={c} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <div style={{ width: 12, height: 2, background: COMPOUND_COLORS[c] }} />
                    <span style={{ fontSize: 9, color: COMPOUND_COLORS[c], fontWeight: 600 }}>{c}</span>
                  </span>
                ))}
              </div>
            </div>
            <div className="card-body">
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 20, left: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(48,54,61,0.45)" vertical={false} />
                  <XAxis dataKey="tyre_life" tick={{ fontSize: 8, fill: '#6e7681', fontFamily: 'monospace' }} tickLine={false}
                    label={{ value: 'Tyre Life (laps)', position: 'insideBottom', offset: -12, fontSize: 9, fill: '#6e7681' }} />
                  <YAxis tick={{ fontSize: 8, fill: '#6e7681', fontFamily: 'monospace' }} tickLine={false} axisLine={false} width={36}
                    label={{ value: 'Lap Time (s)', angle: -90, position: 'insideLeft', offset: 12, fontSize: 9, fill: '#6e7681' }}
                    domain={['auto', 'auto']} />
                  <Tooltip formatter={(v, name) => [`${v}s`, name]}
                    contentStyle={{ background: 'rgba(22,27,34,0.97)', border: '1px solid rgba(48,54,61,0.9)', borderRadius: 4, fontSize: 10 }} />
                  <Legend wrapperStyle={{ fontSize: 10 }} />
                  {Object.keys(data).map(c => (
                    <Line key={c} type="monotone" dataKey={c} stroke={COMPOUND_COLORS[c]}
                      strokeWidth={2} dot={false} name={c} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="grid-2">
            {/* Bar comparison */}
            <div className="card">
              <div className="card-header"><span className="card-title">Lap Time Comparison by Stint Age</span></div>
              <div className="card-body">
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={barData} margin={{ top: 4, right: 8, bottom: 16, left: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(48,54,61,0.45)" vertical={false} />
                    <XAxis dataKey="life" tick={{ fontSize: 9, fill: '#6e7681' }} tickLine={false} />
                    <YAxis tick={{ fontSize: 8, fill: '#6e7681', fontFamily: 'monospace' }} tickLine={false} axisLine={false} width={36} domain={['auto', 'auto']} />
                    <Tooltip formatter={(v, name) => [`${v}s`, name]}
                      contentStyle={{ background: 'rgba(22,27,34,0.97)', border: '1px solid rgba(48,54,61,0.9)', borderRadius: 4, fontSize: 10 }} />
                    <Legend wrapperStyle={{ fontSize: 9 }} />
                    {Object.keys(data).map(c => (
                      <Bar key={c} dataKey={c} fill={COMPOUND_COLORS[c]} opacity={0.8} radius={[2, 2, 0, 0]} />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Stats */}
            <div className="card">
              <div className="card-header"><span className="card-title">Compound Statistics</span></div>
              <div className="card-body">
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr>
                      {['Compound', 'Best Lap', 'Degradation', 'Optimal Lap', 'Model'].map(h => (
                        <th key={h} style={{ fontSize: 9, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', padding: '4px 6px', textAlign: 'left', borderBottom: '1px solid var(--border)' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {stats.map(s => (
                      <tr key={s.compound}>
                        <td style={{ padding: '6px 6px', borderBottom: '1px solid rgba(48,54,61,0.3)' }}>
                          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <CompoundBadge compound={s.compound} size={18} />
                            <span style={{ fontSize: 11, fontWeight: 600, color: COMPOUND_COLORS[s.compound] }}>{s.compound}</span>
                          </span>
                        </td>
                        <td style={{ padding: '6px 6px', fontSize: 11, fontFamily: 'monospace', color: 'var(--text-primary)', borderBottom: '1px solid rgba(48,54,61,0.3)' }}>{(s.minTime / 1000).toFixed(3)}s</td>
                        <td style={{ padding: '6px 6px', fontSize: 11, fontFamily: 'monospace', color: '#f87171', borderBottom: '1px solid rgba(48,54,61,0.3)' }}>+{(s.degradation / 1000).toFixed(3)}s</td>
                        <td style={{ padding: '6px 6px', fontSize: 11, fontFamily: 'monospace', color: 'var(--text-secondary)', borderBottom: '1px solid rgba(48,54,61,0.3)' }}>Lap {s.optimalLap}</td>
                        <td style={{ padding: '6px 6px', fontSize: 9, color: 'var(--text-muted)', borderBottom: '1px solid rgba(48,54,61,0.3)' }}>{s.modelType}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
