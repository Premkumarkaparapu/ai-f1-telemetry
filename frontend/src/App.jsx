import { useState, useRef, useEffect } from 'react';
import { AuthProvider, useAuth } from './AuthContext.jsx';
import AuthModal, { ProfileEditModal } from './components/AuthModal.jsx';
import Dashboard from './pages/Dashboard';
import Sessions from './pages/Sessions';
import Drivers from './pages/Drivers';
import Laps from './pages/Laps';
import TelemetryPage from './pages/TelemetryPage';
import Weather from './pages/Weather';
import Stints from './pages/Stints';
import PitStops from './pages/PitStops';
import LapComparison from './pages/LapComparison';
import DriverPerformance from './pages/DriverPerformance';
import Degradation from './pages/Degradation';
import LiveReplay from './pages/LiveReplay';
import StrategySimulator from './pages/StrategySimulator';
import About from './pages/About';

// ── Icons ─────────────────────────────────────────────────────────────────────
const Icon = ({ d, size = 13 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d={d} />
  </svg>
);

const ICONS = {
  dashboard:   'M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z M9 22V12h6v10',
  sessions:    'M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01',
  drivers:     'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2 M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M23 21v-2a4 4 0 0 0-3-3.87 M16 3.13a4 4 0 0 1 0 7.75',
  laps:        'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z',
  telemetry:   'M22 12h-4l-3 9L9 3l-3 9H2',
  weather:     'M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z',
  stints:      'M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5',
  pitstops:    'M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z',
  compare:     'M9 3H5a2 2 0 0 0-2 2v4m6-6h10a2 2 0 0 1 2 2v4M9 3v18m0 0h10a2 2 0 0 0 2-2V9M9 21H5a2 2 0 0 0-2-2V9m0 0h18',
  performance: 'M18 20V10 M12 20V4 M6 20v-6',
  tyre:        'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm0 6a4 4 0 1 0 0 8 4 4 0 0 0 0-8z',
  prediction:  'M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z',
  strategy:    'M1 6v16l7-4 8 4 7-4V2l-7 4-8-4-7 4z M8 2v16 M16 6v16',
  about:       'M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z M12 8h.01 M11 12h1v4h1',
  user:        'M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2 M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z',
  logout:      'M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4 M16 17l5-5-5-5 M21 12H9',
  login:       'M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4 M10 17l5-5-5-5 M15 12H3',
  edit:        'M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7 M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z',
  docs:        'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M16 13H8 M16 17H8 M10 9H8',
  github:      'M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22',
};

const NAV = [
  { section: 'DATA' },
  { id: 'dashboard',    label: 'Dashboard',          icon: 'dashboard' },
  { id: 'sessions',     label: 'Sessions',            icon: 'sessions' },
  { id: 'drivers',      label: 'Drivers',             icon: 'drivers' },
  { id: 'laps',         label: 'Laps',                icon: 'laps' },
  { id: 'telemetry',    label: 'Telemetry',           icon: 'telemetry' },
  { id: 'weather',      label: 'Weather',             icon: 'weather' },
  { id: 'stints',       label: 'Stints',              icon: 'stints' },
  { id: 'pitstops',     label: 'Pit Stops',           icon: 'pitstops' },
  { section: 'ANALYTICS' },
  { id: 'compare',      label: 'Compare Laps',        icon: 'compare' },
  { id: 'performance',  label: 'Driver Performance',  icon: 'performance' },
  { id: 'tyreanalysis', label: 'Tyre Analysis',       icon: 'tyre' },
  { section: 'PREDICTIONS' },
  { id: 'prediction',   label: 'Lap Time Prediction', icon: 'prediction' },
  { id: 'strategy',     label: 'Strategy Simulator',  icon: 'strategy' },
  { section: 'ABOUT' },
  { id: 'about', label: 'Platform Internals', icon: 'about', private: true },
];

function PageContent({ page, navigate, onLoginClick }) {
  const { user } = useAuth();

  // Private pages: only accessible when logged in
  if (page === 'about' && !user) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        height: '100%', minHeight: 480, gap: 20, padding: 40,
      }}>
        <div style={{
          width: 72, height: 72, borderRadius: '50%',
          background: 'linear-gradient(135deg, rgba(232,0,45,0.15), rgba(112,184,255,0.1))',
          border: '2px solid rgba(232,0,45,0.3)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 30, boxShadow: '0 0 40px rgba(232,0,45,0.2)',
        }}>🔒</div>
        <div style={{ textAlign: 'center', maxWidth: 360 }}>
          <div style={{ fontSize: 20, fontWeight: 800, color: 'var(--text-primary)', marginBottom: 8 }}>
            Members Only
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.6 }}>
            Platform internals, engineering notes, and model accuracy details
            are restricted to registered users.
          </div>
        </div>
        <button
          onClick={() => onLoginClick('login')}
          style={{
            padding: '10px 28px', borderRadius: 8, border: 'none', cursor: 'pointer',
            background: 'linear-gradient(135deg, #e8002d, #b00020)',
            color: '#fff', fontWeight: 700, fontSize: 13, fontFamily: 'inherit',
            boxShadow: '0 4px 20px rgba(232,0,45,0.35)',
            transition: 'all 0.2s',
          }}>
          Sign In to Access
        </button>
        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          Don't have an account?&nbsp;
          <span
            onClick={() => onLoginClick('register')}
            style={{ color: '#70b8ff', cursor: 'pointer', textDecoration: 'underline' }}>
            Register free
          </span>
        </div>
      </div>
    );
  }

  switch (page) {
    case 'dashboard':    return <Dashboard />;
    case 'sessions':     return <Sessions onNavigate={navigate} />;
    case 'drivers':      return <Drivers />;
    case 'laps':         return <Laps />;
    case 'telemetry':    return <TelemetryPage />;
    case 'weather':      return <Weather />;
    case 'stints':       return <Stints />;
    case 'pitstops':     return <PitStops />;
    case 'compare':      return <LapComparison />;
    case 'performance':  return <DriverPerformance />;
    case 'tyreanalysis': return <Degradation />;
    case 'prediction':   return <LiveReplay />;
    case 'strategy':     return <StrategySimulator />;
    case 'about':        return <About />;
    default:             return <Dashboard />;
  }
}

