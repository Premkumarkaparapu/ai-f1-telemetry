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
  variables: {
    colorPrimary: '#e8002d',
    colorBackground: '#0f1923',
    colorInputBackground: 'rgba(255,255,255,0.05)',
    colorInputText: '#f0f4f8',
    colorText: '#f0f4f8',
    colorTextSecondary: '#8899aa',
    colorNeutral: '#1a2535',
    borderRadius: '10px',
    fontFamily: "'Inter', 'Outfit', system-ui, sans-serif",
  },
  elements: {
    card: {
      background: 'linear-gradient(145deg, #0f1923, #0d1520)',
      border: '1px solid rgba(255,255,255,0.08)',
      boxShadow: '0 32px 80px rgba(0,0,0,0.7), 0 0 0 1px rgba(232,0,45,0.1)',
    },
    headerTitle: { color: '#f0f4f8', fontWeight: 800 },
    headerSubtitle: { color: '#8899aa' },
    socialButtonsBlockButton: {
      background: 'rgba(255,255,255,0.05)',
      border: '1px solid rgba(255,255,255,0.1)',
      color: '#f0f4f8',
    },
    dividerLine: { background: 'rgba(255,255,255,0.08)' },
    dividerText: { color: '#8899aa' },
    formButtonPrimary: {
      background: 'linear-gradient(135deg, #e8002d, #c00025)',
      boxShadow: '0 4px 16px rgba(232,0,45,0.3)',
      fontWeight: 700,
    },
    footerActionLink: { color: '#e8002d', fontWeight: 600 },
    identityPreview: { background: 'rgba(255,255,255,0.04)' },
    userButtonPopoverCard: {
      background: '#0f1923',
      border: '1px solid rgba(255,255,255,0.08)',
    },
    userButtonPopoverActionButton: { color: '#f0f4f8' },
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
