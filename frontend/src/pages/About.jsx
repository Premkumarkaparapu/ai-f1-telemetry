export default function About() {
  const stack = [
    { group: 'Data Pipeline', items: [['FastF1', 'Python library for F1 telemetry','#60a5fa'],['SQLite', 'Embedded database — 1M+ telemetry points','#34d399'],['Pandas', '5Hz downsampling & feature engineering','#fbbf24']] },
    { group: 'Machine Learning', items: [['XGBoost', 'Lap time predictor (R²=0.922)','#c084fc'],['Ridge Regression', 'Per-compound tyre degradation curves','#f87171'],['scikit-learn', 'Feature engineering & model pipeline','#fb923c']] },
    { group: 'Backend API', items: [['FastAPI', 'REST API with 20+ endpoints','#e8002d'],['SQLAlchemy', 'ORM for database access','#60a5fa'],['Pydantic', 'Request/response validation','#34d399']] },
    { group: 'Frontend', items: [['React + Vite', 'Component-based UI with HMR','#60a5fa'],['Recharts', 'Telemetry & strategy charts','#c084fc'],['CSS Design System', 'Custom dark F1 theme','#e8002d']] },
  ];

  const endpoints = [
    ['GET', '/api/v1/sessions/', 'List all sessions'],
    ['GET', '/api/v1/drivers/', 'Drivers for a session'],
    ['GET', '/api/v1/laps/', 'Lap times for a driver'],
    ['GET', '/api/v1/telemetry/{lap_id}', 'Raw telemetry points'],
    ['GET', '/api/v1/sessions/{id}/standings', 'Race standings'],
    ['GET', '/api/v1/sessions/{id}/weather', 'Weather data'],
    ['GET', '/api/v1/laps/stints/', 'Tyre stint breakdown'],
    ['GET', '/api/v1/laps/pitstops/', 'Pit stop records'],
    ['POST', '/api/v1/predict/', 'ML lap time prediction'],
    ['POST', '/api/v1/predict/strategy', 'Race strategy simulation'],
    ['GET', '/api/v1/predict/degradation/{compound}', 'Tyre degradation curve'],
    ['GET', '/api/v1/predict/pit-window/{session}/{driver}', 'Optimal pit window'],
  ];

  return (
    <div className="content-area">
      <div className="page-header">
        <div><div className="page-title">ℹ️ About Platform</div><div className="page-desc">AI-powered F1 Telemetry & Strategy Analysis Platform</div></div>
        <a href="https://github.com/Premkumarkaparapu/ai-f1-telemetry" target="_blank" rel="noreferrer"
          style={{ padding:'6px 14px', borderRadius:4, border:'1px solid rgba(48,54,61,0.8)', background:'rgba(22,27,34,0.8)',
            color:'var(--text-primary)', textDecoration:'none', fontSize:11, fontWeight:600, display:'flex', alignItems:'center', gap:6 }}>
          ⭐ GitHub
        </a>
      </div>

      {/* Hero */}
      <div className="card" style={{ marginBottom:10, borderColor:'rgba(232,0,45,0.2)', background:'linear-gradient(135deg, rgba(232,0,45,0.06) 0%, rgba(22,27,34,0) 100%)' }}>
        <div className="card-body" style={{ padding:'24px 20px' }}>
          <div style={{ display:'flex', alignItems:'center', gap:16, marginBottom:16 }}>
            <div style={{ width:48, height:32, background:'#e8002d', borderRadius:4, display:'flex', alignItems:'center', justifyContent:'center',
              fontFamily:'Arial Black', fontWeight:900, color:'white', fontSize:20 }}>F1</div>
            <div>
              <div style={{ fontSize:20, fontWeight:800, color:'var(--text-primary)' }}>F1 Telemetry & Strategy Platform</div>
              <div style={{ fontSize:12, color:'var(--text-muted)', marginTop:2 }}>Production-grade real-time analytics for Formula 1 data</div>
            </div>
          </div>
          <p style={{ fontSize:12, color:'var(--text-secondary)', lineHeight:1.7, maxWidth:700 }}>
            Built to showcase engineering skills applicable to an F1 team environment. Ingests real FastF1 telemetry data, 
            runs ML models for lap time prediction and tyre degradation analysis, and provides a fully interactive 
            strategy simulation tool — all backed by a production FastAPI backend with 20+ REST endpoints.
          </p>
          <div style={{ display:'flex', gap:16, marginTop:16, flexWrap:'wrap' }}>
            {[['R² = 0.922', 'ML Accuracy', '#c084fc'], ['5Hz', 'Telemetry Rate', '#60a5fa'], ['20+', 'API Endpoints', '#34d399'], ['417 pts/lap', 'Data Density', '#fbbf24']].map(([val, label, color]) => (
              <div key={label} style={{ textAlign:'center', padding:'10px 16px', background:'rgba(22,27,34,0.5)', borderRadius:6, border:`1px solid ${color}22` }}>
                <div style={{ fontSize:22, fontWeight:900, color, fontFamily:'monospace' }}>{val}</div>
                <div style={{ fontSize:9, color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.05em', marginTop:2 }}>{label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Tech Stack */}
      <div className="grid-2" style={{ marginBottom:10 }}>
        {stack.map(({ group, items }) => (
          <div key={group} className="card">
            <div className="card-header"><span className="card-title">{group}</span></div>
            <div className="card-body">
              {items.map(([name, desc, color]) => (
                <div key={name} style={{ display:'flex', gap:10, marginBottom:10, alignItems:'flex-start' }}>
                  <div style={{ width:3, height:36, borderRadius:2, background:color, flexShrink:0, marginTop:2 }} />
                  <div>
                    <div style={{ fontSize:12, fontWeight:700, color }}>{name}</div>
                    <div style={{ fontSize:10, color:'var(--text-muted)', marginTop:1 }}>{desc}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* API Endpoints */}
      <div className="card" style={{ marginBottom:10 }}>
        <div className="card-header">
          <span className="card-title">API Endpoints</span>
          <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer"
            style={{ fontSize:10, color:'#60a5fa', textDecoration:'none', fontWeight:600 }}>📄 Swagger UI →</a>
        </div>
        <div className="card-body" style={{ padding:0 }}>
          <table className="standings-table" style={{ width:'100%' }}>
            <thead><tr><th>Method</th><th>Endpoint</th><th>Description</th></tr></thead>
            <tbody>
              {endpoints.map(([method, path, desc]) => (
                <tr key={path}>
                  <td><span style={{ padding:'2px 8px', borderRadius:10, fontSize:9, fontWeight:700,
                    background: method==='GET' ? 'rgba(52,211,153,0.15)' : 'rgba(232,0,45,0.15)',
                    color: method==='GET' ? '#34d399' : '#e8002d', border:`1px solid ${method==='GET'?'rgba(52,211,153,0.3)':'rgba(232,0,45,0.3)'}` }}>
                    {method}
                  </span></td>
                  <td style={{ fontFamily:'monospace', fontSize:10, color:'var(--text-secondary)' }}>{path}</td>
                  <td style={{ fontSize:10, color:'var(--text-muted)' }}>{desc}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Architecture */}
      <div className="card">
        <div className="card-header"><span className="card-title">Architecture Overview</span></div>
        <div className="card-body">
          <div style={{ display:'flex', gap:0, alignItems:'center', flexWrap:'wrap', justifyContent:'center' }}>
            {[
              ['🏎️', 'FastF1 API', 'Real F1 data', '#60a5fa'],
              ['→','','','#6e7681'],
              ['⚙️', 'Data Pipeline', 'Transform + Load', '#fbbf24'],
              ['→','','','#6e7681'],
              ['🗄️', 'SQLite DB', '1M+ telemetry rows', '#34d399'],
              ['→','','','#6e7681'],
              ['🤖', 'ML Models', 'XGBoost + Ridge', '#c084fc'],
              ['→','','','#6e7681'],
              ['⚡', 'FastAPI', '20+ REST endpoints', '#e8002d'],
              ['→','','','#6e7681'],
              ['🌐', 'React UI', 'This dashboard', '#60a5fa'],
            ].map((item, i) => item[0]==='→'
              ? <span key={i} style={{ fontSize:18, color:'var(--text-muted)', margin:'0 4px' }}>→</span>
              : (
                <div key={i} style={{ textAlign:'center', padding:'12px 14px', background:'rgba(22,27,34,0.6)',
                  borderRadius:6, border:`1px solid ${item[3]}22`, minWidth:100 }}>
                  <div style={{ fontSize:24, marginBottom:4 }}>{item[0]}</div>
                  <div style={{ fontSize:11, fontWeight:700, color:item[3] }}>{item[1]}</div>
                  <div style={{ fontSize:9, color:'var(--text-muted)', marginTop:2 }}>{item[2]}</div>
                </div>
              )
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
