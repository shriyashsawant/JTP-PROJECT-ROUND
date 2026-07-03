from fastapi import APIRouter, Depends, HTTPException
from asyncpg.connection import Connection
from app.models.schemas import ContextSearchRequest, PerfumeResponse, HealthResponse
from app.api.dependencies import get_db
from app.services.db_repository import search_by_context, check_health, find_reference_perfume
from app.services.ml_engine import build_context_query
from app.services.intent_detector import (
    detect_scenarios, detect_gender, detect_longevity_intent,
    detect_longevity_hours_required, detect_projection_preference, detect_dupe_intent,
    detect_budget_from_text,
)

router = APIRouter(prefix="/api/v1", tags=["Search"])

@router.post("/search/context", response_model=list[PerfumeResponse])
async def context_search(req: ContextSearchRequest, conn: Connection = Depends(get_db)):
    """Search perfumes by natural language + optional scenario(s) + skin type + budget.

    Scenarios/gender/longevity intent are also auto-detected from the free-text
    query itself and merged with any explicit selections, so a single compound
    sentence (e.g. "office commute, gym in the evening, long lasting") can drive
    the same blended result as manually picking multiple filters.

    Also detects "cheaper alternative to X" / "dupe for X" style intent even
    when typed into this general search box (not just the dedicated dupe
    form): looks up X in our own DB to ground scoring in its real composition.
    Budget priority is: (1) an explicit price stated in the free text itself
    ("under Rs 500") - this overrides even the `budget` field, since a UI
    budget slider always sends *some* number (its default), so a specific
    price actually typed by the user is the more deliberate signal; (2) the
    `budget` field; (3) X's own price as a "cheaper than the original"
    default - only when neither (1) nor (2) is given. If dupe intent is
    clear but we can't find X at all and no budget was given by any of those
    routes, we genuinely can't compute "cheaper than what", so we ask for
    clarification (422) instead of silently returning unconstrained results.
    """
    if not req.query.strip():
        raise HTTPException(400, detail="Query is required")

    detected_scenarios = detect_scenarios(req.query)
    scenarios = list(dict.fromkeys((req.scenario or []) + detected_scenarios)) or None
    gender = req.gender or detect_gender(req.query)
    hours_required = detect_longevity_hours_required(req.query)
    longevity_requested = detect_longevity_intent(req.query) or bool(hours_required)
    projection_preference = detect_projection_preference(req.query)
    dupe_intent = detect_dupe_intent(req.query)

    # Only look up (and score against) a reference perfume's composition for an
    # actual dupe/alternative search. Doing this unconditionally was a real bug:
    # a plain identity search like "Dior Sauvage Elixir" would still resolve a
    # reference via substring match (picking the shorter base "Sauvage" row),
    # and every candidate - including "Sauvage" itself - would then be scored
    # by composition overlap against THAT reference. The reference trivially
    # matches itself perfectly, silently outranking the more specific flanker
    # the user actually typed.
    reference = await find_reference_perfume(conn, req.query) if dupe_intent else None
    reference_accords = reference["main_accords"] if reference else None
    reference_notes = reference["notes"] if reference else None

    budget = detect_budget_from_text(req.query)
    if budget is None:
        budget = req.budget
    if dupe_intent and budget is None:
        if reference and reference.get("price_inr"):
            budget = reference["price_inr"]
        else:
            raise HTTPException(422, detail={
                "needs_clarification": True,
                "field": "budget",
                "message": (
                    "Looking for a cheaper alternative, but we don't have a reference "
                    "price to compare against - what's your budget?"
                ),
            })

    enriched = build_context_query(
        req.query, scenarios, req.skin_type, req.note_families,
        reference_accords=reference_accords, reference_notes=reference_notes,
    )
    raw_query = req.query
    if reference_accords or reference_notes:
        raw_query = f"{req.query} {' '.join(reference_accords or [])} {' '.join(reference_notes or [])}"

    results = await search_by_context(
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

@router.get("/health", response_model=HealthResponse)
async def health_check(conn: Connection = Depends(get_db)):
    db_ok = await check_health(conn)
    return {"status": "ok" if db_ok else "degraded", "db_connected": db_ok}
