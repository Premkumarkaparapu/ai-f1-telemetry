import { useState, useEffect } from 'react';
import { api } from '../api.js';
import { msToLapTime, CompoundBadge } from '../utils.jsx';

export default function Stints() {
  const [sessions, setSessions] = useState([]);
  const [sessionId, setSessionId] = useState('1');
  const [drivers, setDrivers] = useState([]);
  const [standings, setStandings] = useState([]);
  const [stintData, setStintData] = useState({});
  const [loading, setLoading] = useState(false);

  useEffect(() => { api.getSessions().then(s => { setSessions(s); if(s.length) setSessionId(String(s[0].session_id)); }).catch(()=>{}); }, []);

  useEffect(() => {
    if(!sessionId) return;
    setLoading(true);
    Promise.allSettled([api.getDrivers(sessionId), api.getStandings(sessionId)]).then(([dR, sR]) => {
      const drvs = dR.status === 'fulfilled' ? dR.value : [];
      const stand = sR.status === 'fulfilled' ? sR.value : [];
      setDrivers(drvs); setStandings(stand);
      // Load stints for all drivers
      Promise.allSettled(drvs.map(d => api.getStints(d.driver_id, sessionId).then(st => ({ driverId: d.driver_id, code: d.code, stints: st }))))
        .then(results => {
          const map = {};
          results.forEach(r => { if(r.status==='fulfilled') map[r.value.driverId] = r.value; });
          setStintData(map);
        }).finally(() => setLoading(false));
    });
  }, [sessionId]);

  const COMPOUND_COLORS = { SOFT:'#e8002d', MEDIUM:'#fbbf24', HARD:'#f0f6fc', INTERMEDIATE:'#34d399', WET:'#60a5fa' };
  const maxLaps = 57;

  return (
    <div className="content-area">
      <div className="page-header">
        <div><div className="page-title">🔄 Tyre Stints</div><div className="page-desc">Stint-by-stint compound and tyre life breakdown for all drivers</div></div>
        <select className="filter-select" value={sessionId} onChange={e => setSessionId(e.target.value)}>
          {sessions.map(s => <option key={s.session_id} value={s.session_id}>{s.event_name} {s.year}</option>)}
        </select>
      </div>

      {loading && <div className="loading-state"><div className="spinner" /><span>Loading stint data…</span></div>}

      {!loading && (
        <div className="card">
          <div className="card-header"><span className="card-title">Race Stint Map</span><div style={{ display:'flex', gap:12 }}>
            {Object.keys(COMPOUND_COLORS).map(c => (
              <span key={c} style={{ display:'flex', alignItems:'center', gap:4 }}>
                <div style={{ width:10, height:10, borderRadius:2, background:COMPOUND_COLORS[c], opacity:0.8 }} />
                <span style={{ fontSize:9, color:'var(--text-muted)' }}>{c}</span>
              </span>
            ))}
          </div></div>
          <div className="card-body">
            {/* Stint timeline for each driver */}
            {standings.map(s => {
              const dStints = stintData[s.driver_id]?.stints ?? [];
              return (
                <div key={s.driver_id} style={{ display:'flex', alignItems:'center', gap:10, marginBottom:8 }}>
                  <div style={{ width:36, fontSize:11, fontWeight:700, color:'var(--text-secondary)', textAlign:'right', flexShrink:0 }}>{s.driver_code}</div>
                  <div style={{ flex:1, height:22, background:'rgba(22,27,34,0.5)', borderRadius:3, position:'relative', overflow:'hidden' }}>
                    {dStints.map((st, i) => {
                      const startPct = ((st.start_lap-1)/maxLaps*100).toFixed(2);
                      const widthPct = ((st.end_lap-st.start_lap+1)/maxLaps*100).toFixed(2);
                      const color = COMPOUND_COLORS[st.compound] ?? '#888';
                      return (
                        <div key={i} title={`${st.compound}: Laps ${st.start_lap}–${st.end_lap}`}
                          style={{ position:'absolute', left:`${startPct}%`, width:`${widthPct}%`, height:'100%',
                            background: color, opacity:0.75, borderRight:'1px solid rgba(22,27,34,0.8)',
                            display:'flex', alignItems:'center', justifyContent:'center', overflow:'hidden' }}>
                          <span style={{ fontSize:8, fontWeight:700, color:st.compound==='HARD'?'#0d1117':'white', whiteSpace:'nowrap' }}>
                            {st.compound?.[0]}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}

            {/* Lap markers */}
            <div style={{ display:'flex', alignItems:'center', gap:10, marginTop:4 }}>
              <div style={{ width:36 }} />
              <div style={{ flex:1, position:'relative', height:12 }}>
                {[1,10,20,30,40,50,57].map(lap => (
                  <span key={lap} style={{ position:'absolute', left:`${((lap-1)/maxLaps*100).toFixed(2)}%`, fontSize:7, color:'var(--text-muted)', fontFamily:'monospace', transform:'translateX(-50%)' }}>{lap}</span>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Detailed table */}
      {!loading && Object.keys(stintData).length > 0 && (
        <div className="card" style={{ marginTop:10 }}>
          <div className="card-header"><span className="card-title">Stint Details</span></div>
          <div style={{ overflowX:'auto', maxHeight:340, overflowY:'auto' }}>
            <table className="standings-table" style={{ width:'100%' }}>
              <thead style={{ position:'sticky', top:0 }}>
                <tr><th>Driver</th><th>Stint</th><th>Compound</th><th>Start Lap</th><th>End Lap</th><th>Stint Length</th><th>Starting Life</th></tr>
              </thead>
              <tbody>
                {standings.flatMap(s => {
                  const dStints = stintData[s.driver_id]?.stints ?? [];
                  return dStints.map((st, i) => (
                    <tr key={`${s.driver_id}-${i}`}>
                      <td style={{ fontWeight:600, color:'var(--text-primary)' }}>{s.driver_code}</td>
                      <td style={{ fontFamily:'monospace', color:'var(--text-muted)' }}>Stint {st.stint_number}</td>
                      <td><span style={{ display:'flex', alignItems:'center', gap:5 }}><CompoundBadge compound={st.compound} size={16} /><span style={{ fontSize:10 }}>{st.compound}</span></span></td>
                      <td style={{ fontFamily:'monospace' }}>{st.start_lap}</td>
                      <td style={{ fontFamily:'monospace' }}>{st.end_lap}</td>
                      <td style={{ fontFamily:'monospace', color:'#60a5fa' }}>{st.end_lap - st.start_lap + 1} laps</td>
                      <td style={{ fontFamily:'monospace', color:'var(--text-muted)' }}>{st.tyre_life_start ?? 1} laps old</td>
                    </tr>
                  ));
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
