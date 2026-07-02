from fastapi import APIRouter, Depends, HTTPException
from asyncpg.connection import Connection
from app.models.schemas import ContextSearchRequest, PerfumeResponse, HealthResponse
from app.api.dependencies import get_db
from app.services.db_repository import search_by_context, check_health
from app.services.ml_engine import build_context_query
from app.services.intent_detector import (
    detect_scenarios, detect_gender, detect_longevity_intent,
    detect_longevity_hours_required, detect_projection_preference,
)

router = APIRouter(prefix="/api/v1", tags=["Search"])

@router.post("/search/context", response_model=list[PerfumeResponse])
async def context_search(req: ContextSearchRequest, conn: Connection = Depends(get_db)):
    """Search perfumes by natural language + optional scenario(s) + skin type + budget.

    Scenarios/gender/longevity intent are also auto-detected from the free-text
    query itself and merged with any explicit selections, so a single compound
    sentence (e.g. "office commute, gym in the evening, long lasting") can drive
    the same blended result as manually picking multiple filters.
    """
    if not req.query.strip():
        raise HTTPException(400, detail="Query is required")

    detected_scenarios = detect_scenarios(req.query)
    scenarios = list(dict.fromkeys((req.scenario or []) + detected_scenarios)) or None
    gender = req.gender or detect_gender(req.query)
    hours_required = detect_longevity_hours_required(req.query)
    longevity_requested = detect_longevity_intent(req.query) or bool(hours_required)
    projection_preference = detect_projection_preference(req.query)

    enriched = build_context_query(req.query, scenarios, req.skin_type, req.note_families)
    results = await search_by_context(
        conn, enriched, req.budget, req.limit,
        scenarios=scenarios, skin_type=req.skin_type,
        raw_query=req.query, gender=gender, age=req.age, longevity_requested=longevity_requested,
        hours_required=hours_required, projection_preference=projection_preference,
    )
    return results

@router.get("/health", response_model=HealthResponse)
async def health_check(conn: Connection = Depends(get_db)):
    db_ok = await check_health(conn)
    return {"status": "ok" if db_ok else "degraded", "db_connected": db_ok}
