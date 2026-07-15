import { useState, useEffect } from 'react';
import { useAuth } from '../AuthContext.jsx';
import { api } from '../api.js';

const F1_TEAMS = [
  "Red Bull Racing","Ferrari","Mercedes","McLaren","Aston Martin",
  "Alpine","Williams","RB (Racing Bulls)","Haas","Sauber/Audi","Other / No Team",
];

const AVATAR_COLORS = [
  "#e8002d","#1e41ff","#27f4d2","#ff8000","#006f62",
  "#0093cc","#005aff","#b6babd","#9b59b6","#52e252",
];

function getInitials(fullName, username) {
  if (fullName) {
    const parts = fullName.trim().split(' ');
    if (parts.length >= 2) return (parts[0][0] + parts[parts.length-1][0]).toUpperCase();
    return parts[0].slice(0,2).toUpperCase();
  }
  return (username || 'F1').slice(0,2).toUpperCase();
}

export default function AuthModal({ onClose, initialTab = 'login' }) {
  const { login, register } = useAuth();
  const [tab, setTab]         = useState(initialTab); // 'login' | 'register'
  const [step, setStep]       = useState(1);          // register has 2 steps
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');

  // Login form
  const [loginEmail, setLoginEmail]   = useState('');
  const [loginPass,  setLoginPass]    = useState('');

  // Register form
  const [reg, setReg] = useState({
    username: '', email: '', password: '', confirmPass: '',
    full_name: '', team_affiliation: 'Other / No Team',
    bio: '', avatar_color: '#e8002d',
  });

  function updateReg(field, val) {
    setReg(prev => ({ ...prev, [field]: val }));
    setError('');
  }

  // ── Login submit ────────────────────────────────────────────────────────────
  async function handleLogin(e) {
    e.preventDefault();
    setError('');
    if (!loginEmail || !loginPass) { setError('Please fill in all fields'); return; }
    setLoading(true);
    try {
      await login(loginEmail, loginPass);
      onClose();
    } catch (err) {
      setError(err.message.includes('401') ? 'Invalid email or password' : err.message);
    } finally {
      setLoading(false);
    }
  }

  // ── Register step 1 validation ─────────────────────────────────────────────
  function validateStep1() {
    if (!reg.username || reg.username.length < 3) { setError('Username must be at least 3 characters'); return false; }
    if (!reg.email || !reg.email.includes('@'))   { setError('Please enter a valid email'); return false; }
    if (!reg.password || reg.password.length < 8) { setError('Password must be at least 8 characters'); return false; }
    if (reg.password !== reg.confirmPass)          { setError('Passwords do not match'); return false; }
    return true;
  }

  // ── Register submit ─────────────────────────────────────────────────────────
  async function handleRegister(e) {
    e.preventDefault();
    setError('');
    if (step === 1) {
      if (!validateStep1()) return;
      setStep(2); return;
    }
    setLoading(true);
    try {
      await register({
        username:         reg.username,
        email:            reg.email,
        password:         reg.password,
        full_name:        reg.full_name || null,
        team_affiliation: reg.team_affiliation,
        bio:              reg.bio || null,
        avatar_color:     reg.avatar_color,
      });
      onClose();
    } catch (err) {
      const msg = err.message;
      if (msg.includes('Email already')) setError('This email is already registered');
      else if (msg.includes('Username already')) setError('This username is taken');
      else setError('Registration failed. Please try again.');
      setStep(1);
    } finally {
      setLoading(false);
    }
  }

  const initials = getInitials(reg.full_name, reg.username);

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9999,
      background: 'rgba(5,8,14,0.92)',
      backdropFilter: 'blur(16px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 16,
    }} onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>

      <div style={{
        width: '100%', maxWidth: 440,
        background: 'linear-gradient(145deg, #0f1923 0%, #0d1520 100%)',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: 16,
        boxShadow: '0 32px 80px rgba(0,0,0,0.7), 0 0 0 1px rgba(232,0,45,0.1)',
        overflow: 'hidden',
        animation: 'slideUp 0.25s ease',
      }}>

        {/* Header */}
        <div style={{
          padding: '28px 28px 20px',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          background: 'rgba(232,0,45,0.04)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
            <svg width="32" height="22" viewBox="0 0 60 40">
              <rect width="60" height="40" rx="4" fill="#e8002d"/>
              <text x="30" y="28" textAnchor="middle" fill="white"
                fontFamily="Arial Black,Arial" fontWeight="900" fontSize="22">F1</text>
            </svg>
            <div>
              <div style={{ fontSize: 16, fontWeight: 800, color: '#f0f4f8', letterSpacing: '-0.3px' }}>
                F1 Telemetry Platform
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>
                Race data & strategy analytics
              </div>
            </div>
          </div>

          {/* Tabs */}
          <div style={{ display: 'flex', gap: 4, background: 'rgba(255,255,255,0.04)', borderRadius: 8, padding: 3 }}>
            {['login','register'].map(t => (
              <button key={t} onClick={() => { setTab(t); setStep(1); setError(''); }}
                style={{
                  flex: 1, padding: '8px 0', border: 'none', borderRadius: 6, cursor: 'pointer',
                  fontSize: 13, fontWeight: 600, fontFamily: 'inherit', transition: 'all 0.15s',
                  background: tab === t ? 'rgba(232,0,45,0.9)' : 'transparent',
                  color: tab === t ? '#fff' : 'var(--text-muted)',
                }}>
                {t === 'login' ? 'Login' : 'Create Account'}
              </button>
            ))}
          </div>
        </div>

        {/* Body */}
        <div style={{ padding: 28 }}>

          {/* ── LOGIN ───────────────────────────────────────────────────── */}
          {tab === 'login' && (
            <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <Field label="Email" type="email" value={loginEmail}
                     onChange={e => setLoginEmail(e.target.value)} placeholder="your@email.com" />
              <Field label="Password" type="password" value={loginPass}
                     onChange={e => setLoginPass(e.target.value)} placeholder="••••••••" />
              {error && <ErrorBanner>{error}</ErrorBanner>}
              <SubmitBtn loading={loading}>Login to F1 Platform</SubmitBtn>
              <p style={{ textAlign: 'center', fontSize: 12, color: 'var(--text-muted)', margin: 0 }}>
                No account?{' '}
                <button type="button" onClick={() => { setTab('register'); setError(''); }}
                  style={{ background: 'none', border: 'none', color: '#e8002d', cursor: 'pointer', fontWeight: 600, fontSize: 12 }}>
                  Create one free →
                </button>
              </p>
            </form>
          )}

          {/* ── REGISTER STEP 1 ─────────────────────────────────────────── */}
          {tab === 'register' && step === 1 && (
            <form onSubmit={handleRegister} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <StepLabel step={1} label="Account credentials" />
              <Field label="Username" value={reg.username} onChange={e => updateReg('username', e.target.value)}
                     placeholder="e.g. verstappen1" />
              <Field label="Email" type="email" value={reg.email} onChange={e => updateReg('email', e.target.value)}
                     placeholder="your@email.com" />
              <Field label="Password" type="password" value={reg.password} onChange={e => updateReg('password', e.target.value)}
                     placeholder="At least 8 characters" />
              <Field label="Confirm Password" type="password" value={reg.confirmPass}
                     onChange={e => updateReg('confirmPass', e.target.value)} placeholder="Repeat password" />
              {error && <ErrorBanner>{error}</ErrorBanner>}
              <SubmitBtn loading={loading}>Continue →</SubmitBtn>
              <p style={{ textAlign: 'center', fontSize: 12, color: 'var(--text-muted)', margin: 0 }}>
                Already registered?{' '}
                <button type="button" onClick={() => { setTab('login'); setError(''); }}
                  style={{ background: 'none', border: 'none', color: '#e8002d', cursor: 'pointer', fontWeight: 600, fontSize: 12 }}>
                  Login →
                </button>
              </p>
            </form>
          )}

          {/* ── REGISTER STEP 2 ─────────────────────────────────────────── */}
          {tab === 'register' && step === 2 && (
            <form onSubmit={handleRegister} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <StepLabel step={2} label="Your F1 profile" />

              {/* Avatar Preview */}
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10, padding: '12px 0' }}>
                <div style={{
                  width: 60, height: 60, borderRadius: '50%',
                  background: `linear-gradient(135deg, ${reg.avatar_color}, ${reg.avatar_color}99)`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 20, fontWeight: 800, color: '#fff',
                  boxShadow: `0 0 20px ${reg.avatar_color}50`,
                  border: `2px solid ${reg.avatar_color}`,
                  transition: 'all 0.2s',
                }}>
                  {initials}
                </div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'center' }}>
                  {AVATAR_COLORS.map(c => (
                    <button key={c} type="button" onClick={() => updateReg('avatar_color', c)}
                      title={c}
                      style={{
                        width: 22, height: 22, borderRadius: '50%', background: c, cursor: 'pointer',
                        border: reg.avatar_color === c ? `2px solid #fff` : '2px solid transparent',
                        boxShadow: reg.avatar_color === c ? `0 0 8px ${c}` : 'none',
                        transition: 'all 0.15s',
                      }} />
                  ))}
                </div>
              </div>

              <Field label="Full Name (optional)" value={reg.full_name}
                     onChange={e => updateReg('full_name', e.target.value)} placeholder="Fernando Alonso" />

              {/* Team dropdown */}
              <div>
                <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', letterSpacing: '0.5px', textTransform: 'uppercase' }}>
                  Favourite F1 Team
                </label>
                <select value={reg.team_affiliation} onChange={e => updateReg('team_affiliation', e.target.value)}
                  style={{
                    marginTop: 6, width: '100%', background: '#0d1520',
                    border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, color: '#f0f4f8',
                    padding: '9px 12px', fontSize: 13, fontFamily: 'inherit', cursor: 'pointer',
                    colorScheme: 'dark',
                  }}>
                  {F1_TEAMS.map(t => <option key={t} value={t} style={{ background: '#0d1520', color: '#f0f4f8' }}>{t}</option>)}
                </select>
              </div>

              <Field label="Bio (optional)" value={reg.bio}
                     onChange={e => updateReg('bio', e.target.value)}
                     placeholder="F1 fan since 2000. Love Zandvoort…" multiline />

              {error && <ErrorBanner>{error}</ErrorBanner>}

              <div style={{ display: 'flex', gap: 8 }}>
                <button type="button" onClick={() => setStep(1)}
                  style={{
                    flex: '0 0 auto', padding: '10px 16px', border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: 8, background: 'transparent', color: 'var(--text-muted)',
                    cursor: 'pointer', fontFamily: 'inherit', fontSize: 13, fontWeight: 600,
                  }}>
                  ← Back
                </button>
                <SubmitBtn loading={loading} style={{ flex: 1 }}>Create My Account 🏎️</SubmitBtn>
              </div>
            </form>
          )}

        </div>

        {/* Footer */}
        <div style={{
          padding: '12px 28px 20px', textAlign: 'center',
          borderTop: '1px solid rgba(255,255,255,0.04)',
        }}>
          <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: 0 }}>
            Free account • No credit card required • Built for F1 fans 🏁
          </p>
        </div>
      </div>

      <style>{`
        @keyframes slideUp {
          from { transform: translateY(24px); opacity: 0; }
          to   { transform: translateY(0);    opacity: 1; }
        }
      `}</style>
    </div>
  );
}

