"""
Tests for the request-logging middleware in main.py, in isolation from the
real app (which requires a live Postgres connection at startup). Mounts the
middleware function directly onto a throwaway FastAPI app instead.
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

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

    return app


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
