import re

from app.services.decision_engine import rank_and_explain
from app.services.ml_engine import generate_embedding_async
from app.services.scenario_map import classify_accord_tiers, classify_note_tiers


def _parse_concentration_type(name: str) -> str | None:
    """The seeder never populated `type` (see seed_data.py), so derive it
    on-the-fly from the perfume name instead of a costly full reseed."""
    if not name:
        return None
    n = f" {name.lower()} "
    if "eau de toilette" in n or " edt" in n:
        return "Eau de Toilette"
    if "eau de parfum" in n or " edp" in n:
        return "Eau de Parfum"
    if "extrait de parfum" in n or "extrait" in n:
        return "Extrait de Parfum"
    if "cologne" in n or " edc" in n:
        return "Eau de Cologne"
    if "elixir" in n:
        return "Elixir"
    if "parfum" in n:
        return "Parfum"
    if "body spray" in n or "deodorant" in n or "body mist" in n or "mist" in n:
        return "Body Spray"
    return None


def _candidate_pool_size(limit: int, has_budget: bool = False) -> int:
    """Fetch a wider ANN candidate pool than requested so gender/note/longevity
    reranking in rank_and_explain has something real to reorder.

    When a budget is set, the pool needs to span the price spectrum up to that
    budget, not just whatever narrow slice ranks highest by raw text/embedding
    similarity - otherwise "nearest to budget"/deal-breaker sorting can only
    rearrange whichever items happened to make a tiny top-50-by-similarity cut
    (which, for many queries, skews toward cheaper, more numerous perfumes),
    and a perfectly relevant pricier-but-still-within-budget option never even
    enters the pool for it to consider."""
    if has_budget:
        return min(max(limit * 10, 100), 200)
    return min(max(limit * 5, 25), 50)


def _to_pgvector_literal(embedding: list[float]) -> str:
    """asyncpg has no built-in codec for pgvector's `vector` type - a raw Python
    list fails with 'expected str, got list'. Serialize to the text literal
    Postgres' vector input parser accepts, then cast with ::vector in SQL."""
    return "[" + ",".join(str(x) for x in embedding) + "]"


