import { useState, useEffect } from 'react';
import { api } from '../api.js';

// Real API fields: session_id, year, event_name, session_type, track, country, total_laps, created_at

const TYPE_LABEL = { R: 'Race', Q: 'Qualifying', FP1: 'Practice 1', FP2: 'Practice 2', FP3: 'Practice 3', S: 'Sprint' };
const TYPE_COLOR = { R: '#e8002d', Q: '#fbbf24', FP1: '#60a5fa', FP2: '#60a5fa', FP3: '#60a5fa', S: '#c084fc' };
const FLAG = { Bahrain: '🇧🇭', Saudi: '🇸🇦', Australia: '🇦🇺', Japan: '🇯🇵', China: '🇨🇳', Miami: '🇺🇸', Monaco: '🇲🇨', Canada: '🇨🇦', Spain: '🇪🇸', Austria: '🇦🇹', Britain: '🇬🇧', Hungary: '🇭🇺', Belgium: '🇧🇪', Netherlands: '🇳🇱', Italy: '🇮🇹', Singapore: '🇸🇬', Qatar: '🇶🇦', United: '🇺🇸', Mexico: '🇲🇽', Brazil: '🇧🇷', Abu: '🇦🇪' };

function getFlag(eventName) {
  if (!eventName) return '🏁';
  const first = eventName.split(' ')[0];
  return FLAG[first] || '🏁';
}

export default function Sessions({ onNavigate }) {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    api.getSessions()
      .then(d => { setSessions(d); setLoading(false); if (d.length) setSelected(d[0].session_id); })
      .catch(() => setLoading(false));
  }, []);

  const sel = sessions.find(s => s.session_id === selected);

  return (
    <div className="content-area">
      <div className="page-header">
        <div>
          <div className="page-title">Sessions</div>
          <div className="page-desc">All loaded F1 sessions — click a row to view details, double-click to open in Dashboard</div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ fontSize: 11, color: 'var(--text-muted)', background: 'var(--bg-card)', padding: '4px 10px', borderRadius: 12, border: '1px solid var(--border)' }}>
            {sessions.length} session{sessions.length !== 1 ? 's' : ''} in DB
          </span>
        </div>
      </div>

      {loading && <div className="loading-state"><div className="spinner" /><span>Loading sessions...</span></div>}

      {!loading && (
        <div className="grid-2" style={{ gap: 10, alignItems: 'start' }}>
          {/* Session list */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">Loaded Sessions</span>
            </div>
            <div style={{ overflowY: 'auto', maxHeight: 420 }}>
              {sessions.length === 0 && (
                <div className="empty-state" style={{ height: 160 }}>
                  <span style={{ fontSize: 36 }}>📭</span>
                  <span>No sessions in database</span>
                  <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>Run the data pipeline to load a session</span>
                </div>
              )}
              {sessions.map(s => {
                const color = TYPE_COLOR[s.session_type] || '#8b949e';
                const isSelected = selected === s.session_id;
                return (
                  <div key={s.session_id}
                    onClick={() => setSelected(s.session_id)}
                    onDoubleClick={() => onNavigate && onNavigate('dashboard')}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px',
                      cursor: 'pointer', borderBottom: '1px solid var(--border)',
                      background: isSelected ? 'rgba(232,0,45,0.06)' : 'transparent',
                      borderLeft: isSelected ? '3px solid var(--f1-red)' : '3px solid transparent',
                      transition: 'all 0.15s',
                    }}>
                    <div style={{ fontSize: 24, flexShrink: 0 }}>{getFlag(s.event_name)}</div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 700, color: isSelected ? 'var(--text-primary)' : 'var(--text-secondary)', marginBottom: 2 }}>{s.event_name}</div>
                      <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{s.track} · {s.country} · {s.year}</div>
                    </div>
                    <span style={{
                      padding: '2px 8px', borderRadius: 10, fontSize: 10, fontWeight: 700, flexShrink: 0,
                      background: `${color}22`, color, border: `1px solid ${color}44`
                    }}>
                      {TYPE_LABEL[s.session_type] || s.session_type}
                    </span>
                    <span style={{ fontSize: 10, fontFamily: 'monospace', color: 'var(--text-muted)', flexShrink: 0 }}>{s.total_laps ?? '—'} laps</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Session detail */}
          <div>
            {sel ? (
              <>
                <div className="card" style={{ marginBottom: 10, borderColor: `${TYPE_COLOR[sel.session_type] || '#888'}33`, background: `linear-gradient(135deg, ${TYPE_COLOR[sel.session_type] || '#888'}08 0%, transparent 60%)` }}>
                  <div className="card-body">
                    <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start', marginBottom: 16 }}>
                      <div style={{ fontSize: 48 }}>{getFlag(sel.event_name)}</div>
                      <div>
                        <div style={{ fontSize: 20, fontWeight: 800, color: 'var(--text-primary)', lineHeight: 1.2 }}>{sel.event_name}</div>
                        <div style={{ fontSize: 12, color: TYPE_COLOR[sel.session_type] || '#888', fontWeight: 600, marginTop: 4 }}>
                          {TYPE_LABEL[sel.session_type] || sel.session_type} · {sel.year}
                        </div>
                      </div>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                      {[
                        ['Circuit', sel.track || '—'],
                        ['Country', sel.country || '—'],
                        ['Season', sel.year],
                        ['Total Laps', sel.total_laps ?? '—'],
                        ['Session Type', TYPE_LABEL[sel.session_type] || sel.session_type],
                        ['Loaded', sel.created_at ? new Date(sel.created_at).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'],
                      ].map(([k, v]) => (
                        <div key={k} style={{ background: 'rgba(22,27,34,0.6)', borderRadius: 6, padding: '8px 12px', border: '1px solid var(--border)' }}>
                          <div style={{ fontSize: 9, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{k}</div>
                          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginTop: 2 }}>{String(v)}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <button className="btn btn-primary" style={{ width: '100%', justifyContent: 'center', padding: '10px', fontSize: 13 }}
                  onClick={() => onNavigate && onNavigate('dashboard')}>
                  Open in Dashboard →
                </button>
              </>
            ) : (
              <div className="card">
                <div className="empty-state" style={{ height: 200 }}>
                  <span style={{ fontSize: 36 }}>👆</span>
                  <span>Click a session to see details</span>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Load new session guide */}
      <div className="card" style={{ marginTop: 10, borderColor: 'rgba(232,0,45,0.2)', background: 'rgba(232,0,45,0.03)' }}>
        <div className="card-header">
          <span className="card-title">Load More Sessions</span>
        </div>
        <div className="card-body">
          <p style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 10 }}>
            Use the data pipeline to load additional F1 sessions. Replace the event name with any 2024 Grand Prix.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {[
              ['Race',       'python -m data_pipeline.ingest --year 2024 --event "Monaco Grand Prix" --type R'],
              ['Qualifying', 'python -m data_pipeline.ingest --year 2024 --event "Monaco Grand Prix" --type Q'],
              ['Practice 1', 'python -m data_pipeline.ingest --year 2024 --event "Monaco Grand Prix" --type FP1'],
            ].map(([label, cmd]) => (
              <div key={label} style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                <span style={{ fontSize: 10, color: TYPE_COLOR[label[0]] || '#8b949e', fontWeight: 600, minWidth: 64 }}>{label}</span>
                <code style={{ flex: 1, background: 'rgba(22,27,34,0.8)', padding: '5px 10px', borderRadius: 4, fontSize: 10, color: 'var(--text-primary)', border: '1px solid var(--border)', fontFamily: 'var(--font-mono)', overflowX: 'auto' }}>
                  {cmd}
                </code>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
