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
    colorBackground: '#ffffff',
    colorInputBackground: '#f8f9fb',
    colorInputText: '#0f172a',
    colorText: '#0f172a',
    colorTextSecondary: '#64748b',
    colorNeutral: '#e2e8f0',
    colorSuccess: '#16a34a',
    colorDanger: '#dc2626',
    borderRadius: '12px',
    fontFamily: "'Inter', system-ui, sans-serif",
    fontSize: '15px',
    fontWeight: { normal: 400, medium: 500, bold: 700 },
  },
  elements: {
    rootBox: { backdropFilter: 'blur(16px)' },
    card: {
      background: '#ffffff',
      border: '1px solid #e2e8f0',
      boxShadow: '0 20px 60px rgba(0,0,0,0.12), 0 4px 16px rgba(232,0,45,0.08)',
      borderRadius: '20px',
      padding: '8px',
    },
    headerTitle: { color: '#0f172a', fontWeight: 800, fontSize: '22px', letterSpacing: '-0.4px' },
    headerSubtitle: { color: '#64748b', fontSize: '14px' },
    logoBox: { marginBottom: '4px' },
    socialButtonsBlockButton: {
      background: '#f8f9fb',
      border: '1.5px solid #e2e8f0',
      color: '#0f172a',
      borderRadius: '10px',
      fontWeight: 500,
    },
    socialButtonsBlockButtonText: { color: '#1e293b', fontWeight: 500 },
    dividerLine: { background: '#e2e8f0' },
    dividerText: { color: '#94a3b8', fontSize: '12px' },
    formFieldLabel: { color: '#374151', fontWeight: 600, fontSize: '13px' },
    formFieldInput: {
      background: '#f8f9fb',
      border: '1.5px solid #e2e8f0',
      borderRadius: '10px',
      color: '#0f172a',
      fontSize: '15px',
    },
    formButtonPrimary: {
      background: 'linear-gradient(135deg, #e8002d 0%, #c0001f 100%)',
      boxShadow: '0 4px 16px rgba(232,0,45,0.35)',
      fontWeight: 700,
      fontSize: '15px',
      borderRadius: '10px',
      border: 'none',
      letterSpacing: '0.2px',
    },
    footerActionLink: { color: '#e8002d', fontWeight: 600 },
    identityPreviewText: { color: '#475569' },
    identityPreviewEditButton: { color: '#e8002d' },
    formFieldSuccessText: { color: '#16a34a' },
    formFieldErrorText: { color: '#dc2626' },
    alertText: { color: '#0f172a' },
    badge: { background: '#fff1f2', color: '#e8002d', border: '1px solid #fecdd3' },
    userButtonPopoverCard: {
      background: '#ffffff',
      border: '1px solid #e2e8f0',
      borderRadius: '12px',
      boxShadow: '0 8px 32px rgba(0,0,0,0.12)',
    },
    userButtonPopoverActionButton: { color: '#1e293b' },
    userButtonPopoverActionButtonText: { color: '#1e293b' },
    modalBackdrop: { background: 'rgba(15,23,42,0.5)', backdropFilter: 'blur(8px)' },
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
