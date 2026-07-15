import { useState, useEffect, useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { api } from '../api.js';
import { msToLapTime, teamColor } from '../utils.jsx';

// ── Official F1 2024 driver photos from F1 media CDN ─────────────────────────
// Pattern: https://media.formula1.com/content/dam/fom-website/drivers/{X}/{CODENAMEFULL}/{code}.png
const DRIVER_PHOTOS = {
  VER: 'https://media.formula1.com/content/dam/fom-website/drivers/M/MAXVER01_Max_Verstappen/maxver01.png',
  PER: 'https://media.formula1.com/content/dam/fom-website/drivers/S/SERPER01_Sergio_Perez/serper01.png',
  LEC: 'https://media.formula1.com/content/dam/fom-website/drivers/C/CHALEC01_Charles_Leclerc/chalec01.png',
  SAI: 'https://media.formula1.com/content/dam/fom-website/drivers/C/CARSAI01_Carlos_Sainz/carsai01.png',
  HAM: 'https://media.formula1.com/content/dam/fom-website/drivers/L/LEWHAM01_Lewis_Hamilton/lewham01.png',
  RUS: 'https://media.formula1.com/content/dam/fom-website/drivers/G/GEORUS01_George_Russell/georus01.png',
  NOR: 'https://media.formula1.com/content/dam/fom-website/drivers/L/LANNOR01_Lando_Norris/lannor01.png',
  PIA: 'https://media.formula1.com/content/dam/fom-website/drivers/O/OSCPIA01_Oscar_Piastri/oscpia01.png',
  ALO: 'https://media.formula1.com/content/dam/fom-website/drivers/F/FERALO01_Fernando_Alonso/feralo01.png',
  STR: 'https://media.formula1.com/content/dam/fom-website/drivers/L/LANSTR01_Lance_Stroll/lanstr01.png',
  GAS: 'https://media.formula1.com/content/dam/fom-website/drivers/P/PIEGAS01_Pierre_Gasly/piegas01.png',
  OCO: 'https://media.formula1.com/content/dam/fom-website/drivers/E/ESTOCO01_Esteban_Ocon/estoco01.png',
  BOT: 'https://media.formula1.com/content/dam/fom-website/drivers/V/VALBOT01_Valtteri_Bottas/valbot01.png',
  ZHO: 'https://media.formula1.com/content/dam/fom-website/drivers/G/GUAZHO01_Guanyu_Zhou/guazho01.png',
  MAG: 'https://media.formula1.com/content/dam/fom-website/drivers/K/KEVMAG01_Kevin_Magnussen/kevmag01.png',
  HUL: 'https://media.formula1.com/content/dam/fom-website/drivers/N/NICHUL01_Nico_Hulkenberg/nichul01.png',
  TSU: 'https://media.formula1.com/content/dam/fom-website/drivers/Y/YUKTSU01_Yuki_Tsunoda/yuktsu01.png',
  RIC: 'https://media.formula1.com/content/dam/fom-website/drivers/D/DANRIC01_Daniel_Ricciardo/danric01.png',
  ALB: 'https://media.formula1.com/content/dam/fom-website/drivers/A/ALEALB01_Alexander_Albon/alealb01.png',
  SAR: 'https://media.formula1.com/content/dam/fom-website/drivers/L/LOGSAR01_Logan_Sargeant/logsar01.png',
  COL: 'https://media.formula1.com/content/dam/fom-website/drivers/F/FRACOL01_Franco_Colapinto/fracol01.png',
  LAW: 'https://media.formula1.com/content/dam/fom-website/drivers/L/LIALAW01_Liam_Lawson/lialaw01.png',
};

// ── Driver race numbers ───────────────────────────────────────────────────────
const DRIVER_NUMBERS = {
  VER: 1, LEC: 16, SAI: 55, HAM: 44, RUS: 63, NOR: 4, PIA: 81,
  ALO: 14, STR: 18, GAS: 10, OCO: 31, BOT: 77, ZHO: 24, MAG: 20,
  HUL: 27, TSU: 22, RIC: 3, ALB: 23, SAR: 2, PER: 11, COL: 43, LAW: 40,
};

// ── Driver full names ─────────────────────────────────────────────────────────
const DRIVER_NAMES = {
  VER: 'Max Verstappen', LEC: 'Charles Leclerc', SAI: 'Carlos Sainz',
  HAM: 'Lewis Hamilton', RUS: 'George Russell', NOR: 'Lando Norris',
  PIA: 'Oscar Piastri', ALO: 'Fernando Alonso', STR: 'Lance Stroll',
  GAS: 'Pierre Gasly', OCO: 'Esteban Ocon', BOT: 'Valtteri Bottas',
  ZHO: 'Guanyu Zhou', MAG: 'Kevin Magnussen', HUL: 'Nico Hülkenberg',
  TSU: 'Yuki Tsunoda', RIC: 'Daniel Ricciardo', ALB: 'Alexander Albon',
  SAR: 'Logan Sargeant', PER: 'Sergio Pérez', COL: 'Franco Colapinto', LAW: 'Liam Lawson',
};

const POS_MEDAL = { 1: '🥇', 2: '🥈', 3: '🥉' };
const POS_COLORS = { 1: '#fbbf24', 2: '#d1d5db', 3: '#cd7f32' };

// ── Driver Photo Component ────────────────────────────────────────────────────
function DriverPhoto({ code, teamCol, size = 80 }) {
  const [failed, setFailed] = useState(false);
  const photoUrl = DRIVER_PHOTOS[code];
  const initials = code ? code.slice(0, 2) : '??';
  const num = DRIVER_NUMBERS[code];

  if (!photoUrl || failed) {
    // Premium fallback: team-colored avatar with number + initials
    return (
      <div style={{
        width: size, height: size, borderRadius: size * 0.15, flexShrink: 0,
        background: `linear-gradient(135deg, ${teamCol}22, ${teamCol}44)`,
        border: `2px solid ${teamCol}`,
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        position: 'relative', overflow: 'hidden',
      }}>
        {/* Number watermark */}
        {num && (
          <div style={{
            position: 'absolute', bottom: -4, right: -2,
            fontSize: size * 0.55, fontWeight: 900, color: `${teamCol}30`,
            fontFamily: 'Arial Black, monospace', lineHeight: 1, userSelect: 'none',
          }}>{num}</div>
        )}
        <div style={{ fontSize: size * 0.3, fontWeight: 900, color: teamCol, fontFamily: 'monospace', zIndex: 1 }}>
          {initials}
        </div>
        {num && (
          <div style={{ fontSize: size * 0.16, color: `${teamCol}88`, fontFamily: 'monospace', zIndex: 1 }}>#{num}</div>
        )}
      </div>
    );
  }

  return (
    <div style={{
      width: size, height: size, borderRadius: size * 0.15, flexShrink: 0,
      background: `linear-gradient(135deg, ${teamCol}22, ${teamCol}11)`,
      border: `2px solid ${teamCol}44`,
      overflow: 'hidden', position: 'relative',
    }}>
      <img
        src={photoUrl}
        alt={DRIVER_NAMES[code] || code}
        onError={() => setFailed(true)}
        style={{ width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'top center' }}
      />
    </div>
  );
}

// ── Driver List Row ───────────────────────────────────────────────────────────
function DriverRow({ standing, isSelected, onClick }) {
  const [photoFailed, setPhotoFailed] = useState(false);
  const tColor = standing.team_color || teamColor(standing.team);
  const photoUrl = DRIVER_PHOTOS[standing.driver_code];
  const posColor = POS_COLORS[standing.position] || 'var(--text-muted)';

  return (
    <div onClick={onClick} style={{
      display: 'flex', alignItems: 'center', gap: 10, padding: '8px 14px',
      cursor: 'pointer', borderBottom: '1px solid var(--border)',
      background: isSelected ? `${tColor}12` : 'transparent',
      borderLeft: isSelected ? `3px solid ${tColor}` : '3px solid transparent',
      transition: 'all 0.12s',
    }}>
      {/* Position */}
      <div style={{ width: 24, textAlign: 'right', fontFamily: 'monospace', fontWeight: 800, fontSize: 13, color: posColor, flexShrink: 0 }}>
        {POS_MEDAL[standing.position] || standing.position}
      </div>

      {/* Mini photo thumbnail */}
      <div style={{ width: 32, height: 32, borderRadius: 6, flexShrink: 0, overflow: 'hidden',
        background: `${tColor}22`, border: `1.5px solid ${tColor}44` }}>
        {photoUrl && !photoFailed ? (
          <img src={photoUrl} alt={standing.driver_code} onError={() => setPhotoFailed(true)}
            style={{ width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'top' }} />
        ) : (
          <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 9, fontWeight: 900, color: tColor, fontFamily: 'monospace' }}>
            {standing.driver_code?.slice(0, 2)}
          </div>
        )}
      </div>

      {/* Team color bar */}
      <div style={{ width: 3, height: 28, borderRadius: 2, background: tColor, flexShrink: 0 }} />

      {/* Name + team */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12, fontWeight: 800, color: isSelected ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
          {standing.driver_code}
        </div>
        <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {standing.team}
        </div>
      </div>

      {/* Best lap */}
      <div style={{ textAlign: 'right', flexShrink: 0 }}>
        <div style={{ fontSize: 10, fontFamily: 'monospace', fontWeight: 700, color: '#c084fc' }}>
          {msToLapTime(standing.fastest_lap_ms)}
        </div>
        <div style={{ fontSize: 8, color: 'var(--text-muted)' }}>{standing.total_laps} laps</div>
      </div>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────
export default function Drivers() {
  const [sessions, setSessions] = useState([]);
  const [sessionId, setSessionId] = useState('1');
  const [drivers, setDrivers] = useState([]);
  const [standings, setStandings] = useState([]);
  const [selectedDriverId, setSelectedDriverId] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.getSessions()
      .then(s => { setSessions(s); if (s.length) setSessionId(String(s[0].session_id)); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!sessionId) return;
    setLoading(true);
    setSelectedDriverId(null);
    Promise.allSettled([api.getDrivers(sessionId), api.getStandings(sessionId)])
      .then(([dR, sR]) => {
        const drvs = dR.status === 'fulfilled' ? dR.value : [];
        const stand = sR.status === 'fulfilled' ? sR.value : [];
        setDrivers(drvs);
        setStandings(stand);
        if (stand.length) setSelectedDriverId(stand[0].driver_id);
      }).finally(() => setLoading(false));
  }, [sessionId]);

  const standMap = useMemo(() => Object.fromEntries(standings.map(s => [s.driver_id, s])), [standings]);
  const selStand = standMap[selectedDriverId];
  const selDriver = drivers.find(d => d.driver_id === selectedDriverId);
  const tColor = selDriver ? (selDriver.team_color || teamColor(selDriver.team)) : '#e8002d';

  // Gap chart data (top 15 vs selected)
  const gapData = useMemo(() => {
    if (!selStand?.fastest_lap_ms) return [];
    return standings
      .filter(s => s.driver_id !== selectedDriverId && s.fastest_lap_ms)
      .slice(0, 14)
      .map(s => ({
        code: s.driver_code,
        gap: +((s.fastest_lap_ms - selStand.fastest_lap_ms) / 1000).toFixed(3),
        color: s.team_color || teamColor(s.team),
      }));
  }, [standings, selectedDriverId, selStand]);

  const session = sessions.find(s => String(s.session_id) === sessionId);

  return (
    <div className="content-area">
      {/* Header */}
      <div className="page-header">
        <div>
          <div className="page-title">Drivers</div>
          <div className="page-desc">All {drivers.length} drivers — session standings, lap times and performance data</div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {session && (
            <span style={{ fontSize: 11, color: 'var(--text-muted)', background: 'var(--bg-card)', padding: '4px 10px', borderRadius: 12, border: '1px solid var(--border)' }}>
              {session.event_name} {session.year}
            </span>
          )}
          <select className="filter-select" value={sessionId} onChange={e => setSessionId(e.target.value)}>
            {sessions.map(s => <option key={s.session_id} value={s.session_id}>{s.event_name} {s.year}</option>)}
          </select>
        </div>
      </div>

      {loading && <div className="loading-state"><div className="spinner" /><span>Loading drivers...</span></div>}

      {!loading && (
        <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 10, alignItems: 'start' }}>

          {/* ── Left: standings list ── */}
          <div className="card" style={{ overflow: 'hidden' }}>
            <div className="card-header">
              <span className="card-title">Race Standings</span>
              <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{standings.length} drivers</span>
            </div>
            <div style={{ overflowY: 'auto', maxHeight: 560 }}>
              {standings.map(s => (
                <DriverRow key={s.driver_id} standing={s} isSelected={selectedDriverId === s.driver_id}
                  onClick={() => setSelectedDriverId(s.driver_id)} />
              ))}
              {!standings.length && (
                <div className="empty-state" style={{ height: 160 }}>
                  <span>No driver data for this session</span>
                </div>
              )}
            </div>
          </div>

          {/* ── Right: selected driver detail ── */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {selDriver && selStand ? (
              <>
                {/* Hero card with big photo */}
                <div className="card" style={{
                  borderColor: `${tColor}44`,
                  background: `linear-gradient(135deg, ${tColor}14 0%, rgba(13,17,23,0.3) 60%)`,
                }}>
                  <div className="card-body">
                    <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>

                      {/* Big driver photo */}
                      <DriverPhoto code={selDriver.code} teamCol={tColor} size={110} />

                      {/* Name + number */}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
                          <div>
                            {/* Driver number */}
                            {DRIVER_NUMBERS[selDriver.code] && (
                              <div style={{ fontSize: 11, color: tColor, fontFamily: 'monospace', fontWeight: 800, letterSpacing: 1, marginBottom: 2 }}>
                                #{DRIVER_NUMBERS[selDriver.code]}
                              </div>
                            )}
                            {/* 3-letter code */}
                            <div style={{ fontSize: 36, fontWeight: 900, color: 'var(--text-primary)', letterSpacing: '-2px', lineHeight: 1 }}>
                              {selDriver.code}
                            </div>
                            {/* Full name */}
                            <div style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 4 }}>
                              {DRIVER_NAMES[selDriver.code] || selDriver.full_name}
                            </div>
                            {/* Team */}
                            <div style={{ fontSize: 11, color: tColor, fontWeight: 700, marginTop: 3 }}>
                              {selDriver.team}
                            </div>
                          </div>
                          {/* Position medal */}
                          <div style={{ textAlign: 'center', flexShrink: 0 }}>
                            <div style={{ fontSize: 42 }}>{POS_MEDAL[selStand.position] || ''}</div>
                            <div style={{
                              fontSize: 28, fontWeight: 900, fontFamily: 'monospace',
                              color: POS_COLORS[selStand.position] || 'var(--text-secondary)',
                              lineHeight: 1,
                            }}>
                              {POS_MEDAL[selStand.position] ? '' : `P${selStand.position}`}
                            </div>
                            <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 2 }}>POSITION</div>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Stats grid */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginTop: 16 }}>
                      {[
                        ['Best Lap Time', msToLapTime(selStand.fastest_lap_ms), '#c084fc'],
                        ['Average Lap', msToLapTime(selStand.avg_lap_time_ms ? Math.round(selStand.avg_lap_time_ms) : null), '#60a5fa'],
                        ['Total Laps', selStand.total_laps, '#34d399'],
                        ['Pit Stops', selStand.pit_stop_count, '#f87171'],
                        ['Gap to Leader', (() => {
                          const p1 = standings[0]?.fastest_lap_ms;
                          const mine = selStand.fastest_lap_ms;
                          if (!p1 || !mine) return '—';
                          const diff = mine - p1;
                          return diff === 0 ? 'LEADER' : `+${(diff / 1000).toFixed(3)}s`;
                        })(), selStand.position === 1 ? '#34d399' : '#f87171'],
                        ['Race Number', DRIVER_NUMBERS[selDriver.code] ? `#${DRIVER_NUMBERS[selDriver.code]}` : '—', tColor],
                      ].map(([label, value, color]) => (
                        <div key={label} style={{ background: 'rgba(22,27,34,0.7)', borderRadius: 8, padding: '10px 12px', border: '1px solid var(--border)' }}>
                          <div style={{ fontSize: 9, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</div>
                          <div style={{ fontSize: 16, fontFamily: 'monospace', fontWeight: 800, color, marginTop: 3 }}>{value ?? '—'}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Gap chart */}
                {gapData.length > 0 && (
                  <div className="card">
                    <div className="card-header">
                      <span className="card-title">Gap to {selDriver.code}</span>
                      <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                        {selStand.position === 1 ? 'Leader' : `P${selStand.position} — ${msToLapTime(selStand.fastest_lap_ms)}`}
                      </span>
                    </div>
                    <div className="card-body" style={{ padding: '8px 0' }}>
                      <ResponsiveContainer width="100%" height={Math.min(gapData.length * 28, 320)}>
                        <BarChart data={gapData} layout="vertical" margin={{ top: 2, right: 60, bottom: 2, left: 36 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="rgba(48,54,61,0.4)" horizontal={false} />
                          <XAxis type="number" tick={{ fontSize: 8, fill: '#6e7681', fontFamily: 'monospace' }} tickLine={false}
                            tickFormatter={v => `${v > 0 ? '+' : ''}${v}s`} />
                          <YAxis type="category" dataKey="code" tick={{ fontSize: 10, fill: 'var(--text-primary)', fontWeight: 700 }} tickLine={false} axisLine={false} width={34} />
                          <Tooltip
                            formatter={(v) => [`${v > 0 ? '+' : ''}${v}s`, 'Gap']}
                            contentStyle={{ background: 'rgba(22,27,34,0.97)', border: '1px solid rgba(48,54,61,0.9)', borderRadius: 4, fontSize: 10 }} />
                          <Bar dataKey="gap" radius={[0, 4, 4, 0]} maxBarSize={16}
                            fill="#34d399"
                            label={{ position: 'right', fontSize: 9, fill: '#34d399', fontFamily: 'monospace',
                              formatter: v => `${v > 0 ? '+' : ''}${v}s` }} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                )}

                {/* All drivers grid with mini photos */}
                <div className="card">
                  <div className="card-header">
                    <span className="card-title">All Drivers — {session?.event_name}</span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, padding: '12px' }}>
                    {standings.map(s => {
                      const tc = s.team_color || teamColor(s.team);
                      const isSel = s.driver_id === selectedDriverId;
                      return (
                        <div key={s.driver_id} onClick={() => setSelectedDriverId(s.driver_id)}
                          style={{
                            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6,
                            padding: '10px 6px', borderRadius: 8, cursor: 'pointer',
                            background: isSel ? `${tc}18` : 'rgba(22,27,34,0.4)',
                            border: `1px solid ${isSel ? tc : 'var(--border)'}`,
                            transition: 'all 0.15s',
                          }}>
                          <DriverPhoto code={s.driver_code} teamCol={tc} size={52} />
                          <div style={{ fontSize: 11, fontWeight: 800, color: isSel ? tc : 'var(--text-primary)' }}>{s.driver_code}</div>
                          <div style={{ fontSize: 8, color: POS_COLORS[s.position] || 'var(--text-muted)', fontWeight: 700 }}>P{s.position}</div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </>
            ) : (
              <div className="card">
                <div className="empty-state" style={{ height: 300 }}>
                  <span style={{ fontSize: 36 }}>👆</span>
                  <span>Select a driver from the standings</span>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