// ── Profile Avatar Button ──────────────────────────────────────────────────────
function ProfileButton({ onLoginClick }) {
  const { user, logout } = useAuth();
  const [open, setOpen]           = useState(false);
  const [showEdit, setShowEdit]   = useState(false);
  const menuRef = useRef(null);

  // Close when clicking outside
  useEffect(() => {
    function handle(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, []);

  const initials    = user?.avatar_initials || (user ? user.username.slice(0, 2).toUpperCase() : '?');
  const avatarColor = user?.avatar_color || '#e8002d';

  return (
    <>
      <div ref={menuRef} style={{ position: 'relative' }}>
        {/* Avatar circle */}
        <button
          onClick={() => setOpen(o => !o)}
          title={user ? user.username : 'Login / Register'}
          style={{
            width: 32, height: 32, borderRadius: '50%', border: 'none', cursor: 'pointer',
            background: user
              ? `linear-gradient(135deg, ${avatarColor}, ${avatarColor}bb)`
              : 'linear-gradient(135deg, #374151, #1f2937)',
            color: '#fff', fontSize: 11, fontWeight: 800, fontFamily: 'inherit',
            boxShadow: user ? `0 0 12px ${avatarColor}60` : 'none',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'all 0.2s',
            outline: open ? `2px solid ${avatarColor}` : '2px solid transparent',
          }}>
          {initials}
        </button>

        {/* Dropdown menu */}
        {open && (
          <div style={{
            position: 'absolute', right: 0, top: 38,
            background: 'var(--bg-card)', border: '1px solid var(--border)',
            borderRadius: 10, boxShadow: '0 16px 40px rgba(0,0,0,0.5)',
            minWidth: 220, zIndex: 999, overflow: 'hidden',
            animation: 'fadeDown 0.15s ease',
          }}>
            {/* Header */}
            <div style={{
              padding: '14px 16px', borderBottom: '1px solid var(--border)',
              background: user ? `linear-gradient(135deg, ${avatarColor}18, transparent)` : 'rgba(232,0,45,0.04)',
            }}>
              {user ? (
                <>
                  <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
                    {user.full_name || user.username}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                    {user.email}
                  </div>
                  {user.team_affiliation && user.team_affiliation !== 'Other / No Team' && (
                    <div style={{
                      display: 'inline-block', marginTop: 6,
                      fontSize: 9, fontWeight: 700, letterSpacing: '0.5px',
                      color: avatarColor, background: `${avatarColor}18`,
                      border: `1px solid ${avatarColor}40`, borderRadius: 10,
                      padding: '2px 8px', textTransform: 'uppercase',
                    }}>
                      {user.team_affiliation}
                    </div>
                  )}
                </>
              ) : (
                <>
                  <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>Guest User</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                    Login to save preferences
                  </div>
                </>
              )}
            </div>

            {/* Menu items */}
            {user ? (
              <>
                <MenuItem icon={ICONS.edit} label="Edit Profile" onClick={() => { setOpen(false); setShowEdit(true); }} />
                <div style={{ height: 1, background: 'var(--border)', margin: '4px 0' }} />
                <MenuItem icon={ICONS.docs}   label="API Documentation" href="http://localhost:8000/docs" />
                <MenuItem icon={ICONS.github}  label="GitHub Repository"  href="https://github.com/Premkumarkaparapu/ai-f1-telemetry" />
                <MenuItem icon={ICONS.about}   label="Backend Health"     href="http://localhost:8000/health" />
                <div style={{ height: 1, background: 'var(--border)', margin: '4px 0' }} />
                <MenuItem icon={ICONS.logout} label="Sign Out" onClick={() => { logout(); setOpen(false); }} danger />
              </>
            ) : (
              <>
                <MenuItem icon={ICONS.login} label="Login to your account" onClick={() => { setOpen(false); onLoginClick(); }} />
                <MenuItem icon={ICONS.user}  label="Create free account"   onClick={() => { setOpen(false); onLoginClick('register'); }} />
                <div style={{ height: 1, background: 'var(--border)', margin: '4px 0' }} />
                <MenuItem icon={ICONS.docs}   label="API Documentation" href="http://localhost:8000/docs" />
                <MenuItem icon={ICONS.github}  label="GitHub Repository"  href="https://github.com/Premkumarkaparapu/ai-f1-telemetry" />
              </>
            )}
          </div>
        )}
      </div>

      {/* Edit profile modal */}
      {showEdit && user && (
        <ProfileEditModal user={user} onClose={() => setShowEdit(false)} />
      )}
    </>
  );
}

function MenuItem({ icon, label, onClick, href, danger }) {
  const base = {
    display: 'flex', alignItems: 'center', gap: 9, padding: '9px 16px',
    color: danger ? '#ff6b6b' : 'var(--text-secondary)', textDecoration: 'none',
    fontSize: 12, fontWeight: 500, width: '100%', border: 'none',
    background: 'transparent', cursor: 'pointer', fontFamily: 'inherit',
    transition: 'background 0.1s', textAlign: 'left',
  };
  const hoverBg = danger ? 'rgba(239,68,68,0.06)' : 'rgba(255,255,255,0.04)';

  const inner = (
    <>
      <svg width={12} height={12} viewBox="0 0 24 24" fill="none" stroke="currentColor"
        strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
        <path d={icon} />
      </svg>
      {label}
    </>
  );

  if (href) return (
    <a href={href} target="_blank" rel="noreferrer" style={base}
      onMouseEnter={e => e.currentTarget.style.background = hoverBg}
      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
      {inner}
    </a>
  );

  return (
    <button onClick={onClick} style={base}
      onMouseEnter={e => e.currentTarget.style.background = hoverBg}
      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
      {inner}
    </button>
  );
}

// ── Main App Shell ─────────────────────────────────────────────────────────────
function AppShell() {
  const [page, setPage]         = useState('dashboard');
  const [authTab, setAuthTab]   = useState(null);   // null | 'login' | 'register'
  const { user }                = useAuth();

  function openAuth(tab = 'login') { setAuthTab(tab); }

  return (
    <div className="app-shell">
      {/* ── Sidebar ── */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <svg width="24" height="16" viewBox="0 0 60 40">
            <rect width="60" height="40" rx="3" fill="#e8002d" />
            <text x="30" y="28" textAnchor="middle" fill="white"
              fontFamily="Arial Black,Arial" fontWeight="900" fontSize="22">F1</text>
          </svg>
          <span className="sidebar-logo-text">F1 Telemetry<br />&amp; Strategy</span>
        </div>

        {/* User badge in sidebar */}
        {user && (
          <div style={{
            margin: '0 10px 8px', padding: '8px 10px', borderRadius: 8,
            background: `${user.avatar_color || '#e8002d'}14`,
            border: `1px solid ${user.avatar_color || '#e8002d'}30`,
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <div style={{
              width: 26, height: 26, borderRadius: '50%', flexShrink: 0,
              background: `linear-gradient(135deg, ${user.avatar_color || '#e8002d'}, ${user.avatar_color || '#e8002d'}88)`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 9, fontWeight: 800, color: '#fff',
            }}>
              {user.avatar_initials || user.username.slice(0, 2).toUpperCase()}
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {user.full_name || user.username}
              </div>
              {user.team_affiliation && user.team_affiliation !== 'Other / No Team' && (
                <div style={{ fontSize: 9, color: user.avatar_color || '#e8002d', fontWeight: 600, marginTop: 1 }}>
                  {user.team_affiliation}
                </div>
              )}
            </div>
          </div>
        )}

        <nav className="sidebar-nav">
          {NAV.map((item, i) => {
            // Hide private nav items from guests
            if (item.private && !user) return null;
            return item.section
              ? <div key={i} className="sidebar-section-label">{item.section}</div>
              : (
                <button key={item.id}
                  className={`nav-item${page === item.id ? ' active' : ''}`}
                  onClick={() => setPage(item.id)}>
                  <Icon d={ICONS[item.icon]} size={13} />
                  {item.label}
                  {item.private && <span style={{ marginLeft: 'auto', fontSize: 9, opacity: 0.6 }}>🔒</span>}
                </button>
              );
          })}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-version">v1.0.0</div>
        </div>
      </aside>

      {/* ── Main ── */}
      <div className="main-area">
        <header className="top-header">
          <div className="top-header-title">
            <svg width="28" height="18" viewBox="0 0 60 38" style={{ flexShrink: 0 }}>
              <rect width="60" height="38" rx="4" fill="#e8002d" />
              <text x="30" y="27" textAnchor="middle" fill="white"
                fontFamily="Arial Black, Arial" fontWeight="900" fontSize="22">F1</text>
            </svg>
            <span style={{ fontSize: 13, fontWeight: 700, letterSpacing: '-0.2px' }}>F1 Telemetry &amp; Strategy Platform</span>
            <span style={{ fontSize: 10, color: 'var(--text-muted)', background: 'rgba(232,0,45,0.12)', border: '1px solid rgba(232,0,45,0.25)', borderRadius: 10, padding: '1px 7px', marginLeft: 4 }}>2026</span>
          </div>

          <div className="top-header-actions">
            {/* API Live status */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '4px 10px', borderRadius: 20,
              background: 'rgba(52,211,153,0.1)', border: '1px solid rgba(52,211,153,0.25)' }}>
              <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#34d399',
                boxShadow: '0 0 6px #34d399', animation: 'pulse 2s infinite' }} />
              <span style={{ fontSize: 10, color: '#34d399', fontWeight: 600 }}>API Live</span>
            </div>

            {/* API Docs */}
            <a className="header-btn" href="http://localhost:8000/docs" target="_blank" rel="noreferrer">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
              </svg>
              API Docs
            </a>

            {/* GitHub */}
            <a className="header-btn" href="https://github.com/Premkumarkaparapu/ai-f1-telemetry" target="_blank" rel="noreferrer">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z" />
              </svg>
              GitHub
            </a>

            {/* Profile / Auth button */}
            <ProfileButton onLoginClick={openAuth} />
          </div>
        </header>

        <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <PageContent page={page} navigate={(p) => setPage(p)} onLoginClick={openAuth} />
        </div>

        <footer className="page-footer">
          <span>Data provided by FastF1 &nbsp;|&nbsp; 2024–2025 Formula 1 Season</span>
          <span>Built for Williams F1 Early Career Programme 🏎️</span>
        </footer>
      </div>

      {/* ── Auth Modal ── */}
      {authTab && (
        <AuthModal
          initialTab={authTab}
          onClose={() => setAuthTab(null)}
        />
      )}

      <style>{`
        @keyframes fadeDown {
          from { opacity: 0; transform: translateY(-6px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}

// ── Root export with AuthProvider wrapper ─────────────────────────────────────
export default function App() {
  return (
    <AuthProvider>
      <AppShell />
    </AuthProvider>
  );
}
