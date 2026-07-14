import { useState } from 'react'
import Dashboard from './pages/Dashboard'
import LapComparison from './pages/LapComparison'
import Degradation from './pages/Degradation'
import StrategySimulator from './pages/StrategySimulator'
import LiveReplay from './pages/LiveReplay'

const NAV = [
  { id: 'dashboard',  label: 'Dashboard',   icon: '⬛' },
  { id: 'comparison', label: 'Lap Compare',  icon: '⇌' },
  { id: 'degradation',label: 'Degradation',  icon: '📉' },
  { id: 'strategy',   label: 'Strategy Sim', icon: '🎯' },
  { id: 'replay',     label: 'Live Replay',  icon: '▶' },
]

export default function App() {
  const [page, setPage] = useState('dashboard')

  const Page = {
    dashboard:   Dashboard,
    comparison:  LapComparison,
    degradation: Degradation,
    strategy:    StrategySimulator,
    replay:      LiveReplay,
  }[page]

  return (
    <div className="app">
      {/* ── Sidebar ── */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="logo-mark">
            <div className="logo-icon">F1</div>
            <div>
              <div className="logo-text">TELEMETRY</div>
              <div className="logo-sub">AI Platform</div>
            </div>
          </div>
        </div>

        <nav className="sidebar-nav">
          {NAV.map(n => (
            <button
              key={n.id}
              className={`nav-item ${page === n.id ? 'active' : ''}`}
              onClick={() => setPage(n.id)}
            >
              <span className="nav-icon">{n.icon}</span>
              <span>{n.label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <span className="status-dot" />
          API connected
        </div>
      </aside>

      {/* ── Main content ── */}
      <main className="main-content">
        <Page />
      </main>
    </div>
  )
}
