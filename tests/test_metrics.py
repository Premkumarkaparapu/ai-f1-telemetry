"""Unit tests for Prometheus Metrics Observability."""

from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from backend.app.main import app
from backend.app.core.metrics import (
    HTTP_REQUESTS_TOTAL,
    HTTP_REQUEST_DURATION_SECONDS,
    GEMINI_REQUESTS_TOTAL,
    GEMINI_REQUEST_DURATION_SECONDS,
    GEMINI_ERRORS_TOTAL,
)


def test_metrics_endpoint_unauthenticated():
    client = TestClient(app)
    # Check that GET /metrics is unauthenticated and returns status 200
    res = client.get("/metrics")
    assert res.status_code == 200
    # Must contain prometheus payload headers and metrics definitions
    assert "text/plain" in res.headers["Content-Type"]
    assert "http_requests" in res.text


def test_http_request_metrics_increment():
    client = TestClient(app)

    # Clean initial state of the specific label combo if it exists
    before_value = 0.0
    for metric in REGISTRY.collect():
        if metric.name == "http_requests":
            for sample in metric.samples:
                if (
                    sample.name == "http_requests_total"
                    and sample.labels.get("endpoint") == "/health/live"
                    and sample.labels.get("method") == "GET"
                    and sample.labels.get("status_code") == "200"
                ):
                    before_value = sample.value

    # Make request
    res = client.get("/health/live")
    assert res.status_code == 200

    # Retrieve metrics again to assert increment
    after_value = 0.0
    for metric in REGISTRY.collect():
        if metric.name == "http_requests":
            for sample in metric.samples:
                if (
                    sample.name == "http_requests_total"
                    and sample.labels.get("endpoint") == "/health/live"
                    and sample.labels.get("method") == "GET"
                    and sample.labels.get("status_code") == "200"
                ):
                    after_value = sample.value

    assert after_value == before_value + 1.0


def test_gemini_metrics_exist_in_registry():
    # Assert that all custom Gemini metrics are successfully registered.
    # Note: Prometheus client automatically strips '_total' suffix from Counters internally.
    metric_names = [m.name for m in REGISTRY.collect()]
    assert "gemini_requests" in metric_names
    assert "gemini_request_duration_seconds" in metric_names
    assert "gemini_errors" in metric_names
    # Use metrics variables to satisfy flake8 lints
    assert HTTP_REQUESTS_TOTAL is not None
    assert HTTP_REQUEST_DURATION_SECONDS is not None
    assert GEMINI_REQUESTS_TOTAL is not None
    assert GEMINI_REQUEST_DURATION_SECONDS is not None
    assert GEMINI_ERRORS_TOTAL is not None
