import re

from app.services.decision_engine import MATCH_STOP_WORDS, rank_and_explain
from app.services.hnsw_tuner import dynamic_ef_search
from app.services.ml_engine import generate_embedding_async
from app.services.scenario_map import classify_accord_tiers, classify_note_tiers

# Extends decision_engine.MATCH_STOP_WORDS (imported, not copy-pasted - the
# two sets used to be independent copies of the same 28 base words, free to
# silently drift apart) with a few words specific to this lookup's own
# dupe-phrasing vocabulary.
_LOOKUP_STOP_WORDS = MATCH_STOP_WORDS | {
    "cheaper", "alternative", "version", "affordable", "budget", "clone", "similar", "instead", "dupe", "dupes",
}


def _clean_query_for_lookup(query: str) -> str:
    # Lowercase and remove punctuation. Deliberately NOT decision_engine's
    # _normalize_for_match here despite the near-identical shape - that
    # helper's stricter `[^a-z0-9\s]` strips accented characters entirely
    # (e.g. "Chloé" -> "Chlo "), which would break matching against real
    # accented brand names in this catalog; `\w` preserves them.
    q = query.lower()
    q = re.sub(r"[^\w\s]", " ", q)
    # Remove phrases
    phrases = [
        "cheaper alternative to", "cheaper alternative", "affordable alternative",
        "cheaper version", "affordable version", "budget alternative", "budget version",
        "clone of", "similar to", "alternative to", "instead of", "smells like"
    ]
    for phrase in phrases:
        q = q.replace(phrase, " ")

    # Remove individual stop words
    words = q.split()
    cleaned_words = [w for w in words if w not in _LOOKUP_STOP_WORDS]
    return " ".join(cleaned_words)


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


def _clean_notes(notes: list[str]) -> list[str]:
    """Drops elements that are a serialized Python dict rather than a real
    note name - confirmed live against the actual catalog: 514 rows (all
    `source='legacy_seed'`, predating the current app/ingestion/ pipeline
    entirely - there's no still-existing ingestion script to fix, only
    already-shipped data) have a spurious extra `notes` element like
    `"{'middle': [...], 'base': [...], 'top': [...]}"` - a str(dict) of the
    note-tier breakdown that should have been split into
    top_notes/heart_notes/base_notes, sitting alongside the correctly
    flattened individual note strings that were ALSO added. Left as-is, this
    displayed as raw, garbled text in place of a note pill (e.g. "Natura -
    due"), and would themselves get heuristically mis-classified into a
    pyramid tier by _resolve_pyramid's fallback classifier if not filtered
    out first. No real note name in this catalog is wrapped in braces, so a
    whole-element `{...}` shape is an unambiguous, zero-false-positive
    signal - not a general parser, just a narrow filter for this exact
    corruption shape."""
    return [n for n in notes if not (n.startswith("{'") and n.endswith("}"))]


def _candidate_pool_size(limit: int) -> int:
    """Fetch a wider ANN candidate pool than requested so gender/note/longevity
    reranking in rank_and_explain has something real to reorder - and, just as
    importantly, so the *rest* of the ~40,649-row catalog beyond a narrow
    embedding-proximity neighborhood actually gets a chance to compete.
    Vector similarity is deliberately the lowest-weighted active dimension in
    the whole scoring formula (SIM_WEIGHT=0.07 - see DECISION_ENGINE.md §2.2,
    versus SCENARIO_WEIGHT=0.28, NOTE_MATCH_WEIGHT=0.20, LONGEVITY_WEIGHT=0.20)
    precisely because two perfumes can share similar embeddings just from
    generic brand/description text - so a pool that's too narrow silently
    hands the *real* deciding dimensions (occasion, notes, longevity, price,
    gender) a tiny, embedding-biased slice of the catalog to choose from,
    rather than genuine variety across it.

    Previously capped at a hard 50 (no budget) / 200 (budget) regardless of
    how large `limit` grew - a leftover from before the HNSW index bypass fix
    in _fetch_candidates, when a wider pool meant a slower Seq Scan. Now that
    the index scan makes a much larger pool cheap, both cases use the same,
    much wider formula. The actual ceiling here is `hnsw.ef_search`'s own
    hard limit (1000 - pgvector rejects anything higher outright), not an
    arbitrary choice - _fetch_candidates' ef_search is derived from this same
    pool_size, so the two stay in lockstep."""
    return min(1000, max(limit * 15, 500))


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


