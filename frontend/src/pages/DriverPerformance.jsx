import { useState, useEffect, useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line, Legend, ScatterChart, Scatter } from 'recharts';
import { api } from '../api.js';
import { msToLapTime, teamColor } from '../utils.jsx';

export default function DriverPerformance() {
  const [sessions, setSessions] = useState([]);
  const [sessionId, setSessionId] = useState('1');
  const [standings, setStandings] = useState([]);
  const [drivers, setDrivers] = useState([]);
  const [allLaps, setAllLaps] = useState({});
  const [loading, setLoading] = useState(false);

  useEffect(() => { api.getSessions().then(s => { setSessions(s); if(s.length) setSessionId(String(s[0].session_id)); }).catch(()=>{}); }, []);
  useEffect(() => {
    if(!sessionId) return;
    setLoading(true);
    Promise.allSettled([api.getStandings(sessionId), api.getDrivers(sessionId)]).then(([sR, dR]) => {
      const stand = sR.status==='fulfilled' ? sR.value : [];
      const drvs = dR.status==='fulfilled' ? dR.value : [];
      setStandings(stand); setDrivers(drvs);
      // Load top 10 drivers laps
      const top10 = stand.slice(0,10);
      Promise.allSettled(top10.map(s => api.getLaps(s.driver_id).then(laps => ({ driver_id: s.driver_id, code: s.driver_code, laps }))))
        .then(results => {
          const map = {};
          results.forEach(r => { if(r.status==='fulfilled') map[r.value.driver_id] = r.value; });
          setAllLaps(map);
        }).finally(() => setLoading(false));
    });
  }, [sessionId]);

  // Best lap bar chart
  const bestLapBar = useMemo(() => standings.filter(s=>s.fastest_lap_ms).slice(0,10).map(s => ({
    code: s.driver_code,
    ms: s.fastest_lap_ms,
    time_s: +(s.fastest_lap_ms/1000).toFixed(3),
    team: s.team,
  })), [standings]);

  // Avg lap bar chart
  const avgLapBar = useMemo(() => standings.filter(s=>s.avg_lap_time_ms).slice(0,10).map(s => ({
    code: s.driver_code,
    time_s: +(s.avg_lap_time_ms/1000).toFixed(3),
    team: s.team,
  })), [standings]);

  // Gap to leader
  const fastestOverall = standings.length ? standings[0].fastest_lap_ms : null;
  const gapBar = useMemo(() => standings.filter(s=>s.fastest_lap_ms).slice(0,10).map(s => ({
    code: s.driver_code,
    gap_ms: s.fastest_lap_ms - (fastestOverall??s.fastest_lap_ms),
    team: s.team,
  })), [standings, fastestOverall]);

  // Lap consistency (std dev)
  const consistency = useMemo(() => Object.values(allLaps).map(({ code, laps }) => {
    const valid = laps.filter(l=>l.is_valid&&l.lap_time_ms).map(l=>l.lap_time_ms);
    if(valid.length<3) return null;
    const mean = valid.reduce((a,b)=>a+b,0)/valid.length;
    const std = Math.sqrt(valid.reduce((a,b)=>a+(b-mean)**2,0)/valid.length);
    return { code, std_ms: +std.toFixed(0), std_s: +(std/1000).toFixed(3), mean_s: +(mean/1000).toFixed(3) };
  }).filter(Boolean).sort((a,b)=>a.std_ms-b.std_ms), [allLaps]);

  return (
    <div className="content-area">
      <div className="page-header">
        <div><div className="page-title">📊 Driver Performance</div><div className="page-desc">Comparative analysis — best laps, average pace, consistency, gap to leader</div></div>
        <select className="filter-select" value={sessionId} onChange={e => setSessionId(e.target.value)}>
          {sessions.map(s => <option key={s.session_id} value={s.session_id}>{s.event_name} {s.year}</option>)}
        </select>
      </div>

      {loading && <div className="loading-state"><div className="spinner" /><span>Loading performance data…</span></div>}

      {!loading && (
        <>
          <div className="grid-2" style={{ marginBottom:10 }}>
            {/* Best Lap */}
            <div className="card">
              <div className="card-header"><span className="card-title">Best Lap — Top 10</span></div>
              <div className="card-body">
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={bestLapBar} layout="vertical" margin={{top:4,right:20,bottom:4,left:28}}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(48,54,61,0.45)" horizontal={false} />
                    <XAxis type="number" tick={{fontSize:8, fill:'#6e7681', fontFamily:'monospace'}} tickLine={false} domain={['auto','auto']} />
                    <YAxis type="category" dataKey="code" tick={{fontSize:10, fill:'var(--text-primary)', fontWeight:600}} tickLine={false} axisLine={false} />
                    <Tooltip formatter={v=>[`${v}s`, 'Best Lap']} contentStyle={{background:'rgba(22,27,34,0.97)', border:'1px solid rgba(48,54,61,0.9)', borderRadius:4, fontSize:10}} />
                    <Bar dataKey="time_s" fill="#c084fc" radius={[0,3,3,0]} opacity={0.85} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Gap to leader */}
            <div className="card">
              <div className="card-header"><span className="card-title">Gap to Fastest — ms</span></div>
              <div className="card-body">
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={gapBar} layout="vertical" margin={{top:4,right:20,bottom:4,left:28}}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(48,54,61,0.45)" horizontal={false} />
                    <XAxis type="number" tick={{fontSize:8, fill:'#6e7681', fontFamily:'monospace'}} tickLine={false} />
                    <YAxis type="category" dataKey="code" tick={{fontSize:10, fill:'var(--text-primary)', fontWeight:600}} tickLine={false} axisLine={false} />
                    <Tooltip formatter={v=>[`+${v}ms`, 'Gap to P1']} contentStyle={{background:'rgba(22,27,34,0.97)', border:'1px solid rgba(48,54,61,0.9)', borderRadius:4, fontSize:10}} />
                    <Bar dataKey="gap_ms" fill="#f87171" radius={[0,3,3,0]} opacity={0.85} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* Consistency */}
          <div className="card" style={{ marginBottom:10 }}>
            <div className="card-header"><span className="card-title">⚡ Lap Time Consistency (Std Dev) — Lower = More Consistent</span></div>
            <div className="card-body">
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={consistency} margin={{top:4,right:12,bottom:16,left:8}}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(48,54,61,0.45)" vertical={false} />
                  <XAxis dataKey="code" tick={{fontSize:9, fill:'var(--text-primary)', fontWeight:600}} tickLine={false} />
                  <YAxis tick={{fontSize:8, fill:'#6e7681', fontFamily:'monospace'}} tickLine={false} axisLine={false} width={32} />
                  <Tooltip formatter={(v,n)=>[`${v}s`, 'Std Dev']} contentStyle={{background:'rgba(22,27,34,0.97)', border:'1px solid rgba(48,54,61,0.9)', borderRadius:4, fontSize:10}} />
                  <Bar dataKey="std_s" fill="#34d399" radius={[3,3,0,0]} opacity={0.85} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Full standings table */}
          <div className="card">
            <div className="card-header"><span className="card-title">Full Performance Table</span></div>
            <div style={{ overflowX:'auto' }}>
              <table className="standings-table" style={{ width:'100%' }}>
                <thead>
                  <tr><th>Pos</th><th>Driver</th><th>Team</th><th>Best Lap</th><th>Avg Lap</th><th>Gap to P1</th><th>Total Laps</th><th>Pit Stops</th></tr>
                </thead>
                <tbody>
                  {standings.map(s => {
                    const gap = s.fastest_lap_ms && fastestOverall ? s.fastest_lap_ms - fastestOverall : null;
                    return (
                      <tr key={s.driver_id}>
                        <td><span className={`pos-badge${s.position<=3?` p${s.position}`:''}`}>{s.position}</span></td>
                        <td><div style={{display:'flex',alignItems:'center',gap:6}}>
                          <div style={{width:3,height:18,borderRadius:2,background:s.team_color||teamColor(s.team)}} />
                          <span style={{fontWeight:700,color:'var(--text-primary)'}}>{s.driver_code}</span>
                        </div></td>
                        <td style={{color:'var(--text-muted)',fontSize:10}}>{s.team}</td>
                        <td style={{fontFamily:'monospace',color:'#c084fc',fontWeight:600}}>{msToLapTime(s.fastest_lap_ms)}</td>
                        <td style={{fontFamily:'monospace',color:'var(--text-secondary)',fontSize:10}}>{msToLapTime(s.avg_lap_time_ms)}</td>
                        <td style={{fontFamily:'monospace',color: gap===0?'#34d399':'#f87171',fontSize:10}}>{gap===0?'—':gap?`+${gap}ms`:'—'}</td>
                        <td style={{textAlign:'right',color:'var(--text-muted)'}}>{s.total_laps}</td>
                        <td style={{textAlign:'right',color:'var(--text-muted)'}}>{s.pit_stop_count}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
