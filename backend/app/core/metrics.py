"""
AuraMatch AI - Observability Metrics
Prometheus-format metrics, scoped deliberately small per the architecture
roadmap (see documentation/SYSTEM_ARCHITECTURE.md §6 and
documentation/TESTING_AND_OBSERVABILITY.md §5): request latency, error
rates, DB pool utilization, circuit-breaker state, rate-limit rejections -
not a full tracing mesh, which only earns its keep across many services/
hops and this system has one backend service today.

Metric objects are created once at import time (Prometheus client
convention - a Counter/Histogram/Gauge is a long-lived registry entry, not
something to recreate per request) and updated from the two places that
actually observe these events: the request-logging middleware (main.py) for
HTTP latency/failures, and app/api/auth.py for rate-limit rejections. The
DB-pool and circuit-breaker gauges are *state*, not events - they're read
fresh at scrape time (inside the /metrics handler itself) rather than
pushed continuously, since polling them once per scrape is simpler and
cheaper than keeping a gauge in sync on every pool acquire/release.
"""
from prometheus_client import Counter, Gauge, Histogram

http_request_duration_seconds = Histogram(
    "auramatch_http_request_duration_seconds",
    "HTTP request latency in seconds, by route and response status",
    ["route", "status"],
)

http_requests_failed_total = Counter(
    "auramatch_http_requests_failed_total",
    "HTTP requests that raised an unhandled exception (5xx), by route",
    ["route"],
)

db_pool_connections_active = Gauge(
    "auramatch_db_pool_connections_active",
    "asyncpg connection pool utilization",
    ["state"],  # "active" or "idle"
)

circuit_breaker_state = Gauge(
    "auramatch_circuit_breaker_state",
    "Groq circuit breaker state (0=closed, 1=open, 2=half_open)",
    ["breaker"],
)

rate_limit_rejections_total = Counter(
    "auramatch_rate_limit_rejections_total",
    "429 rate-limit rejections, by API key type",
    ["key_type"],
)

# Matches CircuitBreaker.state's own string values (circuit_breaker.py) -
# kept here rather than on the class itself since this mapping is purely an
# observability concern, not part of the breaker's actual behavior.
_BREAKER_STATE_VALUES = {"closed": 0, "open": 1, "half_open": 2}


def set_circuit_breaker_gauge(breaker_name: str, state: str) -> None:
    circuit_breaker_state.labels(breaker=breaker_name).set(_BREAKER_STATE_VALUES.get(state, -1))
