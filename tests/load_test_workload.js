import http from 'k6/http';
import { check, sleep } from 'k6';

// Read configuration from environment variables
const BASE_URL = __ENV.K6_TARGET_URL || 'http://127.0.0.1:8000';
const TOKEN = __ENV.K6_AUTH_TOKEN || 'dev_secret_key'; // Fallback to dev key if token not provided

export const options = {
  stages: [
    { duration: '5s', target: 20 },  // Ramp-up to 20 users
    { duration: '10s', target: 50 }, // Scale to 50 users
    { duration: '5s', target: 0 },   // Ramp-down
  ],
  thresholds: {
    http_req_failed: ['rate<0.05'], // Accept less than 5% failures under load
    http_req_duration: ['p(95)<30000'], // 95% of requests must resolve within 30s
  },
};

export default function () {
  const rand = Math.random();
  const headers = {
    'Content-Type': 'application/json',
  };
  
  // Apply Bearer token or API key authentication depending on provided format
  if (TOKEN.startsWith('ey')) {
    headers['Authorization'] = `Bearer ${TOKEN}`;
  } else {
    // Dev API key format
    headers['X-API-Key'] = TOKEN;
  }

  const params = { headers };

  if (rand < 0.35) {
    // 35% Weight: GET /sessions
    const res = http.get(`${BASE_URL}/api/v1/sessions/`, params);
    check(res, {
      'get sessions status is 200': (r) => r.status === 200,
    });
  } else if (rand < 0.70) {
    // 35% Weight: GET /laps
    const res = http.get(`${BASE_URL}/api/v1/laps/?driver_id=1`, params);
    check(res, {
      'get laps status is 200': (r) => r.status === 200,
    });
  } else if (rand < 0.90) {
    // 20% Weight: POST /predict/strategy
    const payload = JSON.stringify({
      session_id: 1,
      driver_id: 1,
      pit_laps: [18],
      compounds: ['SOFT', 'MEDIUM'],
      pit_time_loss_ms: 25000,
    });
    const res = http.post(`${BASE_URL}/api/v1/predict/strategy`, payload, params);
    check(res, {
      'predict strategy status is 201': (r) => r.status === 201,
    });
  } else {
    // 10% Weight: POST /ai/ask (Gemini Pitwall AI)
    const payload = JSON.stringify({
      question: 'Verify driver tyre degradation rate in stint 1.',
      session_id: 1,
      driver_code: 'VER',
    });
    const res = http.post(`${BASE_URL}/api/v1/ai/ask`, payload, params);
    check(res, {
      'ai ask status is 200': (r) => r.status === 200,
    });
  }

  sleep(0.1); // Small pacing delay between iterations
}
