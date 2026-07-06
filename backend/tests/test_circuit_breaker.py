"""Unit tests for the generic async circuit breaker (circuit_breaker.py)."""
import asyncio

import pytest

from app.services.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError


async def _ok():
    return "ok"


async def _boom():
    raise RuntimeError("boom")


class TestCircuitBreakerClosedState:
    async def test_starts_closed_and_calls_pass_through(self):
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0)
        assert breaker.state == "closed"
        assert await breaker.call(_ok) == "ok"
        assert breaker.state == "closed"

    async def test_failures_below_threshold_stay_closed(self):
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0)
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await breaker.call(_boom)
        assert breaker.state == "closed"

    async def test_a_success_does_not_reset_an_in_progress_failure_streak_incorrectly(self):
        # Sanity check: success fully resets the counter, not just decrements it.
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0)
        with pytest.raises(RuntimeError):
            await breaker.call(_boom)
        await breaker.call(_ok)
        with pytest.raises(RuntimeError):
            await breaker.call(_boom)
        with pytest.raises(RuntimeError):
            await breaker.call(_boom)
        # Only 2 consecutive failures since the success reset the streak.
        assert breaker.state == "closed"


class TestCircuitBreakerTripping:
    async def test_trips_open_after_failure_threshold(self):
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0)
        for _ in range(3):
            with pytest.raises(RuntimeError):
                await breaker.call(_boom)
        assert breaker.state == "open"

    async def test_open_breaker_rejects_immediately_without_calling_func(self):
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=10.0)
        with pytest.raises(RuntimeError):
            await breaker.call(_boom)
        assert breaker.state == "open"

        calls = 0

        async def _tracked():
            nonlocal calls
            calls += 1
            return "should not run"

        with pytest.raises(CircuitBreakerOpenError):
            await breaker.call(_tracked)
        assert calls == 0


class TestCircuitBreakerRecovery:
    async def test_transitions_to_half_open_after_recovery_timeout(self):
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0.05)
        with pytest.raises(RuntimeError):
            await breaker.call(_boom)
        assert breaker.state == "open"

        await asyncio.sleep(0.06)
        assert await breaker.call(_ok) == "ok"
        assert breaker.state == "closed"

    async def test_failed_trial_reopens_and_restarts_the_timer(self):
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0.05)
        with pytest.raises(RuntimeError):
            await breaker.call(_boom)
        await asyncio.sleep(0.06)

        # The half-open trial itself fails - breaker should re-open, not close.
        with pytest.raises(RuntimeError):
            await breaker.call(_boom)
        assert breaker.state == "open"

        # Immediately after the failed trial, still within the new recovery
        # window - must reject without attempting the call.
        with pytest.raises(CircuitBreakerOpenError):
            await breaker.call(_ok)

    async def test_concurrent_calls_while_open_all_reject_without_racing(self):
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=10.0)
        with pytest.raises(RuntimeError):
            await breaker.call(_boom)
        assert breaker.state == "open"

        results = await asyncio.gather(
            *[breaker.call(_ok) for _ in range(5)], return_exceptions=True,
        )
        assert all(isinstance(r, CircuitBreakerOpenError) for r in results)
