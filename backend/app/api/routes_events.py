"""
AuraMatch AI - Feedback Events API
Collects implicit user signals (clicks, purchases, dismissals) for the
Bayesian weight optimizer, plus explanation ratings for the explanation
quality feedback signal. Fire-and-forget: never raises, never blocks
the response to the caller — always returns 202 Accepted.

The optimizer reads these events offline (daily batch), so durability is
nice-to-have but not critical: if the DB write fails, the request still
succeeds; the optimizer just sees one fewer data point.
"""

import asyncio
import logging

from asyncpg.connection import Connection
from fastapi import APIRouter, Depends

from app.api.auth import require_api_key
from app.api.dependencies import get_db, get_db_pool
from app.models.schemas import FeedbackEventRequest
from app.services.ml_engine import generate_document_embedding_async

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Events"])


@router.post("/events", status_code=202)
async def record_event(
    req: FeedbackEventRequest,
    conn: Connection = Depends(get_db),
    _key=Depends(require_api_key),
):
    """Record a user interaction event (click, purchase, or dismiss).

    All fields except `event_type`, `perfume_id`, and `query_id` are
    optional — the optimizer works fine with just those three. Extra
    fields (match_score, position, dwell_ms, variant) improve the
    optimizer's signal but are never required.
    """
    try:
        await conn.execute(
            """
            INSERT INTO feedback_events
                (event_type, perfume_id, query_id, query_text, session_id,
                 variant, match_score, position, dwell_ms)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            req.event_type,
            req.perfume_id,
            req.query_id,
            req.query_text,
            req.session_id,
            req.variant,
            req.match_score,
            req.position,
            req.dwell_ms,
        )
    except Exception:
        logger.warning("Failed to persist feedback event", exc_info=True)


@router.post("/events/explanation-rating", status_code=202)
async def rate_explanation(
    perfume_id: int,
    rating: int = 1,
    query_id: str = "",
    session_id: str | None = None,
    conn: Connection = Depends(get_db),
    _key=Depends(require_api_key),
):
    """Rate whether an explanation was helpful.

    rating: 0 = not helpful, 1 = helpful (only these two values accepted).
    Stored as dedicated event types `explanation_helpful` / `explanation_unhelpful`
    so they don't pollute the optimizer's click/purchase/dismiss signal.

    Anonymized — no user identity stored, just aggregate counts per perfume
    for evaluating explanation quality over time."""
    if rating not in (0, 1):
        logger.warning("invalid_explanation_rating", rating=rating)
        return

    try:
        # Verify perfume exists — log a warning if not, but still fire-and-forget
        exists = await conn.fetchval("SELECT 1 FROM perfumes WHERE id = $1", perfume_id)
        if not exists:
            logger.warning("explanation_rating_nonexistent_perfume", perfume_id=perfume_id)
            return

        event_type = "explanation_helpful" if rating else "explanation_unhelpful"
        await conn.execute(
            """
            INSERT INTO feedback_events
                (event_type, perfume_id, query_id, query_text, session_id,
                 variant, match_score, position, dwell_ms)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            event_type,
            perfume_id,
            query_id,
            "",
            session_id,
            None,
            None,
            None,
            None,
        )
    except Exception:
        logger.warning("Failed to persist explanation rating", exc_info=True)


@router.post("/admin/re-embed", status_code=202)
async def trigger_reembed(
    perfume_id: int | None = None,
    conn: Connection = Depends(get_db),
    _key=Depends(require_api_key),
):
    """Manually trigger re-embedding for missing/stale perfumes.

    If `perfume_id` is provided, only that one perfume is re-embedded
    (backgrounded so the 202 response isn't delayed by embedding computation).
    If omitted, a warning is logged but no action is taken — the background
    sweeper will pick up the next 20 stale rows on its next cycle.
    """
    if perfume_id is None:
        logger.info("reembed_sweep_not_triggered")
        return

    row = await conn.fetchrow(
        "SELECT id, brand, perfume, main_accords, notes FROM perfumes WHERE id = $1",
        perfume_id,
    )
    if not row:
        logger.warning("reembed_nonexistent_perfume", perfume_id=perfume_id)
        return

    text_parts = [
        row.get("brand") or "",
        row.get("perfume") or "",
        " ".join(row.get("main_accords") or []),
        " ".join(row.get("notes") or []),
    ]
    doc_text = " ".join(part for part in text_parts if part).strip()
    if not doc_text:
        logger.warning("reembed_empty_text", perfume_id=perfume_id)
        return

    # Fire-and-forget: embed in background so the 202 response arrives quickly
    async def _reembed():
        try:
            emb = await generate_document_embedding_async(doc_text)
            emb_list = emb.tolist() if hasattr(emb, "tolist") else emb
            pool = await get_db_pool()
            async with pool.acquire() as bg_conn:
                await bg_conn.execute(
                    "UPDATE perfumes SET embedding = $1::vector, last_embedded_at = NOW() WHERE id = $2",
                    emb_list,
                    perfume_id,
                )
        except Exception:
            logger.warning("reembed_background_error", perfume_id=perfume_id, exc_info=True)

    asyncio.create_task(_reembed())
