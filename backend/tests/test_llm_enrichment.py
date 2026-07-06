"""
Unit tests for llm_enrichment.py's fail-safe behavior and its circuit-breaker
wiring around the Groq call. Never hits the real network - `_call_groq` is
monkeypatched throughout.
"""
import app.services.llm_enrichment as llm_enrichment
from app.services.circuit_breaker import CircuitBreaker
from app.services.llm_enrichment import enhance_with_llm


async def test_returns_none_without_api_key(monkeypatch):
    monkeypatch.setattr(llm_enrichment.settings, "groq_api_key", "")
    assert await enhance_with_llm("query", [{"id": 1}], 5) is None


async def test_returns_none_with_no_candidates(monkeypatch):
    monkeypatch.setattr(llm_enrichment.settings, "groq_api_key", "fake-key")
    assert await enhance_with_llm("query", [], 5) is None


class TestCircuitBreakerIntegration:
    def setup_method(self):
        # Fresh breaker per test - the real module uses a shared singleton,
        # which would otherwise leak trip state between test cases.
        llm_enrichment._groq_breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=10.0)

    async def test_repeated_groq_failures_trip_the_breaker_and_stop_calling_it(self, monkeypatch):
        monkeypatch.setattr(llm_enrichment.settings, "groq_api_key", "fake-key")
        calls = 0

        async def _always_fails(prompt):
            nonlocal calls
            calls += 1
            raise RuntimeError("groq is down")

        monkeypatch.setattr(llm_enrichment, "_call_groq", _always_fails)
        candidates = [{"id": 1, "brand": "A", "perfume": "B"}]

        # First 2 calls actually hit (failing) _call_groq and trip the breaker.
        assert await enhance_with_llm("query", candidates, 1) is None
        assert await enhance_with_llm("query", candidates, 1) is None
        assert calls == 2
        assert llm_enrichment._groq_breaker.state == "open"

        # Breaker is now open - subsequent calls must short-circuit without
        # ever invoking _call_groq again (no repeated timeout tax).
        assert await enhance_with_llm("query", candidates, 1) is None
        assert calls == 2

    async def test_success_after_recovery_keeps_calls_flowing(self, monkeypatch):
        monkeypatch.setattr(llm_enrichment.settings, "groq_api_key", "fake-key")

        async def _succeeds(prompt):
            return {"results": [{"id": 1, "explanation": "Great pick."}]}

        monkeypatch.setattr(llm_enrichment, "_call_groq", _succeeds)
        candidates = [{"id": 1, "brand": "A", "perfume": "B", "match_score": 90}]

        result = await enhance_with_llm("query", candidates, 1)
        assert result is not None
        assert result[0]["explanation"] == "Great pick."
        assert llm_enrichment._groq_breaker.state == "closed"
