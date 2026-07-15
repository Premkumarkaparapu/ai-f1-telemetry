import { useState, useEffect } from 'react';
import { api } from '../api.js';
import { msToLapTime } from '../utils.jsx';

export default function PitStops() {
  const [sessions, setSessions] = useState([]);
  const [sessionId, setSessionId] = useState('1');
  const [drivers, setDrivers] = useState([]);
  const [standings, setStandings] = useState([]);
  const [allPits, setAllPits] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => { api.getSessions().then(s => { setSessions(s); if(s.length) setSessionId(String(s[0].session_id)); }).catch(()=>{}); }, []);

  useEffect(() => {
    if(!sessionId) return;
    setLoading(true);
    Promise.allSettled([api.getDrivers(sessionId), api.getStandings(sessionId)]).then(([dR, sR]) => {
      const drvs = dR.status === 'fulfilled' ? dR.value : [];
      const stand = sR.status === 'fulfilled' ? sR.value : [];
      setDrivers(drvs); setStandings(stand);

      // Derive pit laps from lap data (is_pit_lap=true)
      Promise.allSettled(drvs.map(d =>
        api.getLaps(d.driver_id).then(laps => ({
          driver: d,
          pitLaps: laps.filter(l => l.is_pit_lap),
        }))
      )).then(results => {
        const pits = [];
        results.forEach(r => {
          if(r.status === 'fulfilled') {
            r.value.pitLaps.forEach(l => pits.push({
              driver_code: r.value.driver.code,
              team: r.value.driver.team,
              team_color: r.value.driver.team_color,
              lap_number: l.lap_number,
              lap_time_ms: l.lap_time_ms,
              compound_after: l.compound,
            }));
          }
        });
        pits.sort((a,b) => a.lap_number - b.lap_number);
        setAllPits(pits);
      }).finally(() => setLoading(false));
    });
  }, [sessionId]);

  const avgPitLap = allPits.length ? (allPits.reduce((a,p)=>a+p.lap_number,0)/allPits.length).toFixed(1) : '—';
  const pitsByLap = allPits.reduce((a,p) => { a[p.lap_number] = (a[p.lap_number]||0)+1; return a; }, {});
  const busiest = Object.entries(pitsByLap).sort((a,b)=>b[1]-a[1])[0];

  return (
    <div className="content-area">
      <div className="page-header">
        <div><div className="page-title">🔧 Pit Stops</div><div className="page-desc">All pit stop laps — lap number, compound change, and timing</div></div>
        <select className="filter-select" value={sessionId} onChange={e => setSessionId(e.target.value)}>
          {sessions.map(s => <option key={s.session_id} value={s.session_id}>{s.event_name} {s.year}</option>)}
        </select>
      </div>

      {loading && <div className="loading-state"><div className="spinner" /><span>Loading pit stops…</span></div>}

      {!loading && (
        <>
          <div className="kpi-row" style={{ marginBottom:10 }}>
            {[
              ['Total Pit Stops', allPits.length, 'across all drivers', '#e8002d'],
              ['Avg Pit Lap', avgPitLap, 'of 57', '#fbbf24'],
              ['Busiest Lap', busiest ? `Lap ${busiest[0]}` : '—', busiest ? `${busiest[1]} cars` : '', '#60a5fa'],
              ['Drivers Who Pitted', new Set(allPits.map(p=>p.driver_code)).size, 'drivers', '#34d399'],
            ].map(([label, val, sub, color]) => (
              <div key={label} className="kpi-card">
                <div className="kpi-label">{label}</div>
                <div className="kpi-value" style={{ color, fontSize:18 }}>{val}</div>
                {sub && <div className="kpi-sub">{sub}</div>}
              </div>
            ))}
          </div>

          <div className="card">
            <div className="card-header"><span className="card-title">All Pit Stop Laps</span><span style={{fontSize:10,color:'var(--text-muted)'}}>{allPits.length} total</span></div>
            <div style={{ overflowX:'auto', maxHeight:460, overflowY:'auto' }}>
              <table className="standings-table" style={{ width:'100%' }}>
                <thead style={{ position:'sticky', top:0 }}>
                  <tr><th>Driver</th><th>Team</th><th>Pit Lap</th><th>Compound After</th><th>Lap Time</th><th>Note</th></tr>
                </thead>
                <tbody>
                  {allPits.map((p, i) => (
                    <tr key={i}>
                      <td>
                        <div style={{ display:'flex', alignItems:'center', gap:6 }}>
                          <div style={{ width:3, height:16, borderRadius:2, background: p.team_color||'#888' }} />
                          <span style={{ fontWeight:700, color:'var(--text-primary)' }}>{p.driver_code}</span>
                        </div>
                      </td>
                      <td style={{ color:'var(--text-muted)', fontSize:10 }}>{p.team}</td>
                      <td style={{ fontFamily:'monospace', fontWeight:700, color:'#fbbf24' }}>Lap {p.lap_number}</td>
                      <td>
                        <span style={{ display:'flex', alignItems:'center', gap:5 }}>
                          <div style={{ width:12, height:12, borderRadius:'50%',
                            background: {SOFT:'#e8002d',MEDIUM:'#fbbf24',HARD:'#f0f6fc',INTERMEDIATE:'#34d399'}[p.compound_after]||'#888' }} />
                          <span style={{ fontSize:10 }}>{p.compound_after}</span>
                        </span>
                      </td>
                      <td style={{ fontFamily:'monospace', color:'#f87171' }}>{msToLapTime(p.lap_time_ms)}</td>
                      <td style={{ fontSize:9, color:'var(--text-muted)' }}>Includes pit time</td>
                    </tr>
                  ))}
                  {!allPits.length && <tr><td colSpan={6} style={{ textAlign:'center', color:'var(--text-muted)', padding:32 }}>No pit lap data found</td></tr>}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