def _resolve_pyramid(r, notes: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Rows seeded before the top_notes/heart_notes/base_notes columns
    existed (or restored from a pre-baked dump that predates them - see
    docker-entrypoint-initdb.d's 02_seed_data.sql.gz) still have them as
    NULL until a full reseed. Rather than showing an empty pyramid for the
    entire existing dataset until that happens, classify on the fly - same
    heuristic seed_data.py uses, just applied at request time instead of
    seed time. Real data (once a reseed populates these columns) is always
    preferred and used as-is."""
    top_notes = r.get("top_notes") or []
    heart_notes = r.get("heart_notes") or []
    base_notes = r.get("base_notes") or []
    if not (top_notes or heart_notes or base_notes):
        if notes:
            top_notes, heart_notes, base_notes = classify_note_tiers(notes)
        elif r.get("main_accords"):
            top_notes, heart_notes, base_notes = classify_accord_tiers(r["main_accords"])
    return top_notes, heart_notes, base_notes


def _format_perfume_row(r) -> dict:
    notes = r["notes"] or []
    top_notes, heart_notes, base_notes = _resolve_pyramid(r, notes)
    return {
        "id": r["id"],
        "brand": r["brand"],
        "perfume": r["perfume"],
        "price_inr": float(r["price_inr"]) if r["price_inr"] else None,
        "notes": notes,
        "main_accords": r["main_accords"] or [],
        "top_notes": top_notes,
        "heart_notes": heart_notes,
        "base_notes": base_notes,
        "type": r["type"] or _parse_concentration_type(r["perfume"]),
        "gender": r["gender"],
        "longevity_score": float(r["longevity_score"]) if r["longevity_score"] else None,
        "sillage_score": float(r["sillage_score"]) if r["sillage_score"] else None,
        "similarity": float(r["similarity"]) if r.get("similarity") else 0,
        "match_score": round(float(r["similarity"]) * 100, 1) if r.get("similarity") else 0,
        "savings": None,
        "url": r.get("url"),
        "country": r.get("country"),
        "perfumer": r.get("perfumer"),
    }


def _build_exclusion_patterns(negated_terms: list[str] | None) -> list[str] | None:
    """Builds Postgres regex patterns (word-bounded via \\m/\\M) from negated
    free-text terms (see intent_detector.detect_negated_terms), for a SQL-
    level `~* ANY(...)` filter that removes candidates whose notes/accords
    contain an excluded term BEFORE the ANN pool is narrowed - rather than
    only penalizing them after the fact within an already-narrow pool that
    might itself be dominated by the excluded note (e.g. if the top-200
    ANN-similarity results for "vanilla" are almost all vanilla-forward,
    penalizing them post-fetch never reaches the genuinely vanilla-free
    alternatives further down). decision_engine._negation_penalty still runs
    as a safety net for anything this simpler pattern doesn't catch."""
    if not negated_terms:
        return None
    return [rf"\m{re.escape(t)}\M" for t in negated_terms]


async def _fetch_candidates(
    db, query: str, reference_id: int | None, budget: float | None, pool_size: int,
    exclude_id: int | None, exclude_family_brand: str | None,
    excluded_note_patterns: list[str] | None = None,
):
    """Runs the ANN candidate-pool query. When `reference_id` is given (the
    caller already resolved a named perfume to a row in our own DB), compare
    candidates directly against THAT row's actual stored embedding via a SQL
    subquery - skips model inference entirely (near-instant) and scores
    against the real vector instead of a text reconstruction of its accords/
    notes re-embedded through the model."""
    if reference_id is not None:
        sql = """
            SELECT id, brand, perfume, price_inr, notes, main_accords, type,
                   gender, longevity_score, sillage_score,
                   top_notes, heart_notes, base_notes,
                   url, country, perfumer,
                   1 - (embedding <=> (SELECT embedding FROM perfumes WHERE id = $1)) AS similarity
            FROM perfumes
            WHERE ($2::float IS NULL OR price_inr <= $2) AND ($4::int IS NULL OR id != $4)
              AND ($5::text IS NULL OR NOT (brand ILIKE '%' || $5 || '%' OR $5 ILIKE '%' || brand || '%'))
              AND ($6::text[] IS NULL OR NOT EXISTS (
                  SELECT 1 FROM unnest(COALESCE(notes, '{}') || COALESCE(main_accords, '{}')) AS n
                  WHERE n ~* ANY($6::text[])
              ))
            ORDER BY similarity DESC
            LIMIT $3
        """
        return await db.fetch(sql, reference_id, budget, pool_size, exclude_id, exclude_family_brand,
                               excluded_note_patterns)

    embedding = await generate_embedding_async(query)
    sql = """
        SELECT id, brand, perfume, price_inr, notes, main_accords, type,
               gender, longevity_score, sillage_score,
               top_notes, heart_notes, base_notes,
               url, country, perfumer,
               1 - (embedding <=> $1::vector) AS similarity
        FROM perfumes
        WHERE ($2::float IS NULL OR price_inr <= $2) AND ($4::int IS NULL OR id != $4)
          AND ($5::text IS NULL OR NOT (brand ILIKE '%' || $5 || '%' OR $5 ILIKE '%' || brand || '%'))
          AND ($6::text[] IS NULL OR NOT EXISTS (
              SELECT 1 FROM unnest(COALESCE(notes, '{}') || COALESCE(main_accords, '{}')) AS n
              WHERE n ~* ANY($6::text[])
          ))
        ORDER BY similarity DESC
        LIMIT $3
    """
    return await db.fetch(sql, _to_pgvector_literal(embedding), budget, pool_size, exclude_id,
                           exclude_family_brand, excluded_note_patterns)


async def search_by_context(
    db, query: str, budget: float | None = None, limit: int = 5,
    scenarios: list[str] | None = None, skin_type: str | None = None, raw_query: str = "",
    gender: str | None = None, age: int | None = None, longevity_requested: bool = False,
    hours_required: int | None = None, projection_preference: str | None = None,
    exclude_id: int | None = None, reference_accords: list[str] | None = None, reference_notes: list[str] | None = None,
    exclude_family_brand: str | None = None, deal_breaker: bool = False,
    reference_id: int | None = None, negated_terms: list[str] | None = None,
    note_families: list[str] | None = None,
) -> list[dict]:
    pool_size = _candidate_pool_size(limit, has_budget=budget is not None)
    excluded_note_patterns = _build_exclusion_patterns(negated_terms)
    rows = await _fetch_candidates(db, query, reference_id, budget, pool_size, exclude_id, exclude_family_brand,
                                    excluded_note_patterns)

    results = [_format_perfume_row(r) for r in rows]
    return rank_and_explain(
        results, query=raw_query, budget=budget, scenarios=scenarios, skin_type=skin_type,
        gender=gender, age=age, longevity_requested=longevity_requested,
        hours_required=hours_required, projection_preference=projection_preference, limit=limit,
        reference_accords=reference_accords, reference_notes=reference_notes, deal_breaker=deal_breaker,
        negated_terms=negated_terms, note_families=note_families,
    )


FUZZY_REFERENCE_THRESHOLD = 0.3

async def find_reference_perfume(db, query: str) -> dict | None:
    """Look up the perfume the user is naming (e.g. 'Dior Sauvage') in our OWN
    database, so the dupe engine can ground its search in that perfume's REAL
    accords/notes instead of just hoping a generic embedding model 'knows'
    what an arbitrary brand name smells like. Matches by checking whether
    both the row's brand and perfume name appear as substrings of the query
    text; prefers rows with real note data and the shortest (base/flagship)
    name when several flankers match (e.g. 'Sauvage' over 'Sauvage Elixir').

    Falls back to pg_trgm word-similarity matching (typo-tolerant) only when
    the exact substring match finds nothing - e.g. 'Crred Aventus' won't
    substring-match 'creed' at all, so without this fallback the whole dupe
    search silently loses its composition grounding over a single typo.
    Exact match stays the preferred path because trigram similarity alone
    can't reliably tell a typo apart from a genuinely different-but-similar
    brand (e.g. 'Armaf' vs 'Armani' score ~0.67 on this same metric)."""
    if not query or len(query.strip()) < 3:
        return None
    sql = """
        SELECT id, brand, perfume, main_accords, notes, price_inr, gender
        FROM perfumes
        WHERE length(brand) >= 3 AND length(perfume) >= 3
          AND $1 ILIKE '%' || brand || '%'
          AND $1 ILIKE '%' || perfume || '%'
        ORDER BY (notes IS NULL OR array_length(notes, 1) IS NULL), length(perfume) ASC
        LIMIT 1
    """
    row = await db.fetchrow(sql, query)
    if not row:
        fuzzy_sql = """
            SELECT id, brand, perfume, main_accords, notes, price_inr, gender
            FROM perfumes
            WHERE length(brand) >= 3 AND length(perfume) >= 3
              AND word_similarity(brand, $1) > $2
              AND word_similarity(perfume, $1) > $2
            ORDER BY (notes IS NULL OR array_length(notes, 1) IS NULL),
                     (word_similarity(brand, $1) + word_similarity(perfume, $1)) DESC,
                     length(perfume) ASC
            LIMIT 1
        """
        row = await db.fetchrow(fuzzy_sql, query, FUZZY_REFERENCE_THRESHOLD)
    if not row:
        return None
    return {
        "id": row["id"], "brand": row["brand"], "perfume": row["perfume"],
        "main_accords": row["main_accords"] or [], "notes": row["notes"] or [],
        "price_inr": float(row["price_inr"]) if row["price_inr"] else None,
        "gender": row["gender"],
    }


async def search_by_budget(
    db, query: str, budget: float | None = None, limit: int = 6,
    scenarios: list[str] | None = None, skin_type: str | None = None, raw_query: str = "",
    gender: str | None = None, age: int | None = None, longevity_requested: bool = False,
    hours_required: int | None = None, projection_preference: str | None = None,
    exclude_id: int | None = None, reference_accords: list[str] | None = None, reference_notes: list[str] | None = None,
    exclude_family_brand: str | None = None, deal_breaker: bool = False,
    reference_id: int | None = None, negated_terms: list[str] | None = None,
    note_families: list[str] | None = None,
) -> list[dict]:
    pool_size = _candidate_pool_size(limit, has_budget=budget is not None)
    excluded_note_patterns = _build_exclusion_patterns(negated_terms)
    rows = await _fetch_candidates(db, query, reference_id, budget, pool_size, exclude_id, exclude_family_brand,
                                    excluded_note_patterns)

    results = [_format_perfume_row(r) for r in rows]
    return rank_and_explain(
        results, query=raw_query, budget=budget, scenarios=scenarios, skin_type=skin_type,
        gender=gender, age=age, longevity_requested=longevity_requested,
        hours_required=hours_required, projection_preference=projection_preference, limit=limit,
        reference_accords=reference_accords, reference_notes=reference_notes, deal_breaker=deal_breaker,
        negated_terms=negated_terms, note_families=note_families,
    )


async def get_perfume_by_id(db, perfume_id: int) -> dict | None:
    sql = """
        SELECT id, brand, perfume, launch_year, price_inr, type, gender,
               main_accords, notes, top_notes, heart_notes, base_notes,
               longevity_score, sillage_score, image_url,
               url, country, perfumer
        FROM perfumes
        WHERE id = $1
    """
    r = await db.fetchrow(sql, perfume_id)
    if not r:
        return None
    notes = r["notes"] or []
    top_notes, heart_notes, base_notes = _resolve_pyramid(r, notes)
    return {
        "id": r["id"],
        "brand": r["brand"],
        "perfume": r["perfume"],
        "launch_year": r["launch_year"],
        "price_inr": float(r["price_inr"]) if r["price_inr"] else None,
        "currency": "INR",
        "type": r["type"] or _parse_concentration_type(r["perfume"]),
        "gender": r["gender"],
        "main_accords": r["main_accords"] or [],
        "notes": notes,
        "top_notes": top_notes,
        "heart_notes": heart_notes,
        "base_notes": base_notes,
        "longevity_score": float(r["longevity_score"]) if r["longevity_score"] else None,
        "sillage_score": float(r["sillage_score"]) if r["sillage_score"] else None,
        "image_url": r["image_url"],
        "url": r.get("url"),
        "country": r.get("country"),
        "perfumer": r.get("perfumer"),
    }


async def check_health(db) -> bool:
    try:
        await db.fetchval("SELECT 1")
        return True
    except Exception:
        return False
