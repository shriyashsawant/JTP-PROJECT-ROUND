import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.dependencies import close_db, get_db_pool
from app.api.routes_dupe import router as dupe_router
from app.api.routes_search import router as search_router
from app.core.config import settings
from app.core.logging_config import request_id_var, setup_logging
from app.core.metrics import (
    db_pool_connections_active,
    http_request_duration_seconds,
    http_requests_failed_total,
    set_circuit_breaker_gauge,
)
from app.services.intent_detector import eager_init_scenario_embeddings
from app.services.llm_enrichment import close_http_client, get_groq_breaker_state
from app.services.ml_engine import get_model

setup_logging()
logger = logging.getLogger("auramatch.access")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm up the DB pool and the embedding model at boot so the first real
    # user request doesn't pay for pool creation + a 4-6s cold model load.
    await get_db_pool()
    await asyncio.to_thread(get_model)
    await eager_init_scenario_embeddings()
    yield
    await close_db()
    await close_http_client()

app = FastAPI(
    title="AuraMatch AI",
    description="AI-Powered Fragrance Recommendation Engine",
    version="1.0.0",
    lifespan=lifespan,
)


def _route_template(request: Request) -> str:
    """The matched route's path TEMPLATE (e.g. "/api/v1/perfume/{perfume_id}"),
    not the resolved path with real values substituted in - using the latter
    as a metric label would give every distinct perfume ID its own label
    series, an unbounded-cardinality metric that gets worse forever as the
    catalog/traffic grows. Starlette sets `request.scope["route"]` once
    routing has matched (i.e. by the time `call_next` returns), so this is
    only ever called after that point. Falls back to the raw path for
    requests that never matched a route at all (a genuine 404)."""
    route = request.scope.get("route")
    return route.path if route is not None else request.url.path


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Assigns a request ID (also returned as X-Request-ID, so a client-reported
    error can be traced back to a specific server-side log line) and logs one
    access-log line per request with method/path/status/duration. The ID is
    stashed in a ContextVar rather than just a local variable so every log
    emitted deeper in the call stack during this request - route handlers,
    services - is automatically tagged with it too (see RequestIdFilter).

    Also records the two HTTP metrics from app/core/metrics.py - latency
    histogram and failure counter - here rather than per-route, since this
    is the one place every request (successful or not) already passes
    through exactly once."""
    request_id = uuid.uuid4().hex[:12]
    token = request_id_var.set(request_id)
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration = time.perf_counter() - start
        logger.exception("%s %s -> 500 (%.1fms)", request.method, request.url.path, duration * 1000)
        route = _route_template(request)
        http_requests_failed_total.labels(route=route).inc()
        http_request_duration_seconds.labels(route=route, status="500").observe(duration)
        request_id_var.reset(token)
        raise

    duration = time.perf_counter() - start
    logger.info("%s %s -> %d (%.1fms)", request.method, request.url.path, response.status_code, duration * 1000)
    http_request_duration_seconds.labels(route=_route_template(request), status=str(response.status_code)).observe(duration)
    response.headers["X-Request-ID"] = request_id
    request_id_var.reset(token)
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    # X-API-Key added for the third-party API auth layer (see auth.py) - the
    # frontend sends it on every request, and browsers preflight (OPTIONS)
    # any cross-origin request carrying a non-simple header like this one;
    # without it listed here, CORSMiddleware itself rejects the preflight
    # with 400 before the actual request is ever allowed through.
    allow_headers=["Content-Type", "X-API-Key"],
)

app.include_router(search_router)
app.include_router(dupe_router)

@app.get("/")
async def root():
    return {"app": "AuraMatch AI", "status": "running"}


@app.get("/metrics")
async def metrics():
    """Prometheus scrape target - see documentation/TESTING_AND_OBSERVABILITY.md
    §5. Deliberately unauthenticated (same convention as /health): a metrics
    endpoint is meant to be scraped by infrastructure, not called by product
    clients, and exposes no user data - only aggregate counters/gauges.

    The DB-pool and circuit-breaker gauges are refreshed here, at scrape
    time, rather than kept continuously in sync on every pool acquire/
    breaker transition - polling once per scrape is simpler and just as
    accurate for state that's cheap to read on demand."""
    pool = await get_db_pool()
    db_pool_connections_active.labels(state="active").set(pool.get_size() - pool.get_idle_size())
    db_pool_connections_active.labels(state="idle").set(pool.get_idle_size())
    set_circuit_breaker_gauge("groq", get_groq_breaker_state())
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
