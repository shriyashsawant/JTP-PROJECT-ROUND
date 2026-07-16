"""Unit tests for the token-bucket rate limiter (app/services/rate_limiter.py)."""
import asyncio
import uuid

from app.services.rate_limiter import RateLimiter, check_rate_limit


def _unique_key(*parts: str) -> tuple:
    # check_rate_limit's bucket registry is a module-level global that
    # persists for the whole test session - a fresh uuid per test avoids any
    # possibility of one test's bucket state leaking into another's.
    return (uuid.uuid4().hex, *parts)


class TestRateLimiterTokenConsumption:
    async def test_allows_requests_up_to_capacity(self):
        limiter = RateLimiter(capacity=3, refill_rate=0.0)  # no refill during the test
        assert (await limiter.try_consume())[0] is True
        assert (await limiter.try_consume())[0] is True
        assert (await limiter.try_consume())[0] is True

    async def test_rejects_once_capacity_is_exhausted(self):
        limiter = RateLimiter(capacity=2, refill_rate=0.0)
        assert (await limiter.try_consume())[0] is True
        assert (await limiter.try_consume())[0] is True
        assert (await limiter.try_consume())[0] is False

    async def test_refills_over_time(self):
        # capacity=1, refill_rate=20/sec -> a token is back well within 0.1s
        limiter = RateLimiter(capacity=1, refill_rate=20.0)
        assert (await limiter.try_consume())[0] is True
        assert (await limiter.try_consume())[0] is False
        await asyncio.sleep(0.1)
        assert (await limiter.try_consume())[0] is True

    async def test_never_refills_past_capacity(self):
        limiter = RateLimiter(capacity=2, refill_rate=1000.0)
        await asyncio.sleep(0.05)  # would overflow capacity many times over if unclamped
        assert (await limiter.try_consume())[0] is True
        assert (await limiter.try_consume())[0] is True
        assert (await limiter.try_consume())[0] is False


class TestRateLimiterConcurrency:
    async def test_concurrent_consumers_never_exceed_capacity(self):
        # 20 concurrent callers, only 5 tokens available, no refill during the
        # test - exactly 5 should succeed regardless of scheduling order.
        limiter = RateLimiter(capacity=5, refill_rate=0.0)
        results = await asyncio.gather(*[limiter.try_consume() for _ in range(20)])
        assert sum(r[0] for r in results) == 5


class TestCheckRateLimit:
    async def test_different_keys_get_independent_buckets(self):
        # Exhaust one key's bucket; a different key must be unaffected.
        key_a, key_b = _unique_key("a"), _unique_key("b")
        for _ in range(5):
            await check_rate_limit(key_a, requests_per_minute=5)
        assert (await check_rate_limit(key_a, requests_per_minute=5))[0] is False
        assert (await check_rate_limit(key_b, requests_per_minute=5))[0] is True

    async def test_same_key_reuses_the_same_bucket(self):
        key = _unique_key("reuse")
        for _ in range(3):
            assert (await check_rate_limit(key, requests_per_minute=3))[0] is True
        assert (await check_rate_limit(key, requests_per_minute=3))[0] is False
