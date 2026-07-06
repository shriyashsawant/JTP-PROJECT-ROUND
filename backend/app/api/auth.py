"""
AuraMatch AI - API Authentication
Two-tier API key model (publishable vs secret) - see migration 0004_api_keys
for the full rationale. This dependency is the only place that distinguishes
them: validates the X-API-Key header against the hashed api_keys table,
enforces the Origin allowlist for publishable keys, and applies per-key rate
limiting before letting a request through to the actual route handler.
"""
import hashlib
from dataclasses import dataclass

from asyncpg.connection import Connection
from fastapi import Depends, HTTPException, Request

from app.api.dependencies import get_db
from app.services.rate_limiter import check_rate_limit


@dataclass
class ApiKeyContext:
    id: int
    key_type: str
    label: str


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def origin_allowed(origin: str | None, allowed_origins: list[str] | None) -> bool:
    """Pure function so it's unit-testable independent of the dependency/DB.
    No allowlist configured, or no Origin header sent, means fail closed -
    a publishable key issued without ever specifying where it's meant to be
    used should never pass this check."""
    if not allowed_origins or not origin:
        return False
    return origin in allowed_origins


async def require_api_key(request: Request, conn: Connection = Depends(get_db)) -> ApiKeyContext:
    """Applied to the product routes (search/context, search/dupe, perfume
    detail) - not /health, which stays open (standard liveness-probe
    convention). Rejects with 401 (missing/invalid/revoked key), 403
    (publishable key used from a non-allowlisted Origin), or 429 (rate
    limit exceeded) before the route handler ever runs."""
    raw_key = request.headers.get("x-api-key")
    if not raw_key:
        raise HTTPException(401, detail="Missing X-API-Key header")

    row = await conn.fetchrow(
        """
        SELECT id, key_type, label, allowed_origins, rate_limit_per_minute, revoked_at
        FROM api_keys WHERE key_hash = $1
        """,
        hash_key(raw_key),
    )
    if row is None or row["revoked_at"] is not None:
        raise HTTPException(401, detail="Invalid or revoked API key")

    bucket_key: tuple
    if row["key_type"] == "publishable":
        origin = request.headers.get("origin")
        if not origin_allowed(origin, row["allowed_origins"]):
            raise HTTPException(403, detail="Origin not allowed for this API key")
        # One publishable key is shared by every real visitor of the
        # frontend - bucket by (key, client_ip) so a scraped-key abuser
        # hammering it doesn't throttle out every legitimate user sharing
        # that same key (see app/services/rate_limiter.py).
        client_ip = request.client.host if request.client else "unknown"
        bucket_key = (row["id"], client_ip)
    else:
        # One secret key = one partner = one bucket; a partner's IP may
        # legitimately rotate, so it isn't part of the key.
        bucket_key = (row["id"],)

    if not await check_rate_limit(bucket_key, row["rate_limit_per_minute"]):
        raise HTTPException(429, detail="Rate limit exceeded")

    return ApiKeyContext(id=row["id"], key_type=row["key_type"], label=row["label"])
