import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(error) {
    return { error };
  }
  componentDidCatch(error, info) {
    console.error('React crash:', error, info);
  }
  render() {
    if (this.state.error) {
      return (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          height: '100vh', background: '#0d1117', color: '#ff6b6b', fontFamily: 'monospace', padding: 40, gap: 16
        }}>
          <div style={{ fontSize: 32 }}>💥 React Crash</div>
          <div style={{ fontSize: 14, color: '#ff6b6b', maxWidth: 800, wordBreak: 'break-word' }}>
            {this.state.error?.message}
          </div>
          <pre style={{ fontSize: 11, color: '#a8b8cc', maxWidth: 900, overflow: 'auto',
            background: 'rgba(255,255,255,0.05)', padding: 16, borderRadius: 8, whiteSpace: 'pre-wrap' }}>
            {this.state.error?.stack}
          </pre>
          <button onClick={() => this.setState({ error: null })}
            style={{ padding: '8px 20px', background: '#e8002d', color: '#fff', border: 'none',
              borderRadius: 6, cursor: 'pointer', fontSize: 13, fontWeight: 700 }}>
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <ErrorBoundary>
    <App />
  </ErrorBoundary>
)
