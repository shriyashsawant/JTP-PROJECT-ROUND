"""
AuraMatch AI - Incremental Embedding Sweeper
Background task that periodically scans the perfumes table for rows whose
text embedding or image embedding is missing or stale and recomputes them.
Runs every 60 seconds until told to stop.

This avoids blocking the API: new perfumes added via seeding or admin
endpoints get their embedding computed lazily by the sweeper, not during
the insert request.
"""

import asyncio
import logging

from app.core.config import settings
from app.services.image_search import compute_image_embedding
from app.services.ml_engine import generate_document_embedding_async

logger = logging.getLogger(__name__)

_SWEEP_INTERVAL = 60  # seconds
_BATCH_SIZE = 20
_ROW_DELAY = 0.1  # 100ms between individual embedding calls to avoid overwhelming the model/API

_stop_event = asyncio.Event()


async def start_sweeper(pool):
    """Start the background sweep loop. Runs until `stop_sweeper()` is called."""
    _stop_event.clear()
    logger.info("embedding_sweeper_started", interval=_SWEEP_INTERVAL)
    while not _stop_event.is_set():
        try:
            await _sweep_text(pool)
            await _sweep_image(pool)
        except Exception:
            logger.warning("embedding_sweeper_error", exc_info=True)
        try:
            await asyncio.wait_for(
                asyncio.get_event_loop().create_future(),
                timeout=_SWEEP_INTERVAL,
            )
        except asyncio.TimeoutError:
            pass


def stop_sweeper():
    """Signal the sweeper to exit at the next loop iteration."""
    _stop_event.set()
    logger.info("embedding_sweeper_stopped")


async def _sweep_text(pool):
    """Find rows needing text-embedding and recompute them in small batches."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, brand, perfume, main_accords, notes
            FROM perfumes
            WHERE embedding IS NULL
               OR last_embedded_at IS NULL
               OR last_embedded_at < updated_at
            LIMIT $1
            """,
            _BATCH_SIZE,
        )

    if not rows:
        return

    logger.info("embedding_sweep_text_batch", count=len(rows))

    for row in rows:
        if _stop_event.is_set():
            break
        try:
            text_parts = [
                row.get("brand") or "",
                row.get("perfume") or "",
                " ".join(row.get("main_accords") or []),
                " ".join(row.get("notes") or []),
            ]
            doc_text = " ".join(part for part in text_parts if part).strip()
            if not doc_text:
                continue

            embedding = await generate_document_embedding_async(doc_text)

            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE perfumes
                    SET embedding = $1::vector,
                        last_embedded_at = NOW()
                    WHERE id = $2
                    """,
                    embedding.tolist() if hasattr(embedding, "tolist") else embedding,
                    row["id"],
                )

            # Rate limit between individual API calls
            await asyncio.sleep(_ROW_DELAY)

        except Exception:
            logger.warning(
                "embedding_sweep_row_error",
                perfume_id=row["id"],
                exc_info=True,
            )


async def _sweep_image(pool):
    """Find rows needing image-embedding and recompute them in small batches."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, image_url
            FROM perfumes
            WHERE image_url IS NOT NULL
              AND image_embedding IS NULL
            LIMIT $1
            """,
            _BATCH_SIZE,
        )

    if not rows:
        return

    logger.info("embedding_sweep_image_batch", count=len(rows))

    for row in rows:
        if _stop_event.is_set():
            break
        try:
            image_url = row.get("image_url")
            if not image_url:
                continue

            emb = await compute_image_embedding(image_url)
            if emb is None:
                continue

            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE perfumes
                    SET image_embedding = $1::vector
                    WHERE id = $2
                    """,
                    emb,
                    row["id"],
                )

            await asyncio.sleep(_ROW_DELAY)

        except Exception:
            logger.warning(
                "image_embedding_sweep_row_error",
                perfume_id=row["id"],
                exc_info=True,
            )
