"""
Unit tests for app/api/auth.py: the origin_allowed pure function, and
require_api_key against a fake asyncpg connection (following test_ingestion.
py's FakeConn convention - no real DB in unit tests), plus an end-to-end
wiring test on a throwaway FastAPI app (following test_middleware.py's
pattern) proving the dependency actually rejects/accepts requests correctly
when mounted on a real route.
"""
import uuid
from datetime import UTC, datetime

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.api.auth import hash_key, origin_allowed, require_api_key
from app.api.dependencies import get_db


class TestOriginAllowed:
    def test_matching_origin_is_allowed(self):
        assert origin_allowed("http://localhost:3000", ["http://localhost:3000"]) is True

    def test_non_matching_origin_is_rejected(self):
        assert origin_allowed("http://evil.example", ["http://localhost:3000"]) is False

    def test_no_origin_header_is_rejected(self):
        assert origin_allowed(None, ["http://localhost:3000"]) is False

    def test_no_allowlist_configured_is_rejected(self):
        assert origin_allowed("http://localhost:3000", None) is False
        assert origin_allowed("http://localhost:3000", []) is False


class FakeAuthConn:
    """Returns a canned api_keys row (or None) regardless of the hash
    queried - each test controls the row directly, no real hashing/DB
    round-trip needed to exercise require_api_key's branching."""

    def __init__(self, row: dict | None):
        self.row = row

    async def fetchrow(self, sql, *args):
        assert "FROM api_keys WHERE key_hash" in sql
        return dict(self.row) if self.row is not None else None


def _key_row(**overrides) -> dict:
    defaults = dict(
        id=1, key_type="secret", label="Test key",
        allowed_origins=None, rate_limit_per_minute=1000, revoked_at=None,
    )
    defaults.update(overrides)
    return defaults


def _build_test_app(row: dict | None) -> FastAPI:
    app = FastAPI()

    async def fake_get_db():
        yield FakeAuthConn(row)

    app.dependency_overrides[get_db] = fake_get_db

    @app.get("/protected")
    async def protected(key=Depends(require_api_key)):
        return {"key_id": key.id, "key_type": key.key_type}

    return app


class TestRequireApiKeyUnit:
    async def test_missing_header_raises_401(self):
        scope = {"type": "http", "headers": [], "client": ("127.0.0.1", 1234)}
        request = Request(scope)
        with pytest.raises(HTTPException) as exc_info:
            await require_api_key(request, conn=FakeAuthConn(None))
        assert exc_info.value.status_code == 401

    async def test_unknown_key_raises_401(self):
        scope = {
            "type": "http",
            "headers": [(b"x-api-key", b"sk_live_bogus")],
            "client": ("127.0.0.1", 1234),
        }
        request = Request(scope)
        with pytest.raises(HTTPException) as exc_info:
            await require_api_key(request, conn=FakeAuthConn(None))
        assert exc_info.value.status_code == 401

    async def test_revoked_key_raises_401(self):
        scope = {
            "type": "http",
            "headers": [(b"x-api-key", b"sk_live_revoked")],
            "client": ("127.0.0.1", 1234),
        }
        request = Request(scope)
        row = _key_row(revoked_at=datetime.now(UTC))
        with pytest.raises(HTTPException) as exc_info:
            await require_api_key(request, conn=FakeAuthConn(row))
        assert exc_info.value.status_code == 401

    async def test_secret_key_bypasses_origin_check(self):
        scope = {
            "type": "http",
            "headers": [(b"x-api-key", b"sk_live_ok")],
            "client": ("127.0.0.1", 1234),
        }
        request = Request(scope)
        row = _key_row(key_type="secret", allowed_origins=None, rate_limit_per_minute=100000)
        ctx = await require_api_key(request, conn=FakeAuthConn(row))
        assert ctx.key_type == "secret"

    async def test_publishable_key_with_disallowed_origin_raises_403(self):
        scope = {
            "type": "http",
            "headers": [(b"x-api-key", b"pk_live_ok"), (b"origin", b"http://evil.example")],
            "client": ("127.0.0.1", 1234),
        }
        request = Request(scope)
        row = _key_row(key_type="publishable", allowed_origins=["http://localhost:3000"])
        with pytest.raises(HTTPException) as exc_info:
            await require_api_key(request, conn=FakeAuthConn(row))
        assert exc_info.value.status_code == 403

    async def test_publishable_key_with_allowed_origin_succeeds(self):
        scope = {
            "type": "http",
            "headers": [(b"x-api-key", b"pk_live_ok"), (b"origin", b"http://localhost:3000")],
            "client": ("127.0.0.1", 1234),
        }
        request = Request(scope)
        row = _key_row(
            id=2, key_type="publishable", allowed_origins=["http://localhost:3000"],
            rate_limit_per_minute=100000,
        )
        ctx = await require_api_key(request, conn=FakeAuthConn(row))
        assert ctx.key_type == "publishable"
        assert ctx.id == 2

    async def test_rate_limit_exceeded_raises_429(self):
        scope = {
            "type": "http",
            "headers": [(b"x-api-key", b"sk_live_ratelimited")],
            "client": ("127.0.0.1", 1234),
        }
        request = Request(scope)
        # Unique key id per test run so the rate-limit bucket registry
        # (a module-level global) can't leak state from another test.
        row = _key_row(id=int(uuid.uuid4().int % 1_000_000_000), rate_limit_per_minute=1)
        conn = FakeAuthConn(row)
        assert (await require_api_key(request, conn=conn)) is not None
        with pytest.raises(HTTPException) as exc_info:
            await require_api_key(request, conn=conn)
        assert exc_info.value.status_code == 429


class TestHashKey:
    def test_deterministic(self):
        assert hash_key("same-input") == hash_key("same-input")

    def test_different_inputs_differ(self):
        assert hash_key("a") != hash_key("b")

    def test_never_returns_the_raw_key(self):
        assert hash_key("my-secret-key") != "my-secret-key"


class TestRequireApiKeyEndToEnd:
    def test_missing_key_is_rejected_through_the_real_app(self):
        client = TestClient(_build_test_app(None))
        resp = client.get("/protected")
        assert resp.status_code == 401

    def test_valid_key_reaches_the_route_through_the_real_app(self):
        row = _key_row(id=99, rate_limit_per_minute=100000)
        client = TestClient(_build_test_app(row))
        resp = client.get("/protected", headers={"X-API-Key": "sk_live_whatever"})
        assert resp.status_code == 200
        assert resp.json() == {"key_id": 99, "key_type": "secret"}
