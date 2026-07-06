"""
AuraMatch AI - Circuit Breaker
Generic async circuit breaker for wrapping unreliable external calls (currently
just the optional Groq re-ranking call - see llm_enrichment.py). Standard
three-state design:

  CLOSED     -> calls go through normally. N consecutive failures trips to OPEN.
  OPEN       -> calls are rejected immediately (no network attempt) until the
                recovery timeout elapses, then one trial call is let through (HALF_OPEN).
  HALF_OPEN  -> exactly one trial call is in flight. Success closes the breaker
                (resets the failure count); failure re-opens it and restarts the timer.

The point: once an external dependency is genuinely down, every caller stops
paying its full timeout on every single request - failures become an
immediate, cheap rejection instead of a repeated slow timeout, while still
probing for recovery periodically instead of staying open forever.
"""
import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


class CircuitBreakerOpenError(Exception):
    """Raised instead of attempting the wrapped call while the breaker is OPEN."""


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0):
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._state = "closed"
        self._failures = 0
        self._opened_at: float | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> str:
        return self._state

    async def _acquire(self) -> bool:
        """True if the caller may proceed. False means short-circuit to the
        fallback without attempting the call at all."""
        async with self._lock:
            if self._state == "open":
                if self._opened_at is not None and (time.monotonic() - self._opened_at) >= self._recovery_timeout:
                    self._state = "half_open"
                    return True
                return False
            # If half_open, a trial call is already in flight - reject
            # concurrent callers rather than letting several probe requests
            # through at once while recovery is still unconfirmed.
            return self._state != "half_open"

    async def _record_success(self) -> None:
        async with self._lock:
            self._state = "closed"
            self._failures = 0
            self._opened_at = None

    async def _record_failure(self) -> None:
        async with self._lock:
            if self._state == "half_open":
                # The trial call failed - stay open, restart the recovery window.
                self._state = "open"
                self._opened_at = time.monotonic()
                return
            self._failures += 1
            if self._failures >= self._failure_threshold:
                self._state = "open"
                self._opened_at = time.monotonic()

    async def call(self, func: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
        """Runs `func(*args, **kwargs)` if the breaker allows it. Raises
        CircuitBreakerOpenError without calling `func` at all if OPEN (or if a
        HALF_OPEN trial is already in flight); re-raises whatever `func`
        raises on a real failure, after recording it."""
        if not await self._acquire():
            raise CircuitBreakerOpenError()
        try:
            result = await func(*args, **kwargs)
        except Exception:
            await self._record_failure()
            raise
        else:
            await self._record_success()
            return result
