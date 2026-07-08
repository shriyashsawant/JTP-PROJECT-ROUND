"""
Tests for the request-logging middleware in main.py, in isolation from the
real app (which requires a live Postgres connection at startup). Mounts the
middleware function directly onto a throwaway FastAPI app instead.
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.metrics import http_request_duration_seconds, http_requests_failed_total
from app.main import app as real_app
from app.main import request_logging_middleware


def _build_test_app() -> FastAPI:
    app = FastAPI()
    app.middleware("http")(request_logging_middleware)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    @app.get("/boom")
    async def boom():
        raise RuntimeError("kaboom")

    @app.get("/items/{item_id}")
    async def get_item(item_id: int):
        return {"item_id": item_id}

    return app


def _sample(metric, suffix: str, **labels) -> float:
    """Reads a metric's current value via the public `collect()` API
    (`_total`/`_count` suffix included in the sample name itself) rather than
    reaching into private per-child attributes, which vary across
    prometheus_client versions. Returns 0.0 if never observed - a metric
    with no data yet, not an error."""
    for family in metric.collect():
        for s in family.samples:
            if s.name.endswith(suffix) and s.labels == labels:
                return s.value
    return 0.0


def _counter_value(counter, **labels) -> float:
    return _sample(counter, "_total", **labels)


def _histogram_count(histogram, **labels) -> float:
    return _sample(histogram, "_count", **labels)


class TestRequestLoggingMiddleware:
    def test_success_response_gets_request_id_header(self):
        client = TestClient(_build_test_app())
        resp = client.get("/ping")
        assert resp.status_code == 200
        assert "x-request-id" in resp.headers
        assert len(resp.headers["x-request-id"]) == 12

    def test_each_request_gets_a_distinct_request_id(self):
        client = TestClient(_build_test_app())
        first = client.get("/ping").headers["x-request-id"]
        second = client.get("/ping").headers["x-request-id"]
        assert first != second

    def test_unhandled_exception_still_returns_500(self):
        client = TestClient(_build_test_app(), raise_server_exceptions=False)
        resp = client.get("/boom")
        assert resp.status_code == 500


class TestMiddlewareMetrics:
    """The metrics module's Counter/Histogram objects are process-wide
    singletons (app/core/metrics.py), not per-test instances, so every
    assertion here is a before/after delta - never an absolute count -
    to stay correct regardless of what other tests already recorded
    against the same route+status label."""

    def test_successful_request_is_recorded_in_the_latency_histogram(self):
        client = TestClient(_build_test_app())
        before = _histogram_count(http_request_duration_seconds, route="/ping", status="200")
        client.get("/ping")
        after = _histogram_count(http_request_duration_seconds, route="/ping", status="200")
        assert after == before + 1

    def test_route_label_uses_the_path_template_not_the_resolved_path(self):
        # Two different item IDs must collapse into ONE label series
        # ("/items/{item_id}"), not a distinct series per ID - an
        # unbounded-cardinality metric that gets worse forever as traffic
        # grows (see _route_template's own docstring in main.py). Verified
        # live against the real running app too (curl /api/v1/perfume/1 and
        # /2 both landed under one "/api/v1/perfume/{perfume_id}" series).
        client = TestClient(_build_test_app())
        before = _histogram_count(http_request_duration_seconds, route="/items/{item_id}", status="200")
        client.get("/items/1")
        client.get("/items/2")
        after = _histogram_count(http_request_duration_seconds, route="/items/{item_id}", status="200")
        assert after == before + 2
        # Neither literal resolved path should have its own series at all.
        assert _histogram_count(http_request_duration_seconds, route="/items/1", status="200") == 0.0
        assert _histogram_count(http_request_duration_seconds, route="/items/2", status="200") == 0.0

    def test_unhandled_exception_increments_the_failure_counter(self):
        client = TestClient(_build_test_app(), raise_server_exceptions=False)
        before = _counter_value(http_requests_failed_total, route="/boom")
        client.get("/boom")
        after = _counter_value(http_requests_failed_total, route="/boom")
        assert after == before + 1

    def test_successful_request_does_not_increment_the_failure_counter(self):
        client = TestClient(_build_test_app())
        before = _counter_value(http_requests_failed_total, route="/ping")
        client.get("/ping")
        after = _counter_value(http_requests_failed_total, route="/ping")
        assert after == before


class TestCorsAllowsApiKeyHeader:
    """Regression test for a real bug: the frontend sends X-API-Key on every
    request (see app/api/auth.py), but CORSMiddleware's allow_headers only
    listed Content-Type - browsers preflight (OPTIONS) any cross-origin
    request carrying a non-simple header, and Starlette's CORSMiddleware
    rejects the preflight itself with 400 if a requested header isn't
    allowed. curl-based testing never catches this (curl doesn't send
    preflights), so this only ever surfaced from a real browser - a genuine
    testing gap this test closes. Uses the real `app` (not a throwaway one)
    since this is exactly the CORSMiddleware config that matters; a bare
    TestClient(app) - no `with` context manager - never triggers the
    lifespan, so this doesn't need a live DB."""

    def test_preflight_allows_x_api_key(self):
        client = TestClient(real_app)
        resp = client.options(
            "/api/v1/search/context",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-api-key",
            },
        )
        assert resp.status_code == 200
        assert "x-api-key" in resp.headers["access-control-allow-headers"].lower()
