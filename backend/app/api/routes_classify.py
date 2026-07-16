"""
AuraMatch AI - Intent Classification endpoint
Used by the frontend as a second-opinion check when the client-side regex
off-topic detector is uncertain. Returns an embedding-based classification
with optional Groq LLM fallback for low-confidence cases.

Secured with per-IP rate limiting (60 req/min) and input validation via
Pydantic — no DB or API key needed, but still protected against abuse.
"""
from fastapi import APIRouter, Depends, HTTPException, Request

from app.models.schemas import ClassifyIntentRequest
from app.services.off_topic_classifier import classify
from app.services.rate_limiter import check_rate_limit

router = APIRouter(prefix="/api/v1", tags=["classify"])


@router.post("/classify-intent")
async def classify_intent(request: Request, body: ClassifyIntentRequest):
    client_ip = request.client.host if request.client else "127.0.0.1"
    allowed, _, _ = await check_rate_limit(("classify", client_ip), 60)
    if not allowed:
        raise HTTPException(429, detail="Rate limit exceeded")
    return await classify(body.text)