def _clean_notes_and_pyramid(r) -> tuple[list[str], list[str], list[str], list[str], bool]:
    """Shared by _format_perfume_row and get_perfume_by_id - both need the
    same notes = _clean_notes(...) -> _resolve_pyramid(...) -> has_limited_data
    sequence. Previously copy-pasted between the two (a silent-drift risk:
    the next person to touch note-cleaning or the limited-data heuristic
    only had to remember to update one of the two copies to introduce a
    silent inconsistency between search results and the perfume detail
    page)."""
    notes = _clean_notes(r["notes"] or [])
    top_notes, heart_notes, base_notes = _resolve_pyramid(r, notes)
    return notes, top_notes, heart_notes, base_notes, not notes


DENSE_WEIGHT = 0.7
SPARSE_WEIGHT = 0.3


def _format_perfume_row(r) -> dict:
    notes, top_notes, heart_notes, base_notes, has_limited_data = _clean_notes_and_pyramid(r)
    dense_sim = float(r["similarity"]) if r.get("similarity") is not None else 0.0
    sparse_sim = float(r["sparse_similarity"]) if r.get("sparse_similarity") is not None else 0.0
    hybrid_sim = DENSE_WEIGHT * dense_sim + SPARSE_WEIGHT * min(sparse_sim, 1.0)
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
        "longevity_score": float(r["longevity_score"]) if r["longevity_score"] is not None else None,
        "sillage_score": float(r["sillage_score"]) if r["sillage_score"] is not None else None,
        "similarity": hybrid_sim,
        "match_score": round(hybrid_sim * 100, 1),
        "savings": None,
        "url": r.get("url"),
        "country": r.get("country"),
        "perfumer": r.get("perfumer"),
        "has_limited_data": has_limited_data,
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
    excluded_note_patterns: list[str] | None = None, gender: str | None = None,
):
    """Runs the ANN candidate-pool query. When `reference_id` is given (the
    caller already resolved a named perfume to a row in our own DB), compare
    candidates directly against THAT row's actual stored embedding via a SQL
    subquery - skips model inference entirely (near-instant) and scores
    against the real vector instead of a text reconstruction of its accords/
    notes re-embedded through the model.

    The `gender` clause (`$7`) only ever excludes a candidate explicitly
    tagged the *opposite* of what was requested - NULL (unknown) and
    'unisex' rows always pass through untouched. This used to be a Python-
    only soft penalty in decision_engine._gender_fit (0.4x on a mere
    GENDER_WEIGHT=0.08 dimension - a ~3-point effect on the final score,
    easily buried under a perfume that otherwise matches well). That's why
    a candidate explicitly named e.g. "...for Women" could still surface at
    59-73% and rank in the top few results for an explicit male request -
    caught live, not by any unit test, since the unit tests exercise
    _gender_fit's return value in isolation, not whether that value's
    weight is actually large enough to matter in a real ranked list. Kept as
    a hard SQL-level exclusion (same pattern as negated_terms below), not
    just a stronger Python penalty, because an explicitly opposite-gender
    product is a correctness issue for the user, not a matter of degree -
    the Python-side leaning modifier for genuinely unisex-but-skewing
    scents is untouched and still applies its own softer nudge.

    ORDER BY sorts on the raw `embedding <=> ...` distance operator directly,
    not the `similarity` column computed via `1 - (...)` - confirmed via
    EXPLAIN against the live 40,649-row table: sorting by `similarity`
    (a math expression on top of the operator) prevented the planner from
    matching it to idx_perfumes_embedding's HNSW operator class at all, so
    every query - not just ones with a wide-open/unfiltered price range -
    fell back to a Seq Scan (cost ~31,088, all 40,649 rows read and sorted
    in memory). Sorting by the bare operator lets it use the index directly
    (cost ~92-160, an Index Scan on idx_perfumes_embedding) - `similarity`
    itself is still selected and returned unchanged, downstream code
    (_format_perfume_row's match_score) doesn't need to know the sort key
    changed.

    hnsw.ef_search is raised (via a transaction-scoped SET LOCAL, so it
    never leaks onto some other query sharing the same pooled connection
    afterward) before running the index-scan query. This isn't optional
    tuning: HNSW is an *approximate* search - the index scan only walks its
    default-sized candidate window, and a restrictive WHERE filter (e.g. the
    dupe engine's exclude_family_brand dropping an entire well-known brand's
    lineup) can filter that whole window down to zero survivors even though
    plenty of real matches exist further out - reproduced live (a real
    "cheaper alternative to Bleu de Chanel" search returned 0 rows with the
    driver default, 10 good ones once ef_search was raised). Scaled off
    pool_size (which already grows for budget-constrained searches, the
    exact case most likely to filter hard) rather than a single fixed
    constant, capped at 1000 to keep the exhaustiveness/latency tradeoff
    reasonable."""
    ef_search = dynamic_ef_search(pool_size, budget=budget, has_exclusions=bool(exclude_family_brand or excluded_note_patterns))
    if reference_id is not None:
        sql = """
            SELECT id, brand, perfume, price_inr, notes, main_accords, type,
                   gender, longevity_score, sillage_score,
                   top_notes, heart_notes, base_notes,
                   url, country, perfumer,
                   1 - (embedding <=> (SELECT embedding FROM perfumes WHERE id = $1)) AS similarity,
                   COALESCE(ts_rank(search_vector, plainto_tsquery('english', $8::text)), 0) AS sparse_similarity
            FROM perfumes
            WHERE ($2::float IS NULL OR price_inr <= $2) AND ($4::int IS NULL OR id != $4)
              AND ($5::text IS NULL OR NOT (brand ILIKE '%' || $5 || '%' OR $5 ILIKE '%' || brand || '%'))
              AND ($6::text[] IS NULL OR NOT EXISTS (
                  SELECT 1 FROM unnest(COALESCE(notes, '{}') || COALESCE(main_accords, '{}')) AS n
                  WHERE n ~* ANY($6::text[])
              ))
              AND ($7::text IS NULL OR gender IS NULL OR gender = 'unisex' OR gender = $7)
            ORDER BY embedding <=> (SELECT embedding FROM perfumes WHERE id = $1) ASC
            LIMIT $3
        """
        async with db.transaction():
            await db.execute(f"SET LOCAL hnsw.ef_search = {ef_search}")
            return await db.fetch(sql, reference_id, budget, pool_size, exclude_id, exclude_family_brand,
                                   excluded_note_patterns, gender, query)

    embedding = await generate_embedding_async(query, is_query=True)
    # Plain query for FTS — strip BGE prefixes if present
    fts_query = query
    if fts_query.startswith("Represent this sentence for searching relevant passages: "):
        fts_query = fts_query[len("Represent this sentence for searching relevant passages: "):]
    sql = """
        SELECT id, brand, perfume, price_inr, notes, main_accords, type,
               gender, longevity_score, sillage_score,
               top_notes, heart_notes, base_notes,
               url, country, perfumer,
               1 - (embedding <=> $1::vector) AS similarity,
               COALESCE(ts_rank(search_vector, plainto_tsquery('english', $8::text)), 0) AS sparse_similarity
        FROM perfumes
        WHERE ($2::float IS NULL OR price_inr <= $2) AND ($4::int IS NULL OR id != $4)
          AND ($5::text IS NULL OR NOT (brand ILIKE '%' || $5 || '%' OR $5 ILIKE '%' || brand || '%'))
          AND ($6::text[] IS NULL OR NOT EXISTS (
              SELECT 1 FROM unnest(COALESCE(notes, '{}') || COALESCE(main_accords, '{}')) AS n
              WHERE n ~* ANY($6::text[])
          ))
          AND ($7::text IS NULL OR gender IS NULL OR gender = 'unisex' OR gender = $7)
        ORDER BY embedding <=> $1::vector ASC
        LIMIT $3
    """
    async with db.transaction():
        await db.execute(f"SET LOCAL hnsw.ef_search = {ef_search}")
        return await db.fetch(sql, _to_pgvector_literal(embedding), budget, pool_size, exclude_id,
                               exclude_family_brand, excluded_note_patterns, gender, fts_query)


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
    pool_size = _candidate_pool_size(limit)
    excluded_note_patterns = _build_exclusion_patterns(negated_terms)
    rows = await _fetch_candidates(db, query, reference_id, budget, pool_size, exclude_id, exclude_family_brand,
                                    excluded_note_patterns, gender)

    results = [_format_perfume_row(r) for r in rows]
    return rank_and_explain(
        results, query=raw_query, budget=budget, scenarios=scenarios, skin_type=skin_type,
        gender=gender, age=age, longevity_requested=longevity_requested,
        hours_required=hours_required, projection_preference=projection_preference, limit=limit,
        reference_accords=reference_accords, reference_notes=reference_notes, deal_breaker=deal_breaker,
        negated_terms=negated_terms, note_families=note_families,
    )


