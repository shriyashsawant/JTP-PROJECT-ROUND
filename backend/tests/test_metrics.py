"""Unit tests for app/core/metrics.py."""
from app.core.metrics import circuit_breaker_state, set_circuit_breaker_gauge


def _gauge_value(breaker: str) -> float:
    for family in circuit_breaker_state.collect():
        for s in family.samples:
            if s.name == "auramatch_circuit_breaker_state" and s.labels == {"breaker": breaker}:
                return s.value
    return None


class TestSetCircuitBreakerGauge:
    def test_closed_maps_to_zero(self):
        set_circuit_breaker_gauge("test_closed", "closed")
        assert _gauge_value("test_closed") == 0

    def test_open_maps_to_one(self):
        set_circuit_breaker_gauge("test_open", "open")
        assert _gauge_value("test_open") == 1

    def test_half_open_maps_to_two(self):
        set_circuit_breaker_gauge("test_half_open", "half_open")
        assert _gauge_value("test_half_open") == 2

    def test_unknown_state_maps_to_negative_one(self):
        # Defensive: CircuitBreaker.state only ever returns one of the three
        # real states, but this gauge shouldn't silently misreport an
        # unrecognized value as "closed" (0) if that ever changes.
        set_circuit_breaker_gauge("test_unknown", "something_new")
        assert _gauge_value("test_unknown") == -1
