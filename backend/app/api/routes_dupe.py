from fastapi import APIRouter, Depends, HTTPException, Query
from asyncpg.connection import Connection
from app.models.schemas import BudgetSearchRequest, PerfumeResponse, PerfumeDetailResponse
from app.api.dependencies import get_db
from app.services.db_repository import search_by_budget, get_perfume_by_id
from app.services.ml_engine import build_budget_query
from app.services.intent_detector import (
    detect_scenarios, detect_gender, detect_longevity_intent,
    detect_longevity_hours_required, detect_projection_preference,
)

router = APIRouter(prefix="/api/v1", tags=["Dupe Engine"])

@router.post("/search/dupe", response_model=list[PerfumeResponse])
async def dupe_search(req: BudgetSearchRequest, conn: Connection = Depends(get_db)):
    """Dupe Engine — find affordable alternatives within budget."""
    if req.budget < 100:
        raise HTTPException(400, detail="Minimum budget is ₹100")

    detected_scenarios = detect_scenarios(req.query)
    scenarios = list(dict.fromkeys((req.scenario or []) + detected_scenarios)) or None
    gender = req.gender or detect_gender(req.query)
    hours_required = detect_longevity_hours_required(req.query)
    longevity_requested = detect_longevity_intent(req.query) or bool(hours_required)
    projection_preference = detect_projection_preference(req.query)

    enriched = build_budget_query(req.query, scenarios, req.skin_type, req.note_families)
    results = await search_by_budget(
        conn, enriched, req.budget, req.limit,
        scenarios=scenarios, skin_type=req.skin_type,
        raw_query=req.query, gender=gender, age=req.age, longevity_requested=longevity_requested,
        hours_required=hours_required, projection_preference=projection_preference,
    )
    return results

@router.get("/perfume/{perfume_id}", response_model=PerfumeDetailResponse)
async def get_perfume(perfume_id: int, conn: Connection = Depends(get_db)):
    result = await get_perfume_by_id(conn, perfume_id)
    if not result:
        raise HTTPException(404, detail="Perfume not found")
    return result
