"""
AuraMatch AI - Rate Limiter
Token bucket, in-memory, single-process - the backend runs as one worker in
the current docker-compose setup, so an in-process dict is correct today;
moving to a shared store (Redis) would only become necessary if this ever
becomes multi-process/multi-instance, which it isn't yet. Chosen over fixed/
sliding window because it avoids the classic 2x-burst-at-a-window-boundary
flaw for barely more code, and mirrors CircuitBreaker's existing concurrency
pattern (app/services/circuit_breaker.py) - a lock-guarded class per unit of
state, not one global lock serializing unrelated callers.
"""
import asyncio
import time


class RateLimiter:
    """One bucket. Refills continuously at `refill_rate` tokens/sec up to
    `capacity`, so a burst up to the full capacity is always allowed as long
    as enough time has passed since it was last drawn down."""

    def __init__(self, capacity: float, refill_rate: float):
        self._capacity = capacity
        self._refill_rate = refill_rate
        self._tokens = capacity
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def try_consume(self, tokens: float = 1.0) -> bool:
        """True if `tokens` were available and consumed; False (caller should
        reject with 429) if the bucket didn't have enough."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self._capacity, self._tokens + elapsed * self._refill_rate)
            self._last_refill = now
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False


# Keyed by an arbitrary tuple (see app.api.auth: (api_key_id, client_ip) for
# publishable keys since one publishable key is shared by every real visitor
# of the frontend - a scraped-key abuser hammering it shouldn't throttle out
# every legitimate user sharing that same key - vs. just (api_key_id,) for
# secret keys, since one partner = one bucket and their IP may legitimately
# rotate). Guards *creation* of a new bucket only - each bucket's own lock
# handles the actual token check/consume, so concurrent requests against
# *different* keys don't serialize on one global lock.
_buckets: dict[tuple, RateLimiter] = {}
_registry_lock = asyncio.Lock()


async def _get_bucket(key: tuple, capacity: float, refill_rate: float) -> RateLimiter:
    bucket = _buckets.get(key)
    if bucket is None:
        async with _registry_lock:
            bucket = _buckets.get(key)
            if bucket is None:
                bucket = RateLimiter(capacity, refill_rate)
                _buckets[key] = bucket
    return bucket


async def check_rate_limit(key: tuple, requests_per_minute: int) -> bool:
    """True if the request is allowed, False if the bucket is exhausted.
    Capacity = requests_per_minute (a full minute's worth as an allowed
    burst), refilling continuously at requests_per_minute/60 tokens/sec -
    the simplest sensible mapping from an "N requests per minute" rate limit
    to a continuously-refilling bucket."""
    bucket = await _get_bucket(key, capacity=requests_per_minute, refill_rate=requests_per_minute / 60.0)
    return await bucket.try_consume()
