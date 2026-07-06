import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.dependencies import close_db, get_db_pool
from app.api.routes_dupe import router as dupe_router
from app.api.routes_search import router as search_router
from app.core.config import settings
from app.core.logging_config import request_id_var, setup_logging
from app.services.intent_detector import eager_init_scenario_embeddings
from app.services.llm_enrichment import close_http_client
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


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Assigns a request ID (also returned as X-Request-ID, so a client-reported
    error can be traced back to a specific server-side log line) and logs one
    access-log line per request with method/path/status/duration. The ID is
    stashed in a ContextVar rather than just a local variable so every log
    emitted deeper in the call stack during this request - route handlers,
    services - is automatically tagged with it too (see RequestIdFilter)."""
    request_id = uuid.uuid4().hex[:12]
    token = request_id_var.set(request_id)
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception("%s %s -> 500 (%.1fms)", request.method, request.url.path, duration_ms)
        request_id_var.reset(token)
        raise

    duration_ms = (time.perf_counter() - start) * 1000
    logger.info("%s %s -> %d (%.1fms)", request.method, request.url.path, response.status_code, duration_ms)
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
