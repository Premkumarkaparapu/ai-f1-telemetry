import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter } from 'k6/metrics';

// Track success and semaphore limit rejections
const successCount = new Counter('semaphore_acquired');
const rateLimitCount = new Counter('semaphore_rejected');

export const options = {
  vus: 100,          // 100+ concurrent requests
  duration: '5s',    // Run for 5 seconds
};

const BASE_URL = __ENV.API_URL || 'http://localhost:8000';
const API_KEY = __ENV.API_KEY || 'test-m2m-api-key';

export default function () {
  const headers = {
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY,
  };

  const payload = JSON.stringify({
    question: 'Calculate tire degradation and optimal pit window for VER.',
    session_id: 1,
    driver_code: 'VER',
  });

  const res = http.post(`${BASE_URL}/api/v1/ai/ask`, payload, { headers });

  check(res, {
    'status is 200 or 429': (r) => [200, 429].includes(r.status),
  });

  if (res.status === 200) {
    successCount.add(1);
  } else if (res.status === 429) {
    rateLimitCount.add(1);
  }

  // Sleep for 0.1s to stagger requests slightly
  sleep(0.1);
}
