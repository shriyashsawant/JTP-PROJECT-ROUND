from asyncpg.connection import Connection
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.api.auth import require_api_key
from app.api.dependencies import get_db, get_reader_db, get_ab_test
from app.services.ab_testing import AbTest
from app.core.config import settings
from app.models.schemas import BudgetSearchRequest, PerfumeDetailResponse, PerfumeResponse
from app.services.db_repository import find_reference_perfume, get_perfume_by_id, search_by_budget
from app.services.decision_engine import apply_price_order, cap_by_scent_character, cap_per_brand
from app.services.intent_detector import (
    detect_budget_from_text,
    detect_gender,
    detect_longevity_hours_required,
    detect_longevity_intent,
    detect_negated_terms,
    detect_projection_preference,
    detect_scenarios,
)
from app.services.llm_enrichment import enhance_with_llm
from app.services.ml_engine import build_budget_query
from app.services.scenario_map import infer_performance_from_scenarios
from app.services.user_profile import build_personalization_context, build_profile

router = APIRouter(prefix="/api/v1", tags=["Dupe Engine"])

@router.post("/search/dupe", response_model=list[PerfumeResponse])
async def dupe_search(
    req: BudgetSearchRequest, request: Request, response: Response,
    conn: Connection = Depends(get_reader_db),
    _key=Depends(require_api_key),
    ab: AbTest = Depends(get_ab_test),
):
    """Dupe Engine — find affordable alternatives within budget.

    Looks up the named perfume in our own DB first: grounding the search in
    its REAL accords/notes (rather than just embedding the bare name and
    hoping the model recognizes it) is what makes 'cheaper alternative to
    Dior Sauvage' actually return fresh/aromatic/ambroxan-woody perfumes
    instead of unrelated florals that merely share generic text similarity.

    An explicit price stated in the query text itself ("under Rs 500")
    overrides the `budget` field - a deliberately typed number is a stronger
    signal than whatever the form field happens to hold. If neither gives a
    ceiling, we default to the reference perfume's own price - this IS the
    dupe engine, so an unconstrained query would otherwise happily return
    "alternatives" priced higher than the luxury original itself. Only when
    we can't find a reference either do we ask for clarification instead of
    silently returning unconstrained results.
    """
    budget = detect_budget_from_text(req.query)
    if budget is None:
        budget = req.budget

    reference = await find_reference_perfume(conn, req.query)
    reference_accords = reference["main_accords"] if reference else None
    reference_notes = reference["notes"] if reference else None

    if budget is None:
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
    if budget < 100:
        raise HTTPException(400, detail="Minimum budget is ₹100")

    detected_scenarios = await detect_scenarios(req.query)
    scenarios = list(dict.fromkeys((req.scenario or []) + detected_scenarios)) or None
    gender = req.gender or detect_gender(req.query)
    hours_required = req.hours_required or detect_longevity_hours_required(req.query)
    longevity_requested = detect_longevity_intent(req.query) or bool(hours_required)
    projection_preference = req.projection_preference or detect_projection_preference(req.query)
    # See routes_search.py's identical block for the full reasoning - an
    # occasion implies a typical wear duration/projection, filled in only
    # when the user hasn't stated either themselves.
    if not hours_required or not projection_preference:
        inferred_hours, inferred_projection = infer_performance_from_scenarios(scenarios)
        if not hours_required and inferred_hours:
            hours_required = inferred_hours
            longevity_requested = True
        if not projection_preference and inferred_projection:
            projection_preference = inferred_projection
    negated_terms = detect_negated_terms(req.query)

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

    # Same pattern as context_search - see its comments for the full
    # reasoning. `req.limit` can now be as large as 60 (the chat UI's "Show
    # More" pagination); fetch_limit always keeps 20 candidates of headroom
    # above whatever was requested, capped at 120 to bound DB cost, while
    # the LLM itself is only ever handed a bounded llm_pool_cap regardless
    # of how large the pool/limit grows (its value is polishing the top
    # results, not exhaustively re-ranking a "Show More" tail).
    llm_enabled = bool(settings.groq_api_key)
    fetch_limit = min(120, max(25, req.limit + 20))
    llm_pool_cap = 30

    results = await search_by_budget(
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
    # Strict (no backfill) on the wide pool before the LLM sees it - see
    # cap_per_brand's docstring for why relaxing/backfilling at this stage
    # (against the large fetch_limit) would defeat the point.
    results = cap_per_brand(results, fetch_limit, backfill=False)
    # Same as routes_search.py's equivalent block: skipped when `reference`
    # resolved (a real "cheaper alternative to X" should cluster around X's
    # own scent character), applied when it didn't (an unrecognized
    # reference name with an explicit budget still reaches this point - see
    # the 422 condition above, which only fires when *both* budget and
    # reference are missing). `pre_diversity_results` preserves the
    # pre-cut pool so a scent-homogeneous wide pool can't strictly shrink
    # `results` below `req.limit` with no way back - both return paths below
    # backfill any shortfall from it, same remainder pattern already used
    # for the LLM's own shortfall.
    pre_diversity_results = results
    if not reference:
        results = cap_by_scent_character(results, fetch_limit, backfill=False)

    if llm_enabled:
        llm_pick_count = min(req.limit, llm_pool_cap)
        profile = await build_profile(conn, req.session_id)
        personalization_ctx = build_personalization_context(profile)
        enhanced = await enhance_with_llm(req.query, results[:llm_pool_cap], llm_pick_count, personalization_ctx)
        if enhanced:
            # The LLM re-ranks by its own relevance judgment, which would
            # otherwise silently discard the nearest-to-budget/cheapest-first
            # order the user asked for - reassert it as the final step. Also
            # re-capped (with backfill, at the real req.limit) as a final,
            # always-on guarantee regardless of the LLM's own picks.
            final = cap_per_brand(apply_price_order(enhanced, budget, req.deal_breaker), llm_pick_count)
            if len(final) < req.limit:
                # "Show More" asking for more than the LLM was ever handed -
                # fill the remainder from the wider deterministic pool
                # directly, not re-run through the LLM.
                seen_ids = {r["id"] for r in final}
                remainder = [r for r in pre_diversity_results if r["id"] not in seen_ids]
                final = final + cap_per_brand(remainder, req.limit - len(final))
            response.headers["X-AuraMatch-Variant"] = ab.active_variant
            return final
    final = cap_per_brand(results, req.limit)
    if len(final) < req.limit:
        seen_ids = {r["id"] for r in final}
        remainder = [r for r in pre_diversity_results if r["id"] not in seen_ids]
        final = final + cap_per_brand(remainder, req.limit - len(final))
    response.headers["X-AuraMatch-Variant"] = ab.active_variant
    return final

@router.get("/perfume/{perfume_id}", response_model=PerfumeDetailResponse)
async def get_perfume(
    perfume_id: int, conn: Connection = Depends(get_db),
    _key=Depends(require_api_key),
):
    result = await get_perfume_by_id(conn, perfume_id)
    if not result:
        raise HTTPException(404, detail="Perfume not found")
    return result
