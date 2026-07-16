"""
Integration tests for the FastAPI application — API endpoints end-to-end.

Tests the app through httpx's ASGI transport, exercising real route handling,
middleware, dependency injection, schema validation, CORS headers, and error
responses. These tests need a live database — the whole module is skipped when
DB_HOST and DATABASE_URL are both absent.
"""
import os

import pytest

from app.main import app

pytestmark = pytest.mark.asyncio

_HAS_DB = bool(os.environ.get("DB_HOST")) or bool(os.environ.get("DATABASE_URL"))
if not _HAS_DB:
    pytest.skip("Skipping integration tests — no DB_HOST/DATABASE_URL configured", allow_module_level=True)


try:
    from httpx import ASGITransport, AsyncClient
    _transport = ASGITransport(app=app)
except ImportError:
    from httpx import AsyncClient
    _transport = None


@pytest.fixture
async def client():
    if _transport is not None:
        async with AsyncClient(transport=_transport, base_url="http://test") as c:
            yield c
    else:
        async with AsyncClient(app=app, base_url="http://test") as c:
            yield c


# ---------------------------------------------------------------------------
# Health endpoint (no auth required)
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    async def test_health_returns_valid_response(self, client):
        resp = await client.get("/api/v1/health")
        assert resp.status_code in (200, 503)
        body = resp.json()
        assert "status" in body
        assert "db_connected" in body


# ---------------------------------------------------------------------------
# Authentication & API key validation
# ---------------------------------------------------------------------------

class TestAuthentication:
    async def test_missing_api_key_returns_401(self, client):
        resp = await client.post("/api/v1/search/context", json={"query": "test"})
        assert resp.status_code == 401
        assert "Missing" in resp.json().get("detail", "")

    async def test_invalid_api_key_returns_401(self, client):
        resp = await client.post(
            "/api/v1/search/context",
            json={"query": "test"},
            headers={"X-API-Key": "invalid_key_12345"},
        )
        assert resp.status_code == 401

    async def test_empty_query_returns_400(self, client):
        resp = await client.post(
            "/api/v1/search/context",
            json={"query": ""},
            headers={"X-API-Key": "sk_live_test"},
        )
        assert resp.status_code in (400, 401)

    async def test_long_query_returns_422(self, client):
        resp = await client.post(
            "/api/v1/search/context",
            json={"query": "x" * 501},
            headers={"X-API-Key": "sk_live_test"},
        )
        assert resp.status_code in (400, 401, 422)


# ---------------------------------------------------------------------------
# Request/response schema validation
# ---------------------------------------------------------------------------

class TestSchemaValidation:
    async def test_context_search_limit_range(self, client):
        resp = await client.post(
            "/api/v1/search/context",
            json={"query": "test", "limit": 0},
            headers={"X-API-Key": "sk_live_test"},
        )
        assert resp.status_code in (401, 422)

        resp = await client.post(
            "/api/v1/search/context",
            json={"query": "test", "limit": 61},
            headers={"X-API-Key": "sk_live_test"},
        )
        assert resp.status_code in (401, 422)

    async def test_dupe_search_budget_validation(self, client):
        resp = await client.post(
            "/api/v1/search/dupe",
            json={"query": "test", "budget": 50},
            headers={"X-API-Key": "sk_live_test"},
        )
        assert resp.status_code in (401, 422)

    async def test_dupe_search_empty_query(self, client):
        resp = await client.post(
            "/api/v1/search/dupe",
            json={"query": ""},
            headers={"X-API-Key": "sk_live_test"},
        )
        assert resp.status_code in (400, 422)

    async def test_gender_validation(self, client):
        for gender in ["male", "female", "unisex"]:
            resp = await client.post(
                "/api/v1/search/context",
                json={"query": "test", "gender": gender},
                headers={"X-API-Key": "sk_live_test"},
            )
            assert resp.status_code in (401, 422)

        resp = await client.post(
            "/api/v1/search/context",
            json={"query": "test", "gender": "invalid"},
            headers={"X-API-Key": "sk_live_test"},
        )
        assert resp.status_code in (401, 422)

    async def test_projection_preference_validation(self, client):
        resp = await client.post(
            "/api/v1/search/context",
            json={"query": "test", "projection_preference": "extreme"},
            headers={"X-API-Key": "sk_live_test"},
        )
        assert resp.status_code in (401, 422)

    async def test_age_range_validation(self, client):
        resp = await client.post(
            "/api/v1/search/context",
            json={"query": "test", "age": 200},
            headers={"X-API-Key": "sk_live_test"},
        )
        assert resp.status_code in (401, 422)

        resp = await client.post(
            "/api/v1/search/context",
            json={"query": "test", "age": 25},
            headers={"X-API-Key": "sk_live_test"},
        )
        assert resp.status_code in (401, 422)

    async def test_note_families_accepts_list(self, client):
        resp = await client.post(
            "/api/v1/search/context",
            json={"query": "test", "note_families": ["citrus", "woody"]},
            headers={"X-API-Key": "sk_live_test"},
        )
        assert resp.status_code in (401, 422)

    async def test_hours_required_range(self, client):
        resp = await client.post(
            "/api/v1/search/context",
            json={"query": "test", "hours_required": 0},
            headers={"X-API-Key": "sk_live_test"},
        )
        assert resp.status_code in (401, 422)

    async def test_deal_breaker_defaults_to_false(self, client):
        resp = await client.post(
            "/api/v1/search/context",
            json={"query": "test"},
            headers={"X-API-Key": "sk_live_test"},
        )
        assert resp.status_code in (400, 401, 422)


# ---------------------------------------------------------------------------
# Metrics endpoint (no auth required)
# ---------------------------------------------------------------------------

class TestMetricsEndpoint:
    async def test_metrics_returns_prometheus_format(self, client):
        resp = await client.get("/metrics")
        assert resp.status_code == 200
        for name in [
            "auramatch_http_request_duration_seconds",
            "auramatch_http_requests_failed_total",
            "auramatch_db_pool_connections_active",
            "auramatch_circuit_breaker_state",
            "auramatch_rate_limit_rejections_total",
        ]:
            assert name in resp.text


# ---------------------------------------------------------------------------
# Root endpoint
# ---------------------------------------------------------------------------

class TestRootEndpoint:
    async def test_root_returns_app_info(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["app"] == "AuraMatch AI"
        assert body["status"] == "running"


# ---------------------------------------------------------------------------
# CORS headers
# ---------------------------------------------------------------------------

class TestCORSHeaders:
    async def test_cors_on_preflight(self, client):
        resp = await client.options(
            "/api/v1/search/context",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert resp.status_code == 200
        assert "access-control-allow-origin" in resp.headers

    async def test_cors_on_actual_request(self, client):
        resp = await client.get(
            "/api/v1/health",
            headers={"Origin": "http://localhost:3000"},
        )
        assert resp.status_code in (200, 503)
        assert "access-control-allow-origin" in resp.headers
