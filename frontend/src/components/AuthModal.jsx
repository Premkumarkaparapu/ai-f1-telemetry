import { SignIn, SignUp, useClerk } from '@clerk/clerk-react'
import { useState } from 'react'

// ── Full-page Clerk auth modal overlay ───────────────────────────────────────
export default function AuthModal({ onClose, initialTab = 'login' }) {
  const [tab, setTab] = useState(initialTab === 'register' ? 'signup' : 'signin')
  const { signOut } = useClerk()

  return (
    <div
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
      style={{
        position: 'fixed', inset: 0, zIndex: 9999,
        background: 'rgba(5,8,14,0.92)',
        backdropFilter: 'blur(16px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 16, flexDirection: 'column', gap: 16,
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
        <svg width="36" height="24" viewBox="0 0 60 40">
          <rect width="60" height="40" rx="4" fill="#e8002d" />
          <text x="30" y="28" textAnchor="middle" fill="white"
            fontFamily="Arial Black,Arial" fontWeight="900" fontSize="22">F1</text>
        </svg>
        <div>
          <div style={{ fontSize: 18, fontWeight: 800, color: '#f0f4f8', letterSpacing: '-0.3px' }}>
            F1 Telemetry Platform
          </div>
          <div style={{ fontSize: 11, color: '#8899aa' }}>Race data & strategy analytics</div>
        </div>
      </div>

      {/* Tab switcher */}
      <div style={{
        display: 'flex', gap: 4, background: 'rgba(255,255,255,0.06)',
        borderRadius: 10, padding: 3, width: '100%', maxWidth: 400,
      }}>
        {[['signin', 'Sign In'], ['signup', 'Create Account']].map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)}
            style={{
              flex: 1, padding: '8px 0', border: 'none', borderRadius: 7,
              cursor: 'pointer', fontSize: 13, fontWeight: 600, fontFamily: 'inherit',
              transition: 'all 0.15s',
              background: tab === id ? 'rgba(232,0,45,0.9)' : 'transparent',
              color: tab === id ? '#fff' : '#8899aa',
            }}>
            {label}
          </button>
        ))}
      </div>

      {/* Clerk component */}
      <div style={{ width: '100%', maxWidth: 400 }}>
        {tab === 'signin' ? (
          <SignIn
            afterSignInUrl="/"
            appearance={{ elements: { rootBox: { width: '100%' }, card: { width: '100%' } } }}
            routing="virtual"
            signUpUrl="#signup"
          />
        ) : (
          <SignUp
            afterSignUpUrl="/"
            appearance={{ elements: { rootBox: { width: '100%' }, card: { width: '100%' } } }}
            routing="virtual"
            signInUrl="#signin"
          />
        )}
      </div>

      <button onClick={onClose}
        style={{
          background: 'none', border: '1px solid rgba(255,255,255,0.1)',
          color: '#8899aa', padding: '6px 20px', borderRadius: 8,
          cursor: 'pointer', fontSize: 12, fontFamily: 'inherit',
        }}>
        ✕ Close
      </button>
    </div>
  )
}
