import { useState, useEffect, useMemo } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Legend, ComposedChart, Area,
} from 'recharts';
import { api } from '../api.js';
import { msToLapTime, CompoundBadge, teamColor, speedToColor } from '../utils.jsx';

// ── Helpers ───────────────────────────────────────────────────────────────────
function msDelta(d) {
  if (d == null) return '—';
  const s = (d / 1000).toFixed(3);
  return d >= 0 ? `+${s}` : s;
}

// ── Track Map ─────────────────────────────────────────────────────────────────
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
    const W = 270, H = 190, PAD = 14;
    const sx = v => PAD + ((v - minX) / (maxX - minX || 1)) * (W - PAD * 2);
    const sy = v => H - PAD - ((v - minY) / (maxY - minY || 1)) * (H - PAD * 2);
    const step = Math.max(1, Math.floor(pts.length / 600));
    return pts.filter((_, i) => i % step === 0).slice(0, -1).map((p, i) => {
      const next = pts[Math.min((i + 1) * step, pts.length - 1)];
      return { x1: sx(p.x), y1: sy(p.y), x2: sx(next.x), y2: sy(next.y), color: speedToColor(p.speed, minS, maxS) };
    });
  }, [telemetry]);

  if (!segments.length) return (
    <div className="empty-state" style={{ height: 210 }}>
      <span>Loading track map…</span>
    </div>
  );

  return (
    <div style={{ position: 'relative', padding: '8px 40px 8px 8px', display: 'flex', justifyContent: 'center' }}>
      <svg width={270} height={190} style={{ overflow: 'visible' }}>
        {segments.map((s, i) => (
          <line key={i} x1={s.x1} y1={s.y1} x2={s.x2} y2={s.y2}
            stroke={s.color} strokeWidth="2.8" strokeLinecap="round" />
        ))}
      </svg>
      <div style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', display: 'flex', gap: 4, alignItems: 'stretch' }}>
        <div style={{ width: 8, height: 110, borderRadius: 4, background: 'linear-gradient(to bottom,#ff0000,#ff8c00,#ffff00,#00ff80,#00bfff,#0000ff)' }} />
        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', height: 110 }}>
          {['320', '240', '160', '80', '0'].map(v => (
            <span key={v} style={{ fontSize: 8, color: '#7a90a8', fontFamily: 'monospace' }}>{v}</span>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Speed / Throttle / Brake ──────────────────────────────────────────────────
function SpeedThrottleChart({ telemetry }) {
  const data = useMemo(() => {
    if (!telemetry?.length) return [];
    const step = Math.max(1, Math.floor(telemetry.length / 300));
    return telemetry.filter((_, i) => i % step === 0).map(p => ({
      dist: Math.round(p.distance ?? 0),
      speed: +(p.speed ?? 0).toFixed(1),
      throttle: +(p.throttle ?? 0).toFixed(1),
      brake: +((p.brake ?? 0) * 100).toFixed(1),
      drs: (p.drs ?? 0) > 8 ? 100 : 0,
    }));
  }, [telemetry]);

  if (!data.length) return <div className="empty-state" style={{ height: 165 }}>Loading telemetry…</div>;

  return (
    <ResponsiveContainer width="100%" height={165}>
      <ComposedChart data={data} margin={{ top: 4, right: 36, bottom: 16, left: 2 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,120,155,0.2)" vertical={false} />
        <XAxis dataKey="dist" tick={{ fontSize: 8, fill: '#7a90a8', fontFamily: 'monospace' }}
          tickLine={false} axisLine={{ stroke: 'rgba(99,120,155,0.3)' }}
          label={{ value: 'Distance (m)', position: 'insideBottom', offset: -6, fontSize: 8, fill: '#7a90a8' }} />
        <YAxis yAxisId="spd" domain={[0, 360]} tick={{ fontSize: 8, fill: '#7a90a8', fontFamily: 'monospace' }}
          tickLine={false} axisLine={false} width={26} />
        <YAxis yAxisId="pct" orientation="right" domain={[0, 100]}
          tick={{ fontSize: 8, fill: '#7a90a8', fontFamily: 'monospace' }}
          tickLine={false} axisLine={false} width={20} />
        <Tooltip contentStyle={{ background: 'rgba(26,34,54,0.97)', border: '1px solid rgba(99,120,155,0.5)', borderRadius: 4, fontSize: 10 }} />
        <Area yAxisId="pct" type="step" dataKey="drs" fill="rgba(208,154,255,0.18)"
          stroke="rgba(208,154,255,0.5)" strokeWidth={0.8} dot={false} name="DRS" />
        <Line yAxisId="spd" type="monotone" dataKey="speed" stroke="#70b8ff" strokeWidth={1.5} dot={false} name="Speed (km/h)" />
        <Line yAxisId="pct" type="monotone" dataKey="throttle" stroke="#3dffa0" strokeWidth={1.2} dot={false} name="Throttle (%)" />
        <Line yAxisId="pct" type="monotone" dataKey="brake" stroke="#ff6b6b" strokeWidth={1.2} dot={false} name="Brake (%)" />
        <Legend wrapperStyle={{ fontSize: 9, paddingTop: 2 }} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

// ── Lap Time Evolution ────────────────────────────────────────────────────────
function LapTimeEvolution({ laps, driverCode, pitLaps }) {
  const data = useMemo(() =>
    laps.filter(l => l.lap_time_ms && l.is_valid).map(l => ({
      lap: l.lap_number,
      time: +(l.lap_time_ms / 1000).toFixed(3),
    })), [laps]);

  if (!data.length) return <div className="empty-state" style={{ height: 135 }}>No lap data</div>;
  const domain = [Math.floor(Math.min(...data.map(d => d.time)) - 1), Math.ceil(Math.max(...data.map(d => d.time)) + 1)];

  return (
    <ResponsiveContainer width="100%" height={135}>
      <LineChart data={data} margin={{ top: 4, right: 12, bottom: 18, left: 2 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,120,155,0.2)" vertical={false} />
        <XAxis dataKey="lap" tick={{ fontSize: 8, fill: '#7a90a8', fontFamily: 'monospace' }}
          tickLine={false} axisLine={{ stroke: 'rgba(99,120,155,0.3)' }}
          label={{ value: 'Lap Number', position: 'insideBottom', offset: -10, fontSize: 8, fill: '#7a90a8' }} />
        <YAxis domain={domain} tick={{ fontSize: 8, fill: '#7a90a8', fontFamily: 'monospace' }}
          tickLine={false} axisLine={false} width={28} />
        <Tooltip formatter={v => [`${v}s`, driverCode]} labelFormatter={l => `Lap ${l}`}
          contentStyle={{ background: 'rgba(26,34,54,0.97)', border: '1px solid rgba(99,120,155,0.5)', borderRadius: 4, fontSize: 10 }}
          labelStyle={{ color: '#a8b8cc' }} itemStyle={{ color: '#70b8ff' }} />
        {(pitLaps || []).map(pl => (
          <ReferenceLine key={pl} x={pl} stroke="rgba(168,184,204,0.35)" strokeDasharray="3 3"
            label={{ value: 'Pit', position: 'top', fontSize: 7, fill: '#a8b8cc' }} />
        ))}
        <Line type="monotone" dataKey="time" stroke="#70b8ff" strokeWidth={1.5}
          dot={{ r: 1.5, fill: '#70b8ff' }} activeDot={{ r: 3 }} name={driverCode} />
      </LineChart>
    </ResponsiveContainer>
  );
}

// ── Speed Comparison ──────────────────────────────────────────────────────────
function SpeedComparison({ tel1, tel2, code1, code2 }) {
  const data = useMemo(() => {
    if (!tel1?.length) return [];
    const step = Math.max(1, Math.floor(tel1.length / 250));
    return tel1.filter((_, i) => i % step === 0).map((p, i) => {
      const p2 = tel2?.[i * step];
      return {
        dist: Math.round(p.distance ?? 0),
        [code1]: +(p.speed ?? 0).toFixed(1),
        ...(p2 ? { [code2]: +(p2.speed ?? 0).toFixed(1) } : {}),
      };
    });
  }, [tel1, tel2, code1, code2]);

  if (!data.length) return <div className="empty-state" style={{ height: 135 }}>Select a driver to compare</div>;

  const ts1 = tel1 ? Math.round(Math.max(...tel1.map(p => p.speed ?? 0))) : 0;
  const ts2 = tel2 ? Math.round(Math.max(...tel2.map(p => p.speed ?? 0))) : 0;

  return (
    <div style={{ display: 'flex', gap: 8 }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <ResponsiveContainer width="100%" height={135}>
          <LineChart data={data} margin={{ top: 4, right: 8, bottom: 18, left: 2 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,120,155,0.2)" vertical={false} />
            <XAxis dataKey="dist" tick={{ fontSize: 8, fill: '#7a90a8', fontFamily: 'monospace' }}
              tickLine={false} axisLine={{ stroke: 'rgba(99,120,155,0.3)' }}
              label={{ value: 'Distance (m)', position: 'insideBottom', offset: -10, fontSize: 8, fill: '#7a90a8' }} />
            <YAxis domain={[0, 360]} tick={{ fontSize: 8, fill: '#7a90a8', fontFamily: 'monospace' }}
              tickLine={false} axisLine={false} width={26} />
            <Tooltip contentStyle={{ background: 'rgba(26,34,54,0.97)', border: '1px solid rgba(99,120,155,0.5)', borderRadius: 4, fontSize: 10 }} />
            <Line type="monotone" dataKey={code1} stroke="#70b8ff" strokeWidth={1.5} dot={false} />
            {tel2 && <Line type="monotone" dataKey={code2} stroke="#ff6b6b" strokeWidth={1.5} dot={false} />}
            <Legend wrapperStyle={{ fontSize: 9 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 10, minWidth: 85 }}>
        <div style={{ fontSize: 9, color: '#7a90a8', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Top Speed</div>
        <div style={{ display: 'flex', gap: 10 }}>
          <div>
            <div style={{ fontSize: 9, color: '#70b8ff', fontWeight: 700 }}>{code1}</div>
            <div style={{ fontSize: 18, fontWeight: 800, color: '#70b8ff', fontFamily: 'monospace' }}>{ts1}</div>
            <div style={{ fontSize: 8, color: '#7a90a8' }}>km/h</div>
          </div>
          {tel2 && (
            <div>
              <div style={{ fontSize: 9, color: '#ff6b6b', fontWeight: 700 }}>{code2}</div>
              <div style={{ fontSize: 18, fontWeight: 800, color: '#ff6b6b', fontFamily: 'monospace' }}>{ts2}</div>
              <div style={{ fontSize: 8, color: '#7a90a8' }}>km/h</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Section Header (matches reference image 1 style) ─────────────────────────
function PanelHeader({ title, right }) {
  return (
    <div style={{
      padding: '8px 14px', borderBottom: '1px solid rgba(99,120,155,0.25)',
      background: 'rgba(112,184,255,0.06)',
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    }}>
      <span style={{
        fontSize: 10, fontWeight: 800, letterSpacing: '0.09em',
        textTransform: 'uppercase', color: 'var(--text-secondary)',
      }}>{title}</span>
      {right && <span>{right}</span>}
    </div>
  );
}

// ── Info Row (label + value in a clean line) ──────────────────────────────────
function InfoRow({ label, value, color, children }) {
  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      padding: '6px 14px', borderBottom: '1px solid rgba(99,120,155,0.1)',
    }}>
      <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{label}</span>
      {children ?? (
        <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', fontWeight: 700, color: color || 'var(--text-primary)' }}>
          {value ?? '—'}
        </span>
      )}
    </div>
  );
}

// ── Main Dashboard ────────────────────────────────────────────────────────────
export default function Dashboard() {
  // ── Cascade state ─────────────────────────────────────────────────────────
  const [years,           setYears]           = useState([]);
  const [selectedYear,    setSelectedYear]    = useState('');
  const [events,          setEvents]          = useState([]);      // [{event_name, sessions:[]}]
  const [selectedEvent,   setSelectedEvent]   = useState('');      // event_name
  const [sessionOptions,  setSessionOptions]  = useState([]);      // [{session_id, session_type, label}]
  const [selectedSessionId, setSelectedSessionId] = useState('');

  // ── Session data ──────────────────────────────────────────────────────────
  const [session,         setSession]         = useState(null);
  const [drivers,         setDrivers]         = useState([]);
  const [selectedDriverId,setSelectedDriverId]= useState('');
  const [laps,            setLaps]            = useState([]);
  const [selectedLapId,   setSelectedLapId]   = useState('');
  const [telemetry,       setTelemetry]       = useState([]);
  const [standings,       setStandings]       = useState([]);
  const [weather,         setWeather]         = useState([]);
  const [stints,          setStints]          = useState([]);
  const [pitStops,        setPitStops]        = useState([]);
  const [compareDriverId, setCompareDriverId] = useState('');
  const [compareTelemetry,setCompareTelemetry]= useState([]);
  const [loadingSession,  setLoadingSession]  = useState(false);
  const [loadingTel,      setLoadingTel]      = useState(false);

  // ── Step 1: Load available years ──────────────────────────────────────────
  useEffect(() => {
    api.getYears().then(data => {
      const yrs = data.years || [];
      setYears(yrs);
      if (yrs.length) setSelectedYear(String(yrs[0])); // default: most recent year
    }).catch(console.error);
  }, []);

  // ── Step 2: Load events for chosen year ───────────────────────────────────
  useEffect(() => {
    if (!selectedYear) return;
    setEvents([]); setSelectedEvent(''); setSessionOptions([]); setSelectedSessionId('');
    api.getByYear(Number(selectedYear)).then(data => {
      const evs = data.events || [];
      setEvents(evs);
      if (evs.length) setSelectedEvent(evs[0].event_name);
    }).catch(console.error);
  }, [selectedYear]);

  // ── Step 3: Load session options for chosen event ─────────────────────────
  useEffect(() => {
    if (!selectedEvent || !events.length) return;
    const ev = events.find(e => e.event_name === selectedEvent);
    const opts = ev ? ev.sessions : [];
    setSessionOptions(opts);
    // Default: prefer Race, else first option
    const race = opts.find(o => o.session_type === 'R') || opts[0];
    setSelectedSessionId(race ? String(race.session_id) : '');
  }, [selectedEvent, events]);

  useEffect(() => {
    if (!selectedSessionId) return;
    setLoadingSession(true);
    setDrivers([]); setLaps([]); setStandings([]); setWeather([]);
    setSelectedDriverId(''); setSelectedLapId(''); setTelemetry([]);

    Promise.allSettled([
      api.getSession(selectedSessionId),
      api.getDrivers(selectedSessionId),
      api.getStandings(selectedSessionId),
      api.getWeather(selectedSessionId),
    ]).then(([sessR, drvsR, standR, wxR]) => {
      const sess  = sessR.status  === 'fulfilled' ? sessR.value  : null;
      const drvs  = drvsR.status  === 'fulfilled' ? drvsR.value  : [];
      const stand = standR.status === 'fulfilled' ? standR.value : [];
      const wx    = wxR.status    === 'fulfilled' ? wxR.value    : [];
      setSession(sess); setDrivers(drvs); setStandings(stand); setWeather(wx);
      if (stand.length && drvs.length) {
        const p1 = stand[0];
        const match = drvs.find(d => d.driver_id === p1.driver_id);
        setSelectedDriverId(String(match ? match.driver_id : drvs[0].driver_id));
      } else if (drvs.length) {
        setSelectedDriverId(String(drvs[0].driver_id));
      }
    }).finally(() => setLoadingSession(false));
  }, [selectedSessionId]);

  useEffect(() => {
    if (!selectedDriverId || !selectedSessionId) return;
    setLaps([]); setStints([]); setPitStops([]); setSelectedLapId(''); setTelemetry([]);
    Promise.allSettled([
      api.getLaps(selectedDriverId),
      api.getStints(selectedDriverId, selectedSessionId),
      api.getPitStops(selectedDriverId, selectedSessionId),
    ]).then(([lapsR, stintsR, pitsR]) => {
      const lapData   = lapsR.status   === 'fulfilled' ? lapsR.value   : [];
      const stintData = stintsR.status === 'fulfilled' ? stintsR.value : [];
      const pitData   = pitsR.status   === 'fulfilled' ? pitsR.value   : [];
      setLaps(lapData);
      setStints(Array.isArray(stintData) ? stintData : []);
      setPitStops(Array.isArray(pitData) ? pitData : []);
      const valid = lapData.filter(l => l.is_valid && l.lap_time_ms);
      if (valid.length) {
        const fastest = valid.reduce((a, b) => a.lap_time_ms < b.lap_time_ms ? a : b);
        setSelectedLapId(String(fastest.lap_id));
      }
    });
  }, [selectedDriverId, selectedSessionId]);

  useEffect(() => {
    if (!selectedLapId) { setTelemetry([]); return; }
    setLoadingTel(true);
    const lap = laps.find(l => String(l.lap_id) === selectedLapId);
    const drv = drivers.find(d => String(d.driver_id) === selectedDriverId);
    api.getTelemetry(
      selectedLapId,
      selectedSessionId,
      drv?.code,
      lap?.lap_number
    ).then(setTelemetry).catch(() => setTelemetry([])).finally(() => setLoadingTel(false));
  }, [selectedLapId]);

  useEffect(() => {
    if (!compareDriverId) { setCompareTelemetry([]); return; }
    api.getLaps(compareDriverId).then(lapData => {
      const valid = lapData.filter(l => l.is_valid && l.lap_time_ms);
      if (valid.length) {
        const fastest = valid.reduce((a, b) => a.lap_time_ms < b.lap_time_ms ? a : b);
        const cmpDrv = drivers.find(d => String(d.driver_id) === compareDriverId);
        api.getTelemetry(
          fastest.lap_id,
          selectedSessionId,
          cmpDrv?.code,
          fastest.lap_number
        ).then(setCompareTelemetry).catch(() => {});
      }
    }).catch(() => {});
  }, [compareDriverId]);

  // ── Derived ──────────────────────────────────────────────────────────────────
  const selectedLap    = useMemo(() => laps.find(l => String(l.lap_id) === selectedLapId), [laps, selectedLapId]);
  const selectedDriver = useMemo(() => drivers.find(d => String(d.driver_id) === selectedDriverId), [drivers, selectedDriverId]);
  const compareDriver  = useMemo(() => drivers.find(d => String(d.driver_id) === compareDriverId), [drivers, compareDriverId]);
  const driverStanding = useMemo(() => standings.find(s => String(s.driver_id) === selectedDriverId), [standings, selectedDriverId]);

  const bestLap = useMemo(() => {
    const valid = laps.filter(l => l.is_valid && l.lap_time_ms);
    return valid.length ? valid.reduce((a, b) => a.lap_time_ms < b.lap_time_ms ? a : b) : null;
  }, [laps]);

  const telSummary = useMemo(() => {
    if (!telemetry?.length) return null;
    const speeds = telemetry.map(p => p.speed ?? 0).filter(Boolean);
    const drsCount = telemetry.filter(p => (p.drs ?? 0) > 8).length;
    return {
      topSpeed: speeds.length ? Math.max(...speeds) : 0,
      avgSpeed: speeds.length ? speeds.reduce((a, b) => a + b, 0) / speeds.length : 0,
      drsUsage: telemetry.length ? (drsCount / telemetry.length * 100) : 0,
    };
  }, [telemetry]);

  const hasTelemetry = telemetry?.length > 0;

  const pitLapNumbers = useMemo(() => pitStops.map(p => p.lap_number), [pitStops]);
  const latestWeather = useMemo(() => weather.length ? weather[Math.floor(weather.length / 2)] : null, [weather]);

  const sessionBestSectors = useMemo(() => {
    const valid = laps.filter(l => l.is_valid);
    const min = arr => arr.length ? arr.reduce((a, b) => Math.min(a, b), Infinity) : null;
    return {
      s1: min(valid.filter(l => l.sector1_ms).map(l => l.sector1_ms)),
      s2: min(valid.filter(l => l.sector2_ms).map(l => l.sector2_ms)),
      s3: min(valid.filter(l => l.sector3_ms).map(l => l.sector3_ms)),
    };
  }, [laps]);

  const validLaps = useMemo(() => laps.filter(l => l.is_valid && l.lap_time_ms).sort((a, b) => a.lap_number - b.lap_number), [laps]);

  // ── Derived stints (fallback if API stints empty) ─────────────────────────
  const derivedStints = useMemo(() => {
    if (stints.length) return stints;
    return [...new Set(laps.map(l => l.stint_number))].filter(Boolean).map(sn => {
      const sLaps = laps.filter(l => l.stint_number === sn);
      const validS = sLaps.filter(l => l.lap_time_ms);
      const bestT = validS.length ? Math.min(...validS.map(l => l.lap_time_ms)) : null;
      return {
        stint_number: sn,
        compound: sLaps[0]?.compound ?? '—',
        start_lap: Math.min(...sLaps.map(l => l.lap_number)),
        end_lap: Math.max(...sLaps.map(l => l.lap_number)),
        best_lap_time_ms: bestT,
      };
    });
  }, [stints, laps]);

  return (
    <>
      {/* ── Filter Bar ── */}
      <div className="filter-bar">

        {/* Season (Year) */}
        <div className="filter-group">
          <span className="filter-label">Season</span>
          <select className="filter-select" value={selectedYear}
            onChange={e => setSelectedYear(e.target.value)}
            style={{ colorScheme: 'dark' }}>
            {years.map(y => <option key={y} value={y} style={{ background: '#0d1520' }}>{y}</option>)}
          </select>
        </div>
        <div className="filter-divider" />

        {/* Event (Grand Prix) */}
        <div className="filter-group">
          <span className="filter-label">Event</span>
          <select className="filter-select" value={selectedEvent}
            onChange={e => setSelectedEvent(e.target.value)}
            style={{ colorScheme: 'dark' }}>
            {events.map(ev => (
              <option key={ev.event_name} value={ev.event_name}
                style={{ background: '#0d1520' }}>{ev.event_name}</option>
            ))}
          </select>
        </div>
        <div className="filter-divider" />

        {/* Session Type */}
        <div className="filter-group">
          <span className="filter-label">Session</span>
          <select className="filter-select" value={selectedSessionId}
            onChange={e => setSelectedSessionId(e.target.value)}
            style={{ colorScheme: 'dark' }}>
            {sessionOptions.map(opt => (
              <option key={opt.session_id} value={String(opt.session_id)}
                style={{ background: '#0d1520' }}>{opt.label}</option>
            ))}
          </select>
        </div>
        <div className="filter-divider" />

        {/* Driver */}
        <div className="filter-group">
          <span className="filter-label">Driver</span>
          <select className="filter-select" value={selectedDriverId}
            onChange={e => setSelectedDriverId(e.target.value)}
            style={{ colorScheme: 'dark' }}>
            {drivers.map(d => (
              <option key={d.driver_id} value={d.driver_id}
                style={{ background: '#0d1520' }}>
                {d.code} — {d.full_name !== d.code ? d.full_name : d.team}
              </option>
            ))}
          </select>
        </div>
        <div className="filter-divider" />

        {/* Lap */}
        <div className="filter-group">
          <span className="filter-label">Lap</span>
          <select className="filter-select" value={selectedLapId}
            onChange={e => setSelectedLapId(e.target.value)}
            style={{ colorScheme: 'dark' }}>
            {validLaps.map(l => (
              <option key={l.lap_id} value={l.lap_id}
                style={{ background: '#0d1520' }}>
                Lap {l.lap_number} — {msToLapTime(l.lap_time_ms)}
              </option>
            ))}
          </select>
        </div>
        <div className="filter-spacer" />
        <div className="filter-group">
          <span className="filter-label">vs</span>
          <select className="filter-select" value={compareDriverId} onChange={e => setCompareDriverId(e.target.value)}>
            <option value="">— None —</option>
            {drivers.filter(d => String(d.driver_id) !== selectedDriverId)
              .map(d => <option key={d.driver_id} value={d.driver_id}>{d.code}</option>)}
          </select>
        </div>
        <button className="btn-compare">⚡ Compare Laps</button>
      </div>

      {/* ── Content ── */}
      <div className="content-area">
        {loadingSession && (
          <div className="loading-state"><div className="spinner" /><span>Loading session data…</span></div>
        )}

        {!loadingSession && (<>

          {/* ── KPI Row ── */}
          <div className="kpi-row">
            {[
              { label: 'POSITION',    value: driverStanding?.position ?? '—', icon: '🏆', className: '' },
              { label: 'BEST LAP',    value: msToLapTime(bestLap?.lap_time_ms), sub: `Lap ${bestLap?.lap_number ?? '—'}`, className: 'purple' },
              { label: 'AVG SPEED',   value: telSummary ? telSummary.avgSpeed.toFixed(1) : '—', sub: 'km/h', className: 'teal' },
              { label: 'TOP SPEED',   value: telSummary ? Math.round(telSummary.topSpeed) : '—', sub: 'km/h', className: 'yellow' },
              { label: 'DRS USAGE',   value: telSummary ? telSummary.drsUsage.toFixed(1) + '%' : '—', sub: 'of lap', className: 'green' },
              { label: 'TYRE STINTS', value: derivedStints.length || '—', sub: 'Total', className: '' },
              { label: 'PIT STOPS',   value: pitStops.length || '—', sub: 'Total', className: '' },
            ].map(({ label, value, sub, icon, className }) => (
              <div key={label} className="kpi-card">
                <div className="kpi-label">{label}</div>
                <div className={`kpi-value ${className}`}>{value}</div>
                {sub  && <div className="kpi-sub" style={{ color: !hasTelemetry && ['AVG SPEED','TOP SPEED','DRS USAGE'].includes(label) ? '#ff8c42' : undefined }}>{sub}</div>}
                {icon && <div className="kpi-icon">{icon}</div>}
              </div>
            ))}
          </div>

          {/* ── Row 1: Track Map + Speed/Throttle ── */}
          <div className="grid-2-5">
            <div className="card">
              <div className="card-header">
                <span className="card-title">Track Map — Lap {selectedLap?.lap_number ?? '—'}</span>
                <span style={{ fontSize: 10, color: '#70b8ff', fontFamily: 'monospace' }}>{session?.track ?? ''}</span>
              </div>
              {loadingTel
                ? <div className="loading-state" style={{ height: 210 }}><div className="spinner" /></div>
                : <TrackMap telemetry={telemetry} />}
            </div>

            <div className="card">
              <div className="card-header">
                <span className="card-title">Speed &amp; Throttle — Lap {selectedLap?.lap_number ?? '—'}</span>
                <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                  {[['#70b8ff', 'Speed (km/h)'], ['#3dffa0', 'Throttle (%)'], ['#ff6b6b', 'Brake (%)']].map(([c, l]) => (
                    <span key={l} style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                      <div style={{ width: 10, height: 2, background: c, borderRadius: 1 }} />
                      <span style={{ fontSize: 8, color: '#a8b8cc' }}>{l}</span>
                    </span>
                  ))}
                </div>
              </div>
              <div className="card-body">
                {loadingTel
                  ? <div className="loading-state" style={{ height: 165 }}><div className="spinner" /></div>
                  : <SpeedThrottleChart telemetry={telemetry} />}
              </div>
            </div>
          </div>

          {/* ── Row 2: 4-panel info ── matches reference image 1 layout ── */}
          <div className="grid-4">

            {/* LAP INFORMATION */}
            <div className="card">
              <PanelHeader title="Lap Information" />
              <div style={{ padding: '4px 0' }}>
                {selectedLap ? <>
                  <InfoRow label="Lap Number" value={`${selectedLap.lap_number} / ${session?.total_laps ?? '?'}`} />
                  <InfoRow label="Lap Time"   value={msToLapTime(selectedLap.lap_time_ms)} color="#70b8ff" />
                  <InfoRow label="Sector 1"   value={msToLapTime(selectedLap.sector1_ms)}  color="#3dffa0" />
                  <InfoRow label="Sector 2"   value={msToLapTime(selectedLap.sector2_ms)}  color="#3dffa0" />
                  <InfoRow label="Sector 3"   value={msToLapTime(selectedLap.sector3_ms)}  color="#3dffa0" />
                  <InfoRow label="Tyre Compound">
                    <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <CompoundBadge compound={selectedLap.compound} size={18} />
                      <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-primary)' }}>{selectedLap.compound}</span>
                    </span>
                  </InfoRow>
                  <InfoRow label="Tyre Age" value={selectedLap.tyre_life != null ? `${selectedLap.tyre_life} laps` : '—'} />
                </> : <div className="empty-state" style={{ height: 140 }}>Select a lap</div>}
              </div>
            </div>

            {/* SECTOR TIMES */}
            <div className="card">
              <PanelHeader title="Sector Times" />
              <div>
                {/* Column header row */}
                <div style={{
                  display: 'grid', gridTemplateColumns: '76px 1fr 1fr 60px',
                  padding: '6px 14px', borderBottom: '1px solid rgba(99,120,155,0.2)',
                  background: 'rgba(99,120,155,0.06)',
                }}>
                  <span style={{ fontSize: 9, color: 'var(--text-muted)' }}></span>
                  <span style={{ fontSize: 9, fontWeight: 700, color: '#70b8ff', fontFamily: 'var(--font-mono)' }}>
                    {selectedDriver?.code ?? 'DRV'} {selectedLap ? `(Lap ${selectedLap.lap_number})` : ''}
                  </span>
                  <span style={{ fontSize: 9, color: 'var(--text-muted)' }}>Session Best</span>
                  <span style={{ fontSize: 9, color: 'var(--text-muted)', textAlign: 'right' }}>Δ</span>
                </div>
                {[
                  ['Sector 1', selectedLap?.sector1_ms, sessionBestSectors.s1],
                  ['Sector 2', selectedLap?.sector2_ms, sessionBestSectors.s2],
                  ['Sector 3', selectedLap?.sector3_ms, sessionBestSectors.s3],
                  ['Lap Time', selectedLap?.lap_time_ms, bestLap?.lap_time_ms],
                ].map(([label, dMs, bMs]) => {
                  const delta = (dMs && bMs) ? dMs - bMs : null;
                  const deltaCol = delta == null ? 'var(--text-muted)' : delta > 0 ? '#ff6b6b' : '#3dffa0';
                  const isLapRow = label === 'Lap Time';
                  return (
                    <div key={label} style={{
                      display: 'grid', gridTemplateColumns: '76px 1fr 1fr 60px',
                      padding: '7px 14px', borderBottom: '1px solid rgba(99,120,155,0.1)',
                      background: isLapRow ? 'rgba(112,184,255,0.05)' : 'transparent',
                    }}>
                      <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{label}</span>
                      <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', fontWeight: 700, color: isLapRow ? '#70b8ff' : 'var(--text-primary)' }}>
                        {msToLapTime(dMs)}
                      </span>
                      <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                        {msToLapTime(bMs)}
                      </span>
                      <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 700, textAlign: 'right', color: deltaCol }}>
                        {msDelta(delta)}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* TYRE STINT OVERVIEW */}
            <div className="card">
              <PanelHeader
                title="Tyre Stint Overview"
                right={derivedStints.length ? (
                  <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                    {[...new Set(derivedStints.map(s => s.stint_number ?? 0))].length} stints
                  </span>
                ) : null}
              />
              {/* Deduplicate by stint_number — keep the entry with most laps */}
              {(() => {
                const seen = new Map();
                derivedStints.forEach(s => {
                  const key = s.stint_number ?? 0;
                  const laps = (s.end_lap ?? 0) - (s.start_lap ?? 0);
                  if (!seen.has(key) || laps > (seen.get(key)._laps ?? 0)) {
                    seen.set(key, { ...s, _laps: laps });
                  }
                });
                const uniq = [...seen.values()].sort((a, b) => (a.stint_number ?? 0) - (b.stint_number ?? 0));
                return uniq.length ? (
                  <div style={{ maxHeight: 280, overflowY: 'auto', padding: '4px 0',
                    scrollbarWidth: 'thin', scrollbarColor: 'rgba(112,184,255,0.3) transparent' }}>
                    {uniq.map((s, i) => (
                      <div key={i} style={{
                        display: 'flex', alignItems: 'center', gap: 10,
                        padding: '8px 14px', borderBottom: '1px solid rgba(99,120,155,0.1)',
                      }}>
                        <div style={{ minWidth: 56 }}>
                          <div style={{ fontSize: 9, fontWeight: 800, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
                            Stint {s.stint_number ?? i + 1}
                          </div>
                          <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 1 }}>
                            Laps {s.start_lap} – {s.end_lap}
                          </div>
                        </div>
                        <CompoundBadge compound={s.compound} size={24} />
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 9, color: 'var(--text-muted)', textTransform: 'uppercase' }}>{s.compound}</div>
                          <div style={{ fontSize: 12, fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--text-primary)', marginTop: 2 }}>
                            {s.best_lap_time_ms
                              ? msToLapTime(s.best_lap_time_ms)
                              : (s.avg_lap_time_ms ? msToLapTime(Math.round(s.avg_lap_time_ms)) : '—')}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : <div className="empty-state" style={{ height: 140 }}>No stint data</div>;
              })()}
            </div>

            {/* WEATHER CONDITIONS */}
            <div className="card">
              <PanelHeader
                title="Weather Conditions"
                right={<span style={{ fontSize: 18 }}>{latestWeather?.rainfall ? '🌧️' : '☀️'}</span>}
              />
              <div style={{ padding: '10px 14px' }}>
                <div style={{
                  fontSize: 24, fontWeight: 900, letterSpacing: '-0.5px', marginBottom: 14,
                  color: latestWeather?.rainfall ? '#70b8ff' : '#ffd555',
                }}>
                  {latestWeather ? (latestWeather.rainfall ? 'Wet' : 'Dry') : '—'}
                </div>
                {latestWeather ? [
                  ['🌡',  'Air Temp',   `${latestWeather.air_temp?.toFixed(1)   ?? '—'} °C`,   '#ff9d4d'],
                  ['🏁',  'Track Temp', `${latestWeather.track_temp?.toFixed(1) ?? '—'} °C`,   '#ff6b6b'],
                  ['💧',  'Humidity',   `${latestWeather.humidity?.toFixed(0)   ?? '—'} %`,    '#70b8ff'],
                  ['💨',  'Wind',       `${latestWeather.wind_speed?.toFixed(1) ?? '—'} km/h`, '#a8b8cc'],
                ].map(([icon, label, value, color]) => (
                  <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                    <span style={{ fontSize: 13, width: 18, textAlign: 'center', flexShrink: 0 }}>{icon}</span>
                    <span style={{ flex: 1, fontSize: 10, color: 'var(--text-muted)' }}>{label}</span>
                    <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', fontWeight: 700, color }}>{value}</span>
                  </div>
                )) : <div className="empty-state" style={{ height: 100 }}>No weather data</div>}
              </div>
            </div>

          </div>

          {/* ── Row 3: Lap Time Evolution + Speed Comparison ── */}
          <div className="grid-2">
            <div className="card">
              <div className="card-header">
                <span className="card-title">Lap Time Evolution</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <div style={{ width: 16, height: 2, background: '#70b8ff', borderRadius: 1 }} />
                  <span style={{ fontSize: 9, color: '#a8b8cc' }}>{selectedDriver?.code}</span>
                </span>
              </div>
              <div className="card-body">
                <LapTimeEvolution laps={laps} driverCode={selectedDriver?.code} pitLaps={pitLapNumbers} />
              </div>
            </div>

            <div className="card">
              <div className="card-header">
                <span className="card-title">Speed Comparison — Lap {selectedLap?.lap_number ?? '—'}</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  {[[selectedDriver?.code, '#70b8ff'], [compareDriver?.code, '#ff6b6b']].filter(([c]) => c).map(([code, color]) => (
                    <span key={code} style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                      <div style={{ width: 12, height: 2, background: color, borderRadius: 1 }} />
                      <span style={{ fontSize: 9, color, fontWeight: 700 }}>{code}</span>
                    </span>
                  ))}
                </span>
              </div>
              <div className="card-body">
                <SpeedComparison
                  tel1={telemetry} tel2={compareTelemetry.length ? compareTelemetry : null}
                  code1={selectedDriver?.code ?? 'DRV'} code2={compareDriver?.code ?? 'CMP'}
                />
              </div>
            </div>
          </div>

          {/* ── Standings Table ── */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">Driver Standings — {session?.event_name ?? ''} {session?.session_type === 'R' ? 'Race' : session?.session_type ?? ''}</span>
              <span style={{ fontSize: 9, color: '#a8b8cc' }}>{standings.length} drivers</span>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table className="standings-table">
                <thead>
                  <tr>
                    <th style={{ width: 36 }}>Pos</th>
                    <th>Driver</th>
                    <th>Team</th>
                    <th style={{ textAlign: 'right' }}>Best Lap</th>
                    <th style={{ textAlign: 'right' }}>Avg Lap</th>
                    <th style={{ textAlign: 'right' }}>Laps</th>
                    <th style={{ textAlign: 'right' }}>Pit Stops</th>
                  </tr>
                </thead>
                <tbody>
                  {standings.map(s => (
                    <tr key={s.driver_id}
                      style={{ cursor: 'pointer', background: String(s.driver_id) === selectedDriverId ? 'rgba(232,0,45,0.07)' : undefined }}
                      onClick={() => setSelectedDriverId(String(s.driver_id))}>
                      <td><span className={`pos-badge${s.position <= 3 ? ` p${s.position}` : ''}`}>{s.position}</span></td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <div style={{ width: 3, height: 18, borderRadius: 2, background: s.team_color || teamColor(s.team), flexShrink: 0 }} />
                          <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{s.driver_code}</span>
                        </div>
                      </td>
                      <td style={{ color: 'var(--text-secondary)', fontSize: 10 }}>{s.team ?? '—'}</td>
                      <td style={{ textAlign: 'right', color: '#d09aff', fontFamily: 'monospace', fontWeight: 600 }}>{msToLapTime(s.fastest_lap_ms)}</td>
                      <td style={{ textAlign: 'right', fontFamily: 'monospace', color: 'var(--text-secondary)', fontSize: 10 }}>{msToLapTime(s.avg_lap_time_ms)}</td>
                      <td style={{ textAlign: 'right', color: 'var(--text-secondary)' }}>{s.total_laps}</td>
                      <td style={{ textAlign: 'right', color: 'var(--text-secondary)' }}>{s.pit_stop_count}</td>
                    </tr>
                  ))}
                  {!standings.length && (
                    <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 24 }}>No standings data</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

        </>)}
      </div>
    </>
  );
}
