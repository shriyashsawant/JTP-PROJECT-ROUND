"""
AuraMatch AI - FastAPI Dependencies
Connection pools (writer + optional read replica), A/B test assignment, and
lifespan management.
"""

import asyncio

import asyncpg
from fastapi import Request

from app.core.config import settings
from app.core.logging_config import request_id_var
from app.services.ab_testing import AbTest

# Writer pool (primary DB)
writer_pool = None
_writer_lock = asyncio.Lock()

# Reader pool (read replica — same as writer when DATABASE_READER_URL is unset)
reader_pool = None
_reader_lock = asyncio.Lock()


async def get_db_pool():
    """Get the writer pool — used for INSERT/UPDATE/DELETE and schema writes."""
    global writer_pool
    if writer_pool is None:
        async with _writer_lock:
            if writer_pool is None:
                writer_pool = await asyncpg.create_pool(
                    settings.database_url,
                    min_size=2,
                    max_size=10,
                )
    return writer_pool


async def get_reader_pool():
    """Get the reader pool — used for SELECT queries.

    If DATABASE_READER_URL is configured, this creates a separate pool
    pointing at the read replica. Otherwise falls back to the writer pool
    (single-node setup — no split-reader overhead).

    Callers that only read can use `get_reader_db()` instead to get a
    connection from whichever pool is available.
    """
    global reader_pool
    reader_url = getattr(settings, "database_reader_url", None) or getattr(settings, "DATABASE_READER_URL", None)
    if not reader_url:
        return await get_db_pool()

    if reader_pool is None:
        async with _reader_lock:
            if reader_pool is None:
                reader_pool = await asyncpg.create_pool(
                    reader_url,
                    min_size=2,
                    max_size=20,  # read replicas can handle more connections
                )
    return reader_pool


async def get_db():
    """Yields a writer connection (for reads and writes in the same request).
    Most request handlers use this — only explicit read-only operations
    should use `get_reader_db()`."""
    p = await get_db_pool()
    async with p.acquire() as conn:
        yield conn


async def get_reader_db():
    """Yields a read-only connection — use for SELECT-only operations.

    In a single-node setup this is identical to `get_db()`. When a read
    replica is configured (DATABASE_READER_URL in .env), SELECT queries
    go to the replica and mutations go to the writer.
    """
    p = await get_reader_pool()
    async with p.acquire() as conn:
        yield conn


async def close_db():
    """Close both writer and reader pools at shutdown."""
    global writer_pool, reader_pool
    if writer_pool:
        await writer_pool.close()
        writer_pool = None
    if reader_pool and reader_pool is not writer_pool:
        await reader_pool.close()
    reader_pool = None


async def get_ab_test(request: Request) -> AbTest:
    """FastAPI dependency that creates an AbTest instance from the request's
    X-Request-ID (set by main.py's request_logging_middleware into a ContextVar,
    so we read it from there rather than from request.headers which never
    receives it). Falls back to a hash of the client host + port for requests
    that somehow arrive before the middleware runs."""
    rid = request_id_var.get() or f"{request.client.host}:{request.client.port}" if request.client else "unknown"
    return AbTest(request_id=rid)
