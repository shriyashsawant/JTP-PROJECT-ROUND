"""
AuraMatch AI - Image-Based Similarity Search
Computes lightweight visual embeddings from perfume bottle images using a
color histogram (HSV, 64 dims). No heavyweight vision model needed: the
color palette of a perfume bottle is a surprisingly strong visual signal
for "looks similar" — a fresh aquatic fragrance tends toward blue/clear
glass, while a warm oriental bottle skews amber/opaque.

The embedding is a flattened 4×4×4 HSV histogram (64 floats, L1-normalized).
Stored in a separate `image_embedding VECTOR(64)` column on the perfumes
table (not the same 384-dim semantic embedding) so ANN search against it
uses its own dedicated index.
"""

import asyncio
import io
import logging
import struct
from typing import Sequence

from app.core.config import settings

logger = logging.getLogger(__name__)

IMAGE_DIM = 64

# Shared httpx client for fetching images
_client: "httpx.AsyncClient | None" = None


def _get_client():
    global _client
    if _client is None:
        import httpx
        _client = httpx.AsyncClient(timeout=5.0)
    return _client


async def close_image_client():
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def compute_image_embedding(image_url: str) -> list[float] | None:
    """Download an image from `image_url` and return a 64-dim HSV histogram.

    Returns None if the image can't be fetched or decoded (bad URL, not an
    image, timeout) — callers handle gracefully by skipping ANN image search.
    """
    import numpy as np
    from PIL import Image

    try:
        client = _get_client()
        resp = await client.get(image_url)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
    except Exception:
        logger.debug("image_fetch_failed", url=image_url, exc_info=True)
        return None

    try:
        img = img.resize((128, 128), Image.LANCZOS)
        arr = np.array(img, dtype=np.uint8)
        hsv = np.zeros((128, 128, 3), dtype=np.uint8)

        # Manual RGB -> HSV conversion (cheaper than cv2)
        r, g, b = arr[:, :, 0].astype(float) / 255.0, arr[:, :, 1].astype(float) / 255.0, arr[:, :, 2].astype(float) / 255.0
        max_rgb = np.maximum(np.maximum(r, g), b)
        min_rgb = np.minimum(np.minimum(r, g), b)
        diff = max_rgb - min_rgb

        # Hue
        h = np.zeros_like(max_rgb)
        mask = diff > 0
        r_m = mask & (max_rgb == r)
        g_m = mask & (max_rgb == g)
        b_m = mask & (max_rgb == b)
        h[r_m] = 60.0 * ((g[r_m] - b[r_m]) / diff[r_m] % 6)
        h[g_m] = 60.0 * ((b[g_m] - r[g_m]) / diff[g_m] + 2)
        h[b_m] = 60.0 * ((r[b_m] - g[b_m]) / diff[b_m] + 4)
        hsv[:, :, 0] = (h / 360.0 * 255).astype(np.uint8)

        # Saturation
        s = np.where(max_rgb > 0, diff / max_rgb, 0)
        hsv[:, :, 1] = (s * 255).astype(np.uint8)
        # Value
        hsv[:, :, 2] = (max_rgb * 255).astype(np.uint8)

        # 4×4×4 HSV histogram
        bins = 4
        h_bins = np.clip(hsv[:, :, 0] * bins / 256, 0, bins - 1).astype(int)
        s_bins = np.clip(hsv[:, :, 1] * bins / 256, 0, bins - 1).astype(int)
        v_bins = np.clip(hsv[:, :, 2] * bins / 256, 0, bins - 1).astype(int)

        hist = np.zeros((bins, bins, bins), dtype=float)
        np.add.at(hist, (h_bins, s_bins, v_bins), 1)
        hist = hist.flatten()
        total = hist.sum()
        if total > 0:
            hist = hist / total

        return hist.tolist()
    except Exception:
        logger.debug("image_histogram_error", exc_info=True)
        return None


async def find_similar_by_image(
    conn,
    image_embedding: list[float],
    limit: int = 10,
) -> list[dict]:
    """Find perfumes whose bottle image looks visually similar.

    Uses cosine distance on the 64-dim image embedding via pgvector ANN.
    Returns empty list if no image_embeddings exist in the DB yet.

    Note: the image_embedding column must be populated by a background
    sweeper (see embedding_sweeper.py for the pattern) — this just reads
    whatever is already stored.
    """
    try:
        rows = await conn.fetch(
            f"""
            SELECT id, brand, perfume, price_inr, image_url,
                   1 - (image_embedding <=> $1::vector) AS image_similarity
            FROM perfumes
            WHERE image_embedding IS NOT NULL
            ORDER BY image_embedding <=> $1::vector
            LIMIT $2
            """,
            image_embedding,
            limit,
        )
        return [
            {
                "id": r["id"],
                "brand": r["brand"],
                "perfume": r["perfume"],
                "price_inr": r["price_inr"],
                "image_url": r["image_url"],
                "image_similarity": round(float(r["image_similarity"]), 4),
            }
            for r in rows
        ]
    except Exception:
        logger.warning("image_search_error", exc_info=True)
        return []
