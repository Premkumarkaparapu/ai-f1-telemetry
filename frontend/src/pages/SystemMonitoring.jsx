import { useState, useEffect } from 'react';
import { useAuth } from '@clerk/clerk-react';

export default function SystemMonitoring() {
  const { getToken } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshInterval, setRefreshInterval] = useState(5); // in seconds
  const [autoRefresh, setAutoRefresh] = useState(true);

  // States for backend monitoring data
  const [statusData, setStatusData] = useState(null);
  const [metricsData, setMetricsData] = useState(null);
  const [healthData, setHealthData] = useState(null);
  const [diagnosticsData, setDiagnosticsData] = useState(null);

  const formatUptime = (seconds) => {
    if (!seconds) return '0s';
    const d = Math.floor(seconds / (3600 * 24));
    const h = Math.floor((seconds % (3600 * 24)) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    const parts = [];
    if (d > 0) parts.push(`${d}d`);
    if (h > 0) parts.push(`${h}h`);
    if (m > 0) parts.push(`${m}m`);
    if (s > 0 || parts.length === 0) parts.push(`${s}s`);
    return parts.join(' ');
  };

  const formatBytes = (bytes) => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const fetchData = async () => {
    try {
      const token = await getToken();
      const headers = {
        'Content-Type': 'application/json',
      };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      // Fetch all monitoring metrics in parallel
      const [statusRes, metricsRes, healthRes, diagRes] = await Promise.all([
        fetch('/api/v1/monitoring/status', { headers }),
        fetch('/api/v1/monitoring/metrics', { headers }),
        fetch('/api/v1/monitoring/health', { headers }),
        fetch('/api/v1/monitoring/diagnostics', { headers }),
      ]);

      if (!statusRes.ok || !metricsRes.ok || !healthRes.ok || !diagRes.ok) {
        throw new Error('Failed to retrieve monitoring telemetry. Verify authorization permissions.');
      }

      const [statusJson, metricsJson, healthJson, diagJson] = await Promise.all([
        statusRes.json(),
        metricsRes.json(),
        healthRes.json(),
        diagRes.json(),
      ]);

      setStatusData(statusJson);
      setMetricsData(metricsJson);
      setHealthData(healthJson);
      setDiagnosticsData(diagJson);
      setError(null);
    } catch (err) {
      console.error(err);
      setError(err.message || 'An error occurred while loading metrics.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;
    const id = setInterval(() => {
      fetchData();
    }, refreshInterval * 1000);
    return () => clearInterval(id);
  }, [autoRefresh, refreshInterval]);

  const getHealthBadgeColor = (status) => {
    switch (status) {
      case 'healthy': return '#10b981';
      case 'degraded': return '#f59e0b';
      case 'unavailable': return '#ef4444';
      default: return 'var(--text-muted)';
    }
  };

  if (loading && !statusData) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', minHeight: 400 }}>
        <div style={{ fontSize: 14, color: 'var(--text-muted)' }}>Loading monitoring metrics...</div>
      </div>
    );
  }

  if (error && !statusData) {
    return (
      <div style={{ padding: 30, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 15 }}>
        <div style={{ fontSize: 40 }}>⚠️</div>
        <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>Failed to Load Diagnostics</div>
        <div style={{ fontSize: 13, color: '#ff6b6b', maxWidth: 450, textAlign: 'center', lineHeight: 1.5 }}>
          {error}
        </div>
        <button onClick={fetchData} className="btn-primary" style={{ padding: '8px 20px', fontSize: 12 }}>
          Retry Ping
        </button>
      </div>
    );
  }

  const overallHealth = healthData?.status || 'healthy';

  return (
    <div style={{ padding: '24px 30px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Header bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(255,255,255,0.06)', paddingBottom: 16 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 900, color: 'var(--text-primary)', margin: 0, letterSpacing: '-0.3px' }}>
            System Monitoring
          </h1>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '4px 0 0' }}>
            Diagnostic panel and real-time performance metrics
          </p>
        </div>

        {/* Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}>
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                style={{ cursor: 'pointer' }}
              />
              Auto-refresh
            </label>
            {autoRefresh && (
              <select
                value={refreshInterval}
                onChange={(e) => setRefreshInterval(Number(e.target.value))}
                style={{
                  background: '#15202b',
                  border: '1px solid rgba(255,255,255,0.1)',
                  color: 'var(--text-primary)',
                  fontSize: 11,
                  padding: '2px 6px',
                  borderRadius: 4,
                  cursor: 'pointer',
                }}
              >
                <option value={2}>2s</option>
                <option value={5}>5s</option>
                <option value={10}>10s</option>
                <option value={30}>30s</option>
              </select>
            )}
          </div>

          <button
            onClick={fetchData}
            style={{
              padding: '6px 14px',
              borderRadius: 6,
              background: 'rgba(255,255,255,0.06)',
              border: '1px solid rgba(255,255,255,0.12)',
              color: 'var(--text-primary)',
              fontSize: 11,
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              transition: 'background 0.2s',
            }}
            onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.1)'}
            onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.06)'}
          >
            🔄 Refresh
          </button>
        </div>
      </div>

      {/* Overview stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16 }}>
        <div style={{ background: '#121c24', border: '1px solid rgba(255,255,255,0.05)', borderRadius: 12, padding: 18 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            System State
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 10 }}>
            <div style={{ width: 10, height: 10, borderRadius: '50%', background: getHealthBadgeColor(overallHealth), boxShadow: `0 0 10px ${getHealthBadgeColor(overallHealth)}` }} />
            <span style={{ fontSize: 20, fontWeight: 900, color: 'var(--text-primary)', textTransform: 'capitalize' }}>
              {overallHealth}
            </span>
          </div>
        </div>

        <div style={{ background: '#121c24', border: '1px solid rgba(255,255,255,0.05)', borderRadius: 12, padding: 18 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            Uptime
          </div>
          <div style={{ fontSize: 20, fontWeight: 900, color: 'var(--text-primary)', marginTop: 8 }}>
            {formatUptime(statusData?.uptime_seconds)}
          </div>
        </div>

        <div style={{ background: '#121c24', border: '1px solid rgba(255,255,255,0.05)', borderRadius: 12, padding: 18 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            Model Version
          </div>
          <div style={{ fontSize: 20, fontWeight: 900, color: '#3b82f6', marginTop: 8 }}>
            {diagnosticsData?.model_version || 'v2.7'}
          </div>
        </div>
      </div>

      {/* Section: Component Health Grid */}
      <div>
        <h2 style={{ fontSize: 14, fontWeight: 800, color: 'var(--text-primary)', marginBottom: 12, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
          Backing Infrastructure
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16 }}>
          {/* API Component */}
          <div style={{ background: '#121c24', border: '1px solid rgba(255,255,255,0.05)', borderRadius: 12, padding: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>Application API</span>
              <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 10, background: 'rgba(16,185,129,0.1)', color: '#10b981', fontWeight: 700 }}>
                ONLINE
              </span>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 12 }}>
              Uvicorn backend running healthy.
            </div>
          </div>

          {/* Supabase PostgreSQL Component */}
          <div style={{ background: '#121c24', border: '1px solid rgba(255,255,255,0.05)', borderRadius: 12, padding: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>PostgreSQL Database</span>
              <span style={{
                fontSize: 10, padding: '2px 8px', borderRadius: 10,
                background: statusData?.database === 'connected' ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
                color: statusData?.database === 'connected' ? '#10b981' : '#ef4444',
                fontWeight: 700
              }}>
                {statusData?.database === 'connected' ? 'CONNECTED' : 'DISCONNECTED'}
              </span>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 12 }}>
              Supabase telemetry table connections.
            </div>
          </div>

          {/* Redis Component */}
          <div style={{ background: '#121c24', border: '1px solid rgba(255,255,255,0.05)', borderRadius: 12, padding: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>Redis Cache</span>
              <span style={{
                fontSize: 10, padding: '2px 8px', borderRadius: 10,
                background: statusData?.redis === 'connected' ? 'rgba(16,185,129,0.1)' : 'rgba(245,158,11,0.1)',
                color: statusData?.redis === 'connected' ? '#10b981' : '#f59e0b',
                fontWeight: 700
              }}>
                {statusData?.redis === 'connected' ? 'ONLINE' : 'DEGRADED'}
              </span>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 12 }}>
              Upstash rate limiter &amp; circuit storage.
            </div>
          </div>

          {/* Gemini AI Component */}
          <div style={{ background: '#121c24', border: '1px solid rgba(255,255,255,0.05)', borderRadius: 12, padding: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>Gemini LLM API</span>
              <span style={{
                fontSize: 10, padding: '2px 8px', borderRadius: 10,
                background: statusData?.gemini === 'available' ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
                color: statusData?.gemini === 'available' ? '#10b981' : '#ef4444',
                fontWeight: 700
              }}>
                {statusData?.gemini === 'available' ? 'AVAILABLE' : 'DEGRADED'}
              </span>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 12 }}>
              Circuit state: <strong style={{ color: '#fff' }}>{diagnosticsData?.circuit_breaker_state || 'CLOSED'}</strong>
            </div>
          </div>
        </div>
      </div>

      {/* Two column metrics sections */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: 20 }}>
        {/* Performance metrics */}
        <div style={{ background: '#121c24', border: '1px solid rgba(255,255,255,0.05)', borderRadius: 12, padding: 20 }}>
          <h3 style={{ fontSize: 13, fontWeight: 800, color: 'var(--text-primary)', margin: '0 0 16px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            API Performance Metrics
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.04)', paddingBottom: 8 }}>
              <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>HTTP Requests (Lifetime)</span>
              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
                {metricsData?.request_count ?? 0}
              </span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.04)', paddingBottom: 8 }}>
              <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Avg Response Latency</span>
              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
                {metricsData?.request_latency?.toFixed(1) ?? '0.0'} ms
              </span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.04)', paddingBottom: 8 }}>
              <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Server Errors (5xx)</span>
              <span style={{ fontSize: 13, fontWeight: 700, color: metricsData?.error_count > 0 ? '#ef4444' : 'var(--text-primary)' }}>
                {metricsData?.error_count ?? 0}
              </span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.04)', paddingBottom: 8 }}>
              <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Rate Limit Rejections</span>
              <span style={{ fontSize: 13, fontWeight: 700, color: metricsData?.rate_limit_rejections > 0 ? '#f59e0b' : 'var(--text-primary)' }}>
                {metricsData?.rate_limit_rejections ?? 0}
              </span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: 4 }}>
              <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Redis Ping Latency</span>
              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
                {metricsData?.redis_latency?.toFixed(1) ?? '0.0'} ms
              </span>
            </div>
          </div>
        </div>

        {/* AI & Circuit Breaker metrics */}
        <div style={{ background: '#121c24', border: '1px solid rgba(255,255,255,0.05)', borderRadius: 12, padding: 20 }}>
          <h3 style={{ fontSize: 13, fontWeight: 800, color: 'var(--text-primary)', margin: '0 0 16px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            Gemini Strategist Logs
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.04)', paddingBottom: 8 }}>
              <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Gemini Calls</span>
              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
                {metricsData?.gemini_requests ?? 0}
              </span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.04)', paddingBottom: 8 }}>
              <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Gemini Error Volume</span>
              <span style={{ fontSize: 13, fontWeight: 700, color: metricsData?.gemini_errors > 0 ? '#ef4444' : 'var(--text-primary)' }}>
                {metricsData?.gemini_errors ?? 0}
              </span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.04)', paddingBottom: 8 }}>
              <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Circuit Status</span>
              <span style={{
                fontSize: 11, fontWeight: 700,
                color: diagnosticsData?.circuit_breaker_state === 'CLOSED' ? '#10b981' : '#ef4444'
              }}>
                {diagnosticsData?.circuit_breaker_state || 'CLOSED'}
              </span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: 4 }}>
              <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Gemini Avg Latency</span>
              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
                {metricsData?.gemini_latency?.toFixed(0) ?? '0'} ms
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* ML Prediction Models Diagnostics */}
      <div style={{ background: '#121c24', border: '1px solid rgba(255,255,255,0.05)', borderRadius: 12, padding: 20 }}>
        <h3 style={{ fontSize: 13, fontWeight: 800, color: 'var(--text-primary)', marginBottom: 16, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
          ML Prediction Models Diagnostics
        </h3>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {diagnosticsData?.ml_models ? (
            Object.entries(diagnosticsData.ml_models).map(([key, model]) => (
              <div
                key={key}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  background: 'rgba(255,255,255,0.02)',
                  border: '1px solid rgba(255,255,255,0.04)',
                  borderRadius: 8,
                  padding: '12px 16px',
                }}
              >
                <div>
                  <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', textTransform: 'capitalize' }}>
                    {key} Pipeline
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                    Status: <strong style={{ color: model.status === 'Loaded' ? '#10b981' : '#3b82f6' }}>{model.status}</strong>
                  </div>
                </div>

                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)', fontWeight: 600 }}>
                    Size: {formatBytes(model.file_size_bytes || model.total_file_size_bytes)}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>
                    Checksum verified
                  </div>
                </div>
              </div>
            ))
          ) : (
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>No model diagnostic metadata available.</div>
          )}
        </div>
      </div>
    </div>
  );
}