// ── Reusable sub-components ────────────────────────────────────────────────────

function Field({ label, type = 'text', value, onChange, placeholder, multiline }) {
  const style = {
    marginTop: 6, width: '100%', background: 'rgba(255,255,255,0.04)',
    border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, color: '#f0f4f8',
    padding: '9px 12px', fontSize: 13, fontFamily: 'inherit', outline: 'none',
    boxSizing: 'border-box', transition: 'border-color 0.15s',
  };
  return (
    <div>
      <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', letterSpacing: '0.5px', textTransform: 'uppercase' }}>
        {label}
      </label>
      {multiline
        ? <textarea value={value} onChange={onChange} placeholder={placeholder} rows={2}
                    style={{ ...style, resize: 'vertical' }}
                    onFocus={e => e.target.style.borderColor = '#e8002d'}
                    onBlur={e  => e.target.style.borderColor = 'rgba(255,255,255,0.1)'} />
        : <input type={type} value={value} onChange={onChange} placeholder={placeholder}
                 style={style}
                 onFocus={e => e.target.style.borderColor = '#e8002d'}
                 onBlur={e  => e.target.style.borderColor = 'rgba(255,255,255,0.1)'} />
      }
    </div>
  );
}

function SubmitBtn({ children, loading, style: extraStyle }) {
  return (
    <button type="submit" disabled={loading}
      style={{
        padding: '11px 0', border: 'none', borderRadius: 8, cursor: loading ? 'not-allowed' : 'pointer',
        background: loading ? 'rgba(232,0,45,0.4)' : 'linear-gradient(135deg, #e8002d, #c00025)',
        color: '#fff', fontFamily: 'inherit', fontSize: 14, fontWeight: 700,
        letterSpacing: '0.2px', transition: 'all 0.15s',
        boxShadow: loading ? 'none' : '0 4px 16px rgba(232,0,45,0.3)',
        ...extraStyle,
      }}>
      {loading ? '⏳ Please wait…' : children}
    </button>
  );
}

