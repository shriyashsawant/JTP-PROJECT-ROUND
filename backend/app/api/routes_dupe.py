from fastapi import APIRouter, Depends, HTTPException, Query
from asyncpg.connection import Connection
from app.models.schemas import BudgetSearchRequest, PerfumeResponse, PerfumeDetailResponse
from app.api.dependencies import get_db
from app.services.db_repository import search_by_budget, get_perfume_by_id, find_reference_perfume
from app.services.ml_engine import build_budget_query
from app.services.intent_detector import (
    detect_scenarios, detect_gender, detect_longevity_intent,
    detect_longevity_hours_required, detect_projection_preference, detect_budget_from_text,
)

router = APIRouter(prefix="/api/v1", tags=["Dupe Engine"])

@router.post("/search/dupe", response_model=list[PerfumeResponse])
async def dupe_search(req: BudgetSearchRequest, conn: Connection = Depends(get_db)):
    """Dupe Engine — find affordable alternatives within budget.

    Looks up the named perfume in our own DB first: grounding the search in
    its REAL accords/notes (rather than just embedding the bare name and
    hoping the model recognizes it) is what makes 'cheaper alternative to
    Dior Sauvage' actually return fresh/aromatic/ambroxan-woody perfumes
    instead of unrelated florals that merely share generic text similarity.

    An explicit price stated in the query text itself ("under Rs 500")
    overrides the `budget` field - a deliberately typed number is a stronger
    signal than whatever the form field happens to hold.
    """
    budget = detect_budget_from_text(req.query)
    if budget is None:
        budget = req.budget
    if budget < 100:
        raise HTTPException(400, detail="Minimum budget is ₹100")

    detected_scenarios = detect_scenarios(req.query)
    scenarios = list(dict.fromkeys((req.scenario or []) + detected_scenarios)) or None
    gender = req.gender or detect_gender(req.query)
    hours_required = detect_longevity_hours_required(req.query)
    longevity_requested = detect_longevity_intent(req.query) or bool(hours_required)
    projection_preference = detect_projection_preference(req.query)

    reference = await find_reference_perfume(conn, req.query)
    reference_accords = reference["main_accords"] if reference else None
    reference_notes = reference["notes"] if reference else None

    enriched = build_budget_query(
        req.query, scenarios, req.skin_type, req.note_families,
        reference_accords=reference_accords, reference_notes=reference_notes,
    )
    # Real accord/note words appended to raw_query so decision_engine's note-match
    # scoring and explanation text compare against the target's actual composition,
    # not just the literal brand/perfume-name words in the user's original query.
    raw_query = req.query
    if reference_accords or reference_notes:
        raw_query = f"{req.query} {' '.join(reference_accords or [])} {' '.join(reference_notes or [])}"

    results = await search_by_budget(
        conn, enriched, budget, req.limit,
        scenarios=scenarios, skin_type=req.skin_type,
        raw_query=raw_query, gender=gender, age=req.age, longevity_requested=longevity_requested,
        hours_required=hours_required, projection_preference=projection_preference,
        exclude_id=reference["id"] if reference else None,
        reference_accords=reference_accords, reference_notes=reference_notes,
        exclude_family_brand=reference["brand"] if reference else None,
        exclude_family_name=reference["perfume"] if reference else None,
    )
    return results

@router.get("/perfume/{perfume_id}", response_model=PerfumeDetailResponse)
async def get_perfume(perfume_id: int, conn: Connection = Depends(get_db)):
    result = await get_perfume_by_id(conn, perfume_id)
    if not result:
        raise HTTPException(404, detail="Perfume not found")
    return result
