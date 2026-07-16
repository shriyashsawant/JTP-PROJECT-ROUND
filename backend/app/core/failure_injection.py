"""
AuraMatch AI - Failure Injection Middleware
Simulates failures for chaos engineering: artificial latency, random errors,
and connection drops. Only active when `failure_injection` is in the
FEATURE_FLAGS env var — completely inert in production by default.

This catches the "slow-not-down" failure mode that circuit breakers don't
address: if Groq is slow (2.9s every call, never timing out), the circuit
breaker never trips (no failures), but every search pays a ~3s latency tax.
The middleware can simulate this exact scenario.
"""

import asyncio
import logging
import random

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings

logger = logging.getLogger(__name__)

# Per-route failure profiles: (latency_mean_ms, latency_std_ms, error_rate)
# Keyed by URL path prefix, matched on full segments to avoid false positives
# (e.g. /api/v1/searchimage must not match the /api/v1/search profile).
_FAILURE_PROFILES: dict[str, tuple[float, float, float]] = {
    "/api/v1/search": (200, 50, 0.05),        # 5% error rate, 200±50ms latency
    "/api/v1/events": (50, 20, 0.01),          # 1% error rate
    "/api/v1/classify": (100, 30, 0.02),       # 2% error rate
}


class FailureInjectionMiddleware(BaseHTTPMiddleware):
    """Middleware that injects artificial latency and errors for chaos testing.

    Enabled via `feature_flags=failure_injection` in the .env file.
    When enabled, applies per-route failure profiles: random latency
    from a normal distribution + random HTTP 500/503 errors.

    Completely inert (zero overhead) when the feature flag is not set:
    the `dispatch` method calls `await call_next(request)` immediately
    without any branching logic."""

    async def dispatch(self, request: Request, call_next):
        if "failure_injection" not in settings.feature_flags_set:
            return await call_next(request)

        profile = self._match_profile(request.url.path)
        if profile is None:
            return await call_next(request)

        latency_ms, latency_std, error_rate = profile

        # Inject artificial latency — must use asyncio.sleep so the event loop
        # is not blocked while we wait.
        delay = max(0, random.gauss(latency_ms, latency_std)) / 1000.0
        if delay > 0:
            await asyncio.sleep(delay)
            logger.debug(
                "failure_injection_latency",
                path=request.url.path,
                latency_ms=round(delay * 1000),
            )

        # Inject random errors
        if random.random() < error_rate:
            status = random.choice([500, 502, 503])
            logger.info(
                "failure_injection_error",
                path=request.url.path,
                status=status,
                latency_ms=round(delay * 1000),
            )
            return JSONResponse(
                status_code=status,
                content={"detail": "Simulated failure (chaos testing)"},
            )

        return await call_next(request)

    def _match_profile(self, path: str) -> tuple[float, float, float] | None:
        for prefix, profile in _FAILURE_PROFILES.items():
            # Match on full path segments to avoid false positives
            # (e.g. /api/v1/searchimage must not match /api/v1/search).
            if path == prefix or path.startswith(prefix + "/"):
                return profile
        return None