function ErrorBanner({ children }) {
  return (
    <div style={{
      padding: '10px 14px', borderRadius: 8, fontSize: 13, fontWeight: 500,
      background: 'rgba(232,0,45,0.1)', border: '1px solid rgba(232,0,45,0.3)', color: '#ff6b6b',
    }}>
      ⚠️ {children}
    </div>
  );
}

function StepLabel({ step, label }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
      <div style={{
        width: 22, height: 22, borderRadius: '50%', background: '#e8002d',
        color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 11, fontWeight: 800, flexShrink: 0,
      }}>{step}</div>
      <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' }}>{label}</span>
    </div>
  );
}

// ── Profile Edit Modal ─────────────────────────────────────────────────────────

export function ProfileEditModal({ user, onClose }) {
  const { updateProfile } = useAuth();
  const [form, setForm] = useState({
    full_name:        user.full_name || '',
    team_affiliation: user.team_affiliation || 'Other / No Team',
    bio:              user.bio || '',
    avatar_color:     user.avatar_color || '#e8002d',
    avatar_initials:  user.avatar_initials || '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');
  const [saved,  setSaved]    = useState(false);

  function upd(field, val) { setForm(prev => ({ ...prev, [field]: val })); }

  const initials = form.avatar_initials || getInitials(form.full_name, user.username);

  async function handleSave(e) {
    e.preventDefault();
    setLoading(true); setError(''); setSaved(false);
    try {
      await updateProfile({ ...form, avatar_initials: initials });
      setSaved(true);
      setTimeout(onClose, 800);
    } catch (err) {
      setError('Failed to save. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9999,
      background: 'rgba(5,8,14,0.88)', backdropFilter: 'blur(12px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
    }} onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div style={{
        width: '100%', maxWidth: 420,
        background: 'linear-gradient(145deg, #0f1923 0%, #0d1520 100%)',
        border: '1px solid rgba(255,255,255,0.08)', borderRadius: 16,
        boxShadow: '0 32px 80px rgba(0,0,0,0.7)',
        animation: 'slideUp 0.25s ease',
      }}>
        <div style={{ padding: '24px 24px 20px', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 15, fontWeight: 700, color: '#f0f4f8' }}>Edit Profile</span>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 18 }}>×</button>
        </div>
        <form onSubmit={handleSave} style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 14 }}>
          {/* Avatar */}
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 56, height: 56, borderRadius: '50%',
              background: `linear-gradient(135deg, ${form.avatar_color}, ${form.avatar_color}99)`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 18, fontWeight: 800, color: '#fff',
              boxShadow: `0 0 20px ${form.avatar_color}50`,
              border: `2px solid ${form.avatar_color}`,
            }}>{initials}</div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'center' }}>
              {AVATAR_COLORS.map(c => (
                <button key={c} type="button" onClick={() => upd('avatar_color', c)}
                  style={{ width: 20, height: 20, borderRadius: '50%', background: c, cursor: 'pointer',
                    border: form.avatar_color === c ? '2px solid #fff' : '2px solid transparent',
                    boxShadow: form.avatar_color === c ? `0 0 6px ${c}` : 'none' }} />
              ))}
            </div>
          </div>

          <Field label="Full Name" value={form.full_name} onChange={e => upd('full_name', e.target.value)} placeholder="Your name" />
          <div>
            <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', letterSpacing: '0.5px', textTransform: 'uppercase' }}>Favourite Team</label>
            <select value={form.team_affiliation} onChange={e => upd('team_affiliation', e.target.value)}
              style={{ marginTop: 6, width: '100%', background: '#0d1520', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, color: '#f0f4f8', padding: '9px 12px', fontSize: 13, fontFamily: 'inherit', colorScheme: 'dark' }}>
              {F1_TEAMS.map(t => <option key={t} value={t} style={{ background: '#0d1520', color: '#f0f4f8' }}>{t}</option>)}
            </select>
          </div>
          <Field label="Bio" value={form.bio} onChange={e => upd('bio', e.target.value)} placeholder="F1 fan since…" multiline />

          {error && <div style={{ color: '#ff6b6b', fontSize: 12, padding: '8px 12px', background: 'rgba(232,0,45,0.08)', borderRadius: 6 }}>⚠️ {error}</div>}
          {saved  && <div style={{ color: '#34d399', fontSize: 12, padding: '8px 12px', background: 'rgba(52,211,153,0.08)', borderRadius: 6 }}>✅ Profile saved!</div>}

          <SubmitBtn loading={loading}>Save Changes</SubmitBtn>
        </form>
      </div>
    </div>
  );
}
