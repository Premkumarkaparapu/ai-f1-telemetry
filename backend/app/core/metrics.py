"""Prometheus Metrics Registry.

Defines low-cardinality metrics for HTTP requests, Redis, database pools,
and Gemini API service dependencies.
"""

from prometheus_client import Counter, Histogram, Gauge

# ── HTTP Latency & Throughput ────────────────────────────────────────────────

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total number of HTTP requests processed.",
    ["method", "endpoint", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "Histogram of HTTP request durations in seconds.",
    ["method", "endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float("inf")),
)

# ── Gemini Dependency Health ─────────────────────────────────────────────────

GEMINI_REQUESTS_TOTAL = Counter(
    "gemini_requests_total",
    "Total number of requests sent to the Gemini API.",
    ["model_name", "api_method", "status"],
)

GEMINI_REQUEST_DURATION_SECONDS = Histogram(
    "gemini_request_duration_seconds",
    "Histogram of Gemini API call durations in seconds.",
    ["model_name", "api_method"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 15.0, float("inf")),
)

GEMINI_ERRORS_TOTAL = Counter(
    "gemini_errors_total",
    "Total number of errors encountered when calling the Gemini API.",
    ["model_name", "error_type"],
)

# ── Backing Services Status ──────────────────────────────────────────────────

REDIS_CONNECTION_STATUS = Gauge(
    "redis_connection_status",
    "Status of Redis connection (1 = Connected, 0 = Disconnected).",
)

DB_POOL_ACTIVE = Gauge(
    "db_pool_active",
    "Number of active connections in the database pool.",
)

APP_HEALTH_STATUS = Gauge(
    "app_health_status",
    "Status of application health (1 = healthy, 0 = unhealthy).",
)

APP_READINESS_STATUS = Gauge(
    "app_readiness_status",
    "Status of application readiness to serve traffic (1 = ready, 0 = unready).",
)

RATE_LIMIT_REJECTIONS_TOTAL = Counter(
    "rate_limit_rejections_total",
    "Total number of rate limit rejections (HTTP 429).",
)

CIRCUIT_BREAKER_STATE = Gauge(
    "circuit_breaker_state",
    "State of the circuit breaker (1 = CLOSED, 0.5 = HALF-OPEN, 0 = OPEN).",
)


