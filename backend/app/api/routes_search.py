from asyncpg.connection import Connection
from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import require_api_key
from app.api.dependencies import get_db
from app.core.config import settings
from app.models.schemas import ContextSearchRequest, HealthResponse, PerfumeResponse
from app.services.db_repository import check_health, find_reference_perfume, search_by_context
from app.services.decision_engine import apply_price_order, cap_per_brand
from app.services.intent_detector import (
    detect_budget_from_text,
    detect_dupe_intent,
    detect_gender,
    detect_longevity_hours_required,
    detect_longevity_intent,
    detect_negated_terms,
    detect_projection_preference,
    detect_scenarios,
)
from app.services.llm_enrichment import enhance_with_llm
from app.services.ml_engine import build_context_query

router = APIRouter(prefix="/api/v1", tags=["Search"])

@router.post("/search/context", response_model=list[PerfumeResponse])
async def context_search(
    req: ContextSearchRequest, conn: Connection = Depends(get_db),
    _key=Depends(require_api_key),
):
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

    detected_scenarios = await detect_scenarios(req.query)
    scenarios = list(dict.fromkeys((req.scenario or []) + detected_scenarios)) or None
    gender = req.gender or detect_gender(req.query)
    hours_required = req.hours_required or detect_longevity_hours_required(req.query)
    longevity_requested = detect_longevity_intent(req.query) or bool(hours_required)
    projection_preference = req.projection_preference or detect_projection_preference(req.query)
    dupe_intent = detect_dupe_intent(req.query)
    negated_terms = detect_negated_terms(req.query)

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
    if budget is not None and budget < 100:
        raise HTTPException(400, detail="Minimum budget is ₹100")

    enriched = build_context_query(
        req.query, scenarios, req.skin_type, req.note_families,
        reference_accords=reference_accords, reference_notes=reference_notes,
    )
    raw_query = req.query
    if reference_accords or reference_notes:
        raw_query = f"{req.query} {' '.join(reference_accords or [])} {' '.join(reference_notes or [])}"

    # Always fetch a wider deterministically-ranked pool than the final
    # limit, not just when the LLM is enabled - the extra candidates give
    # the optional LLM layer real alternatives to choose from (it can
    # reorder/drop weak picks but never invent a perfume outside this pool),
    # and separately give cap_per_brand below real backfill material to draw
    # from after removing over-represented brands, in both the LLM and
    # no-LLM paths alike. `req.limit` can now be as large as 60 (the chat
    # UI's "Show More" pagination) - always keep at least 20 candidates of
    # headroom above whatever was actually requested, capped at 120 total to
    # bound DB query cost (deterministic ranking is cheap even at this size).
    llm_enabled = bool(settings.groq_api_key)
    fetch_limit = min(120, max(25, req.limit + 20))
    # The LLM prompt scales with how many candidates it's handed - re-ranking
    # a wide, 120-deep pool on every request would blow up prompt size/
    # latency/cost for marginal benefit, since its real value is polishing
    # the top results, not exhaustively re-ranking a "Show More" tail. Bound
    # what it ever sees regardless of how large the pool/limit grows; any
    # remainder needed to reach req.limit is backfilled directly from the
    # deterministic pool afterward (already ranked, already brand-capped,
    # just without the LLM's own explanation text).
    llm_pool_cap = 30

    results = await search_by_context(
        conn, enriched, budget, fetch_limit,
        scenarios=scenarios, skin_type=req.skin_type,
        raw_query=raw_query, gender=gender, age=req.age, longevity_requested=longevity_requested,
        hours_required=hours_required, projection_preference=projection_preference,
        exclude_id=reference["id"] if reference else None,
        reference_accords=reference_accords, reference_notes=reference_notes,
        exclude_family_brand=reference["brand"] if reference else None,
        deal_breaker=req.deal_breaker,
        reference_id=reference["id"] if reference else None,
        negated_terms=negated_terms,
        note_families=req.note_families,
    )
    # Strict (no backfill) cap on the wide pool before the LLM ever sees it -
    # the LLM's own "prefer variety" prompt instruction is advisory only and
    # was verified (empirically, across many repeated live runs) to not
    # reliably hold on its own for low-signal queries where deterministic
    # scores cluster too closely to differentiate brands. Not backfilled to
    # `fetch_limit` here - relaxing the cap to fill a large pool (25) would
    # let an over-represented brand climb right back up before the LLM ever
    # sees it, defeating the point.
    results = cap_per_brand(results, fetch_limit, backfill=False)

    if llm_enabled:
        llm_pick_count = min(req.limit, llm_pool_cap)
        enhanced = await enhance_with_llm(req.query, results[:llm_pool_cap], llm_pick_count)
        if enhanced:
            # The LLM re-ranks by its own relevance judgment, which would
            # otherwise silently discard the nearest-to-budget/cheapest-first
            # order the user asked for - reassert it as the final step. Also
            # re-capped (with backfill, at the real req.limit this time) since
            # the LLM's own picks - even from an already-capped input pool -
            # are still its own free choice among whatever survived, not a
            # guarantee in themselves.
            final = cap_per_brand(apply_price_order(enhanced, budget, req.deal_breaker), llm_pick_count)
            if len(final) < req.limit:
                # A "Show More" request asking for more than the LLM was ever
                # handed - fill the remainder directly from the wider
                # deterministic pool (already ranked, already brand-capped),
                # not re-run through the LLM.
                seen_ids = {r["id"] for r in final}
                remainder = [r for r in results if r["id"] not in seen_ids]
                final = final + cap_per_brand(remainder, req.limit - len(final))
            return final
    return cap_per_brand(results, req.limit)

@router.get("/health", response_model=HealthResponse)
async def health_check(conn: Connection = Depends(get_db)):
    db_ok = await check_health(conn)
    return {"status": "ok" if db_ok else "degraded", "db_connected": db_ok}