FUZZY_REFERENCE_THRESHOLD = 0.3

# Shared by both perfume-name-only tiers below: matches are grouped into two
# quality tiers (real note data vs none - the same signal the existing
# ORDER BY already uses to prefer the better-documented row), and only the
# distinct brand STRINGS tied at the BEST tier actually present are handed
# back to Python for a same-brand-group check (`_is_same_brand_group`) before
# a match is accepted. This is deliberately not "reject on any cross-brand
# collision at all": e.g. "Aventus" collides between "Creed" (real note
# data) and "Creedfor" (a distinct, lower-priority catalog entry with no
# note data at all) - the notes-tier filter alone already drops "Creedfor"
# out of contention here, no brand-grouping needed. But "Sauvage" collides
# between "Dior" and "Christian Dior" - BOTH real, BOTH with real note data,
# tied at the same best tier - and those are the same real fashion house
# under two different name granularities in this dataset, not a genuine
# conflict; naively counting them as 2 distinct brands broke this exact
# query in production (confirmed live: resolved to an unrelated brand
# instead of Dior). `_is_same_brand_group` resolves that. Ambiguity only
# genuinely blocks a match when the best-tier brands *aren't* recognizably
# the same house - e.g. "Black", which collides across 19 real, unrelated,
# similarly-documented brands with no principled way to prefer one.
_AMBIGUITY_GUARD_CTE = """
    matches AS MATERIALIZED (
        SELECT id, brand, perfume, main_accords, notes, price_inr, gender,
               (notes IS NULL OR array_length(notes, 1) IS NULL) AS notes_missing
        FROM perfumes
        WHERE length(perfume) >= 4
          AND {match_condition}
    ),
    best_tier AS MATERIALIZED (
        SELECT min(notes_missing::int) AS best FROM matches
    ),
    agg AS MATERIALIZED (
        SELECT array_agg(DISTINCT lower(m.brand)) AS best_tier_brands
        FROM matches m, best_tier b
        WHERE m.notes_missing::int = b.best
    )
"""

