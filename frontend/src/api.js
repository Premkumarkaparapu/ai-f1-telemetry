// In production VITE_API_URL is set to the Render backend URL.
// In development, Vite proxies /api to localhost:8000.
const BASE = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api/v1`
  : '/api/v1';

// Clerk token getter — injected at app startup from main.jsx
let _getClerkToken = null;
export function setClerkGetToken(fn) { _getClerkToken = fn; }

async function authHeaders() {
  try {
    if (_getClerkToken) {
      const token = await _getClerkToken();
      if (token) return { Authorization: `Bearer ${token}` };
    }
  } catch (_) {}
  return {};
}

async function get(path) {
  const headers = await authHeaders();
  const res = await fetch(`${BASE}${path}`, { headers });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${path}`);
  return res.json();
}

async function post(path, body) {
  const headers = await authHeaders();
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...headers },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${path}`);
  return res.json();
}

async function put(path, body) {
  const headers = await authHeaders();
  const res = await fetch(`${BASE}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...headers },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${path}`);
  return res.json();
}

// Normalize raw telemetry point from backend schema to frontend schema
function normalizeTelPoint(p) {
  return {
    ...p,
    speed:    p.speed_kmh    ?? p.speed    ?? 0,
    throttle: p.throttle_pct ?? p.throttle ?? 0,
    brake:    p.brake === true ? 1 : (p.brake === false ? 0 : (p.brake ?? 0)),
    drs:      p.drs   === true ? 10 : (p.drs === false ? 0 : (p.drs ?? 0)),
    distance: p.distance_m   ?? p.distance ?? 0,
  };
}

export const api = {
  // Sessions
  getSessions:  ()           => get('/sessions/'),
  getSession:   (id)         => get(`/sessions/${id}`),
  getWeather:   (id)         => get(`/sessions/${id}/weather`),
  getStandings: (id)         => get(`/sessions/${id}/standings`),
  getYears:     ()           => get('/sessions/years'),
  getByYear:    (year)       => get(`/sessions/by-year/${year}`),

  // Drivers
  getDrivers:      (sessionId)        => get(`/drivers/?session_id=${sessionId}`),
  getDriver:       (id)               => get(`/drivers/${id}`),
  getDriverByCode: (code, sessionId)  => get(`/drivers/code/${code}?session_id=${sessionId}`),

  // Laps
  getLaps:    (driverId)             => get(`/laps/?driver_id=${driverId}`),
  getLap:     (id)                   => get(`/laps/${id}`),
  getStints:  (driverId, sessionId)  => get(`/laps/stints/?driver_id=${driverId}&session_id=${sessionId}`),
  getPitStops:(driverId, sessionId)  => get(`/laps/pitstops/?driver_id=${driverId}&session_id=${sessionId}`),

  // Telemetry — DB-stored (top 5 per session)
  getTelemetryFromDB: (lapId) =>
    get(`/telemetry/${lapId}`).then(pts => pts.map(normalizeTelPoint)),

  // Telemetry — live from FastF1 cache (all drivers)
  getTelemetryLive: (sessionId, driverCode, lapNumber) =>
    get(`/telemetry/live/${sessionId}/${driverCode}/${lapNumber}`)
      .then(pts => pts.map(normalizeTelPoint)),

  // Smart telemetry: try DB first, fall back to live cache
  getTelemetry: async (lapId, sessionId, driverCode, lapNumber) => {
    try {
      const pts = await get(`/telemetry/${lapId}`).then(pts => pts.map(normalizeTelPoint));
      if (pts.length > 0) return pts;
    } catch (_) {}
    // Fall back to live if we have the extra context
    if (sessionId && driverCode && lapNumber) {
      return get(`/telemetry/live/${sessionId}/${driverCode}/${lapNumber}`)
        .then(pts => pts.map(normalizeTelPoint));
    }
    return [];
  },

  getTelemetrySummary: (lapId) => get(`/telemetry/${lapId}/summary`),
  compareLaps: (lap1Id, lap2Id) => get(`/telemetry/compare/laps?lap1_id=${lap1Id}&lap2_id=${lap2Id}`),

  // Predictions
  predict:           (body)                        => post('/predict/', body),
  simulateStrategy:  (body)                        => post('/predict/strategy', body),
  getDegradation:    (compound, laps = 40)         => get(`/predict/degradation/${compound}?max_life=${laps}`),
  getPitWindow:      (sessionId, driverId, lap)    => get(`/predict/pit-window/${sessionId}/${driverId}?current_lap=${lap}`),
  getPredictionHistory: (sessionId)                => get(`/predict/history/${sessionId}`),

  // Auth
  register: (body)  => post('/auth/register', body),
  login:    (body)  => post('/auth/login', body),
  getMe:    ()      => get('/auth/me'),
  updateMe: (body)  => put('/auth/me', body),
  getTeams: ()      => get('/auth/teams'),
};

