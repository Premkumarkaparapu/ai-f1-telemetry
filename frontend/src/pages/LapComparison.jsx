import { useState, useEffect, useMemo } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, AreaChart, Area,
} from 'recharts';
import { api } from '../api.js';
import { msToLapTime, msToDelta, CompoundBadge, compoundColor } from '../utils.jsx';

const COLORS = { 1: '#60a5fa', 2: '#f87171' };

export default function LapComparison() {
  const [drivers, setDrivers] = useState([]);
  const [d1Id, setD1Id] = useState(''); const [d2Id, setD2Id] = useState('');
  const [laps1, setLaps1] = useState([]); const [laps2, setLaps2] = useState([]);
  const [lap1Id, setLap1Id] = useState(''); const [lap2Id, setLap2Id] = useState('');
  const [tel1, setTel1] = useState([]); const [tel2, setTel2] = useState([]);
  const [tab, setTab] = useState('speed');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.getDrivers(1).then(d => {
      setDrivers(d);
      if (d.length > 0) setD1Id(String(d[0].driver_id));
      if (d.length > 1) setD2Id(String(d[1].driver_id));
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!d1Id) return;
    api.getLaps(d1Id).then(l => {
      const valid = l.filter(x => x.is_valid && x.lap_time_ms).sort((a,b) => a.lap_number - b.lap_number);
      setLaps1(valid);
      if (valid.length) {
        const fastest = valid.reduce((a,b) => a.lap_time_ms < b.lap_time_ms ? a : b);
        setLap1Id(String(fastest.lap_id));
      }
    }).catch(() => {});
  }, [d1Id]);

  useEffect(() => {
    if (!d2Id) return;
    api.getLaps(d2Id).then(l => {
      const valid = l.filter(x => x.is_valid && x.lap_time_ms).sort((a,b) => a.lap_number - b.lap_number);
      setLaps2(valid);
      if (valid.length) {
        const fastest = valid.reduce((a,b) => a.lap_time_ms < b.lap_time_ms ? a : b);
        setLap2Id(String(fastest.lap_id));
      }
    }).catch(() => {});
  }, [d2Id]);

  useEffect(() => {
    if (!lap1Id) { setTel1([]); return; }
    api.getTelemetry(lap1Id).then(setTel1).catch(() => setTel1([]));
  }, [lap1Id]);

  useEffect(() => {
    if (!lap2Id) { setTel2([]); return; }
    api.getTelemetry(lap2Id).then(setTel2).catch(() => setTel2([]));
  }, [lap2Id]);

  const lap1 = useMemo(() => laps1.find(l => String(l.lap_id) === lap1Id), [laps1, lap1Id]);
  const lap2 = useMemo(() => laps2.find(l => String(l.lap_id) === lap2Id), [laps2, lap2Id]);
  const drv1 = useMemo(() => drivers.find(d => String(d.driver_id) === d1Id), [drivers, d1Id]);
  const drv2 = useMemo(() => drivers.find(d => String(d.driver_id) === d2Id), [drivers, d2Id]);

  const chartData = useMemo(() => {
    if (!tel1.length) return [];
    const step = Math.max(1, Math.floor(tel1.length / 300));
    return tel1.filter((_, i) => i % step === 0).map((p, i) => {
      const p2 = tel2[i * step];
      return {
        dist: Math.round(p.distance ?? 0),
        speed1: +(p.speed ?? 0).toFixed(1),
        throttle1: +(p.throttle ?? 0).toFixed(1),
        brake1: +((p.brake ?? 0) * 100).toFixed(1),
        gear1: p.gear ?? 0,
        speed2: p2 ? +(p2.speed ?? 0).toFixed(1) : null,
        throttle2: p2 ? +(p2.throttle ?? 0).toFixed(1) : null,
        brake2: p2 ? +((p2.brake ?? 0) * 100).toFixed(1) : null,
        gear2: p2 ? (p2.gear ?? 0) : null,
        delta: p2 ? +((p.speed ?? 0) - (p2.speed ?? 0)).toFixed(1) : null,
      };
    });
  }, [tel1, tel2]);

  const c1 = drv1?.code || 'DRV1';
  const c2 = drv2?.code || 'DRV2';

  return (
    <div className="content-area">
      <div className="page-header">
        <div>
          <div className="page-title">⚡ Lap Comparison</div>
          <div className="page-desc">Overlay telemetry traces for any two drivers side-by-side</div>
        </div>
      </div>

      {/* Driver / Lap selectors */}
      <div className="grid-2" style={{ marginBottom: 10 }}>
        {[
          { label: 'Driver 1', color: '#60a5fa', dId: d1Id, setDId: setD1Id, lapId: lap1Id, setLapId: setLap1Id, laps: laps1 },
          { label: 'Driver 2', color: '#f87171', dId: d2Id, setDId: setD2Id, lapId: lap2Id, setLapId: setLap2Id, laps: laps2 },
        ].map(({ label, color, dId, setDId, lapId, setLapId, laps }) => (
          <div key={label} className="card">
            <div className="card-header">
              <span className="card-title" style={{ color }}>{label}</span>
            </div>
            <div className="card-body" style={{ display: 'flex', gap: 10 }}>
              <select className="filter-select" style={{ flex: 1 }} value={dId} onChange={e => setDId(e.target.value)}>
                {drivers.map(d => <option key={d.driver_id} value={d.driver_id}>{d.code} — {d.team}</option>)}
              </select>
              <select className="filter-select" style={{ flex: 1 }} value={lapId} onChange={e => setLapId(e.target.value)}>
                {laps.map(l => <option key={l.lap_id} value={l.lap_id}>Lap {l.lap_number} — {msToLapTime(l.lap_time_ms)}</option>)}
              </select>
            </div>
          </div>
        ))}
      </div>

      {/* Lap info cards */}
      {(lap1 || lap2) && (
        <div className="grid-2" style={{ marginBottom: 10 }}>
          {[{ lap: lap1, color: '#60a5fa', code: c1 }, { lap: lap2, color: '#f87171', code: c2 }].map(({ lap, color, code }) => (
            <div key={code} className="card">
              <div className="card-header">
                <span className="card-title" style={{ color }}>{code}</span>
                <span style={{ fontFamily: 'monospace', fontSize: 14, fontWeight: 700, color }}>{msToLapTime(lap?.lap_time_ms)}</span>
              </div>
              {lap && (
                <div className="card-body">
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, textAlign: 'center' }}>
                    {[['Sector 1', lap.sector1_ms], ['Sector 2', lap.sector2_ms], ['Sector 3', lap.sector3_ms]].map(([k, v]) => (
                      <div key={k}>
                        <div style={{ fontSize: 9, color: 'var(--text-muted)', textTransform: 'uppercase' }}>{k}</div>
                        <div style={{ fontSize: 13, fontFamily: 'monospace', fontWeight: 600, color }}>{msToLapTime(v)}</div>
                      </div>
                    ))}
                  </div>
                  <div style={{ display: 'flex', gap: 10, marginTop: 10, alignItems: 'center' }}>
                    <CompoundBadge compound={lap.compound} size={20} />
                    <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{lap.compound} · {lap.tyre_life} laps old</span>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Tab chart */}
      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', gap: 4 }}>
            {[['speed', 'Speed Trace'], ['throttle', 'Throttle & Brake'], ['gear', 'Gear Map']].map(([id, label]) => (
              <button key={id} onClick={() => setTab(id)}
                style={{ padding: '4px 12px', borderRadius: 4, border: 'none', cursor: 'pointer', fontSize: 11, fontWeight: 600,
                  background: tab === id ? 'var(--f1-red)' : 'var(--bg-secondary)', color: tab === id ? 'white' : 'var(--text-secondary)' }}>
                {label}
              </button>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 12 }}>
            {[[c1, '#60a5fa'], [c2, '#f87171']].map(([code, color]) => (
              <span key={code} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <div style={{ width: 12, height: 2, background: color }} />
                <span style={{ fontSize: 9, color }}>{code}</span>
              </span>
            ))}
          </div>
        </div>
        <div className="card-body">
          {!chartData.length
            ? <div className="empty-state">Select two drivers and laps to compare telemetry</div>
            : (
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={chartData} margin={{ top: 4, right: 12, bottom: 16, left: 2 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(48,54,61,0.45)" vertical={false} />
                  <XAxis dataKey="dist" tick={{ fontSize: 8, fill: '#6e7681', fontFamily: 'monospace' }} tickLine={false}
                    label={{ value: 'Distance (m)', position: 'insideBottom', offset: -10, fontSize: 8, fill: '#6e7681' }} />
                  <YAxis tick={{ fontSize: 8, fill: '#6e7681', fontFamily: 'monospace' }} tickLine={false} axisLine={false} width={30} />
                  <Tooltip contentStyle={{ background: 'rgba(22,27,34,0.97)', border: '1px solid rgba(48,54,61,0.9)', borderRadius: 4, fontSize: 10 }} />
                  <Legend wrapperStyle={{ fontSize: 9 }} />
                  {tab === 'speed' && <>
                    <Line type="monotone" dataKey="speed1" stroke="#60a5fa" strokeWidth={1.5} dot={false} name={`${c1} Speed`} />
                    <Line type="monotone" dataKey="speed2" stroke="#f87171" strokeWidth={1.5} dot={false} name={`${c2} Speed`} />
                  </>}
                  {tab === 'throttle' && <>
                    <Line type="monotone" dataKey="throttle1" stroke="#60a5fa" strokeWidth={1.5} dot={false} name={`${c1} Throttle`} />
                    <Line type="monotone" dataKey="throttle2" stroke="#f87171" strokeWidth={1.5} dot={false} name={`${c2} Throttle`} />
                    <Line type="monotone" dataKey="brake1" stroke="#60a5fa" strokeWidth={1} strokeDasharray="4 2" dot={false} name={`${c1} Brake`} />
                    <Line type="monotone" dataKey="brake2" stroke="#f87171" strokeWidth={1} strokeDasharray="4 2" dot={false} name={`${c2} Brake`} />
                  </>}
                  {tab === 'gear' && <>
                    <Line type="stepAfter" dataKey="gear1" stroke="#60a5fa" strokeWidth={1.5} dot={false} name={`${c1} Gear`} />
                    <Line type="stepAfter" dataKey="gear2" stroke="#f87171" strokeWidth={1.5} dot={false} name={`${c2} Gear`} />
                  </>}
                </LineChart>
              </ResponsiveContainer>
            )}
        </div>
      </div>

      {/* Delta area */}
      {chartData.length > 0 && (
        <div className="card" style={{ marginTop: 10 }}>
          <div className="card-header">
            <span className="card-title">Speed Delta — {c1} vs {c2}</span>
            <span style={{ fontSize: 9, color: 'var(--text-muted)' }}>positive = {c1} faster</span>
          </div>
          <div className="card-body">
            <ResponsiveContainer width="100%" height={100}>
              <AreaChart data={chartData} margin={{ top: 4, right: 12, bottom: 16, left: 2 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(48,54,61,0.45)" vertical={false} />
                <XAxis dataKey="dist" tick={{ fontSize: 8, fill: '#6e7681', fontFamily: 'monospace' }} tickLine={false}
                  label={{ value: 'Distance (m)', position: 'insideBottom', offset: -10, fontSize: 8, fill: '#6e7681' }} />
                <YAxis tick={{ fontSize: 8, fill: '#6e7681', fontFamily: 'monospace' }} tickLine={false} axisLine={false} width={30} />
                <Tooltip contentStyle={{ background: 'rgba(22,27,34,0.97)', border: '1px solid rgba(48,54,61,0.9)', borderRadius: 4, fontSize: 10 }} />
                <Area type="monotone" dataKey="delta" stroke="#34d399" fill="rgba(52,211,153,0.15)" name="Δ Speed (km/h)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
