import http from 'k6/http';
import { check, sleep } from 'k6';

// k6 Load Test Configuration
export const options = {
  stages: [
    { duration: '10s', target: 10 },  // Ramp-up to 10 users
    { duration: '20s', target: 50 },  // Ramp-up to 50 users
    { duration: '20s', target: 100 }, // Ramp-up to 100 users
    { duration: '20s', target: 200 }, // Ramp-up to 200 users (peak load capacity)
    { duration: '15s', target: 0 },   // Cool down to 0 users
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'],   // Error rate must be less than 1%
    http_req_duration: ['p(95)<500'], // 95% of requests must complete under 500ms
  },
};

const BASE_URL = __ENV.API_URL || 'http://localhost:8000';
const API_KEY = __ENV.API_KEY || 'test-m2m-api-key';

export default function () {
  const headers = {
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY,
  };

  // 1. Health check smoke test
  const healthRes = http.get(`${BASE_URL}/health`);
  check(healthRes, {
    'health status is 200': (r) => r.status === 200,
    'health body is ok': (r) => r.json().status === 'ok',
  });
  sleep(1);

  // 2. Fetch sessions list
  const sessionsRes = http.get(`${BASE_URL}/api/v1/sessions`, { headers });
  check(sessionsRes, {
    'sessions list status is 200': (r) => r.status === 200,
  });
  sleep(1);

  // 3. Strategy run prediction request
  const payload = JSON.stringify({
    session_id: 1,
    driver_id: 1,
    prediction_type: 'lap_time',
  });

  const predictRes = http.post(`${BASE_URL}/api/v1/predict/`, payload, { headers });
  check(predictRes, {
    'predict status is 201 or 404 or 422': (r) => [201, 404, 422].includes(r.status),
  });
  sleep(1);
}
