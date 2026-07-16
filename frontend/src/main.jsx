import React from 'react'
import ReactDOM from 'react-dom/client'
import { ClerkProvider, useAuth } from '@clerk/clerk-react'
import App from './App'
import { setClerkGetToken } from './api.js'
import './index.css'

// Clerk publishable key — set VITE_CLERK_PUBLISHABLE_KEY in .env.local
const PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY

if (!PUBLISHABLE_KEY) {
  console.warn(
    '⚠️  VITE_CLERK_PUBLISHABLE_KEY is not set.\n' +
    '   Create frontend/.env.local and add your key from https://clerk.com'
  )
}

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(error) { return { error }; }
  componentDidCatch(error, info) { console.error('React crash:', error, info); }
  render() {
    if (this.state.error) {
      return (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center',
          justifyContent: 'center', height: '100vh', background: '#0d1117',
          color: '#ff6b6b', fontFamily: 'monospace', padding: 40, gap: 16
        }}>
          <div style={{ fontSize: 32 }}>💥 React Crash</div>
          <div style={{ fontSize: 14, maxWidth: 800, wordBreak: 'break-word' }}>
            {this.state.error?.message}
          </div>
          <pre style={{
            fontSize: 11, color: '#a8b8cc', maxWidth: 900, overflow: 'auto',
            background: 'rgba(255,255,255,0.05)', padding: 16, borderRadius: 8,
            whiteSpace: 'pre-wrap'
          }}>
            {this.state.error?.stack}
          </pre>
          <button onClick={() => this.setState({ error: null })}
            style={{
              padding: '8px 20px', background: '#e8002d', color: '#fff',
              border: 'none', borderRadius: 6, cursor: 'pointer',
              fontSize: 13, fontWeight: 700
            }}>Retry</button>
        </div>
      );
    }
    return this.props.children;
  }
}


const clerkAppearance = {
  layout: {
    logoPlacement: 'inside',
    showOptionalFields: false,
    socialButtonsVariant: 'blockButton',
  },
  variables: {
    colorPrimary: '#e8002d',
    colorBackground: '#080c10',
    colorInputBackground: 'rgba(255,255,255,0.06)',
    colorInputText: '#ffffff',
    colorText: '#ffffff',
    colorTextSecondary: '#94a3b8',
    colorNeutral: '#1e2d3d',
    colorSuccess: '#22c55e',
    colorDanger: '#ef4444',
    borderRadius: '12px',
    fontFamily: "'Inter', system-ui, sans-serif",
    fontSize: '15px',
    fontWeight: { normal: 400, medium: 500, bold: 700 },
  },
  elements: {
    rootBox: {
      backdropFilter: 'blur(20px)',
    },
    card: {
      background: 'linear-gradient(160deg, #0d1520 0%, #080c10 60%, #0d0a14 100%)',
      border: '1px solid rgba(232,0,45,0.2)',
      boxShadow: '0 0 0 1px rgba(232,0,45,0.08), 0 40px 100px rgba(0,0,0,0.8), 0 0 60px rgba(232,0,45,0.06)',
      borderRadius: '16px',
      padding: '8px',
    },
    headerTitle: {
      color: '#ffffff',
      fontWeight: 800,
      fontSize: '22px',
      letterSpacing: '-0.3px',
    },
    headerSubtitle: { color: '#64748b', fontSize: '14px' },
    logoBox: { marginBottom: '4px' },
    socialButtonsBlockButton: {
      background: 'rgba(255,255,255,0.04)',
      border: '1px solid rgba(255,255,255,0.1)',
      color: '#e2e8f0',
      borderRadius: '10px',
      transition: 'all 0.2s ease',
      '&:hover': {
        background: 'rgba(255,255,255,0.08)',
        borderColor: 'rgba(232,0,45,0.3)',
      },
    },
    socialButtonsBlockButtonText: { color: '#e2e8f0', fontWeight: 500 },
    dividerLine: { background: 'rgba(255,255,255,0.07)' },
    dividerText: { color: '#475569', fontSize: '12px' },
    formFieldLabel: { color: '#94a3b8', fontWeight: 500, fontSize: '13px' },
    formFieldInput: {
      background: 'rgba(255,255,255,0.05)',
      border: '1px solid rgba(255,255,255,0.1)',
      borderRadius: '10px',
      color: '#ffffff',
      fontSize: '15px',
      '&:focus': { borderColor: 'rgba(232,0,45,0.5)', boxShadow: '0 0 0 3px rgba(232,0,45,0.1)' },
    },
    formButtonPrimary: {
      background: 'linear-gradient(135deg, #e8002d 0%, #b5001f 100%)',
      boxShadow: '0 4px 20px rgba(232,0,45,0.4), inset 0 1px 0 rgba(255,255,255,0.1)',
      fontWeight: 700,
      fontSize: '15px',
      borderRadius: '10px',
      border: 'none',
      letterSpacing: '0.3px',
      transition: 'all 0.2s ease',
      '&:hover': { boxShadow: '0 6px 28px rgba(232,0,45,0.6)' },
    },
    footerActionLink: {
      color: '#e8002d',
      fontWeight: 600,
      '&:hover': { color: '#ff1f47' },
    },
    identityPreviewText: { color: '#94a3b8' },
    identityPreviewEditButton: { color: '#e8002d' },
    formFieldSuccessText: { color: '#22c55e' },
    formFieldErrorText: { color: '#ef4444' },
    alertText: { color: '#f8fafc' },
    badge: { background: 'rgba(232,0,45,0.15)', color: '#e8002d' },
    userButtonPopoverCard: {
      background: 'linear-gradient(160deg, #0d1520, #080c10)',
      border: '1px solid rgba(255,255,255,0.08)',
      borderRadius: '12px',
      boxShadow: '0 20px 60px rgba(0,0,0,0.8)',
    },
    userButtonPopoverActionButton: {
      color: '#e2e8f0',
      '&:hover': { background: 'rgba(232,0,45,0.1)', color: '#ffffff' },
    },
  },
}

// Bridges Clerk's getToken() into api.js so all fetch calls get the JWT
function ClerkTokenBridge() {
  const { getToken } = useAuth()
  React.useEffect(() => {
    setClerkGetToken(() => getToken())
    return () => setClerkGetToken(null)
  }, [getToken])
  return null
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <ErrorBoundary>
    <ClerkProvider
      publishableKey={PUBLISHABLE_KEY || 'pk_test_placeholder'}
      appearance={clerkAppearance}
      afterSignInUrl="/"
      afterSignUpUrl="/"
      afterSignOutUrl="/"
    >
      <ClerkTokenBridge />
      <App />
    </ClerkProvider>
  </ErrorBoundary>
)