# Minimum length for the "core" brand name in _is_same_brand_group - guards
# against a short, generic fragment coincidentally appearing inside an
# unrelated longer brand name. Every real same-brand collision found by
# scanning the actual ~40,649-row catalog (see the PR/commit this landed in)
# had a core of 4+ characters ("dior", "avon", "memo", "akon" were the
# shortest); nothing observed needed anything shorter.
_BRAND_GROUP_MIN_CORE_LEN = 4


def _is_same_brand_group(brands: list[str]) -> bool:
    """True if every brand string is the same real house under a different
    name granularity or a data-source naming quirk, not a genuine collision
    between unrelated brands. Expects already-lowercased, deduplicated
    strings (as produced by `_AMBIGUITY_GUARD_CTE`'s `best_tier_brands`).

    Deliberately a RAW substring check, not the whole-word-boundary
    containment used elsewhere in this codebase for notes/accords
    (`_notes_equivalent` in decision_engine.py): a large, systematic slice of
    this catalog's brands (Creed, Dior, Avon, Chanel, Kenzo, and ~25 others)
    has a second, data-sparse entry named "<brand>for" with NO space -
    "creedfor" has no word boundary after "creed", so a word-bounded check
    would never link them. Verified empirically against the live catalog:
    every one of the 39 real cross-brand name collisions found there (things
    like "christian dior"/"dior", "ajmal"/"ajmal perfumes", "memo"/"memo
    paris") was a genuine same-house variant, not a coincidental unrelated
    match - substring containment is safe here specifically because brand
    names are a much smaller, more curated vocabulary than notes/accords
    are, not because raw substring matching is safe in general.

    The rule: the shortest name in the group is the "core" (e.g. "dior" out
    of "dior"/"christian dior"/"diorfor"); if every other name in the group
    contains it, they're the same group. This also means a genuinely
    unrelated brand breaks the group correctly (it won't contain the core),
    failing safe toward "ambiguous" rather than over-grouping."""
    if len(brands) <= 1:
        return True
    core = min(brands, key=len)
    if len(core) < _BRAND_GROUP_MIN_CORE_LEN:
        return False
    return all(core in b for b in brands)


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
    brand (e.g. 'Armaf' vs 'Armani' score ~0.67 on this same metric).

    The two perfume-name-only tiers further down drop the brand from the
    WHERE clause entirely (by design - that's what lets them recover a query
    that names a perfume without its brand at all), so they compute the
    best-tier brand set in SQL (`_AMBIGUITY_GUARD_CTE`) and only accept the
    top row when `_is_same_brand_group` confirms it's genuinely unambiguous -
    see that constant's and function's own comments for why a same-name
    collision isn't always a real conflict."""
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
    cleaned_query = _clean_query_for_lookup(query)

    if not row and len(cleaned_query) >= 4:
        perfume_only_sql = f"""
            WITH {_AMBIGUITY_GUARD_CTE.format(match_condition="$1 ILIKE '%' || perfume || '%'")}
            SELECT m.id, m.brand, m.perfume, m.main_accords, m.notes, m.price_inr, m.gender,
                   a.best_tier_brands
            FROM matches m, agg a
            ORDER BY m.notes_missing, length(m.perfume) ASC
            LIMIT 1
        """
        candidate = await db.fetchrow(perfume_only_sql, cleaned_query)
        if candidate and _is_same_brand_group(candidate["best_tier_brands"]):
            row = candidate

    if not row and len(cleaned_query) >= 3:
        # Uses cleaned_query, not the raw query: pg_trgm's word_similarity
        # finds the best-matching SUBSTRING of the longer string, so a filler
        # phrase still in the raw query ("dupe for", "cheaper alternative
        # to") isn't just noise here - it actively creates false matches. The
        # word "for" alone scores >0.3 similarity against every "<brand>for"
        # knockoff-brand row in the catalog (confirmed live: raw query "dupe
        # for Ajmal" matched "Avonfor"/"Aqua for Her" - a brand and product
        # neither the brand nor the perfume the user asked about - purely
        # because both contain "for"). Stripping filler words before fuzzy
        # matching removes that false signal entirely without weakening
        # real typo tolerance (the actual brand/perfume name text is
        # untouched by _clean_query_for_lookup).
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
        row = await db.fetchrow(fuzzy_sql, cleaned_query, FUZZY_REFERENCE_THRESHOLD)

    if not row and len(cleaned_query) >= 4:
        fuzzy_perfume_only_sql = f"""
            WITH {_AMBIGUITY_GUARD_CTE.format(match_condition="word_similarity(perfume, $1) > $2")}
            SELECT m.id, m.brand, m.perfume, m.main_accords, m.notes, m.price_inr, m.gender,
                   a.best_tier_brands
            FROM matches m, agg a
            ORDER BY m.notes_missing, word_similarity(m.perfume, $1) DESC, length(m.perfume) ASC
            LIMIT 1
        """
        candidate = await db.fetchrow(fuzzy_perfume_only_sql, cleaned_query, 0.45)
        if candidate and _is_same_brand_group(candidate["best_tier_brands"]):
            row = candidate

    if not row:
        return None
    return {
        "id": row["id"], "brand": row["brand"], "perfume": row["perfume"],
        "main_accords": row["main_accords"] or [], "notes": _clean_notes(row["notes"] or []),
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
    pool_size = _candidate_pool_size(limit)
    excluded_note_patterns = _build_exclusion_patterns(negated_terms)
    rows = await _fetch_candidates(db, query, reference_id, budget, pool_size, exclude_id, exclude_family_brand,
                                    excluded_note_patterns, gender)

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
    notes, top_notes, heart_notes, base_notes, has_limited_data = _clean_notes_and_pyramid(r)
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
        "has_limited_data": has_limited_data,
    }


async def check_health(db) -> bool:
    try:
        await db.fetchval("SELECT 1")
        return True
    except Exception:
        return False
