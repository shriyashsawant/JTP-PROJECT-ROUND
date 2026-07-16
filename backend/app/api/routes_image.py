"""
AuraMatch AI - Image Similarity Search
Lets users find perfumes by uploading a reference image or providing an
image URL — the backend computes a 64-dim HSV color histogram and returns
visually similar perfume bottles from the catalog.

The image embedding is computed on-the-fly for the query image and compared
against pre-computed image_embeddings in the perfumes table via pgvector ANN.
"""

import logging

from asyncpg.connection import Connection
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.auth import require_api_key
from app.api.dependencies import get_db
from app.services.image_search import compute_image_embedding, find_similar_by_image

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Image Search"])


@router.get("/search/image")
async def search_by_image(
    image_url: str = Query(..., min_length=1, max_length=2048),
    limit: int = Query(10, ge=1, le=60),
    conn: Connection = Depends(get_db),
    _key=Depends(require_api_key),
):
    """Search perfumes whose bottle looks visually similar to the given image URL.

    Returns a ranked list of perfumes with an `image_similarity` score (0-1),
    or an empty list if the image can't be fetched or no indexed image
    embeddings exist yet. The embedding is computed live from the URL and
    compared against pre-computed image_embeddings in the DB.
    """
    embedding = await compute_image_embedding(image_url)
    if embedding is None:
        raise HTTPException(422, detail="Could not process the image URL — check that it points to a valid image")

    results = await find_similar_by_image(conn, embedding, limit)
    return results
