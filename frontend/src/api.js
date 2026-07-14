/* API client — all calls proxy through /api/v1 → FastAPI on :8000 */

const BASE = '/api/v1'

async function get(path) {
  const res = await fetch(BASE + path)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${path}`)
  return res.json()
}

async function post(path, body) {
  const res = await fetch(BASE + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `${res.status} ${res.statusText}`)
  }
  return res.json()
}

export const api = {
  // Sessions
  sessions:         ()                           => get('/sessions/'),
  session:          (id)                         => get(`/sessions/${id}`),
  sessionWeather:   (id)                         => get(`/sessions/${id}/weather`),
  sessionStandings: (id)                         => get(`/sessions/${id}/standings`),

  // Drivers
  drivers:          (sessionId)                  => get(`/drivers/?session_id=${sessionId}`),
  driver:           (code, sessionId)            => get(`/drivers/${code}?session_id=${sessionId}`),

  // Laps
  laps:             (driverId, validOnly=false)  => get(`/laps/?driver_id=${driverId}&valid_only=${validOnly}`),
  lap:              (lapId)                      => get(`/laps/${lapId}`),
  stints:           (driverId, sessionId)        => get(`/laps/stints/?driver_id=${driverId}&session_id=${sessionId}`),
  pitstops:         (driverId, sessionId)        => get(`/laps/pitstops/?driver_id=${driverId}&session_id=${sessionId}`),

  // Telemetry
  telemetry:        (lapId)                      => get(`/telemetry/${lapId}`),
  telemetrySummary: (lapId)                      => get(`/telemetry/${lapId}/summary`),
  compareLaps:      (lapId1, lapId2)             => get(`/telemetry/compare/laps?lap_id_1=${lapId1}&lap_id_2=${lapId2}`),

  // Predictions / Strategy
  predict:          (body)                       => post('/predict/', body),
  strategy:         (body)                       => post('/predict/strategy', body),
  degradation:      (compound, maxLife=40)       => get(`/predict/degradation/${compound}?max_life=${maxLife}`),
  pitWindow:        (sessionId, driverId, lap)   => get(`/predict/pit-window/${sessionId}/${driverId}?current_lap=${lap}`),
  predictions:      (sessionId)                  => get(`/predict/history/${sessionId}`),
}
