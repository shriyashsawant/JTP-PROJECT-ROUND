"""
AuraMatch AI - Decision Engine
Hybrid scoring + deterministic explanation generator.
Modular: swap `scorer` and `explainer` with an LLM later (just implement the same interface).
"""
import re
from collections.abc import Callable

from app.services.scenario_map import (
    AGE_BRACKET_ACCORDS,
    BASE_ACCORDS,
    BASE_TIER_FAMILIES,
    NOTE_FAMILIES,
    NOTE_FAMILY_LABELS,
    SCENARIO_MAP,
    TOP_ACCORDS,
    TOP_TIER_FAMILIES,
    age_to_bracket,
    estimate_hours_numeric,
    estimate_wear_hours,
    get_note_family,
    sillage_label,
)

# ---------------------------------------------------------------------------
# 1. Hybrid Scorer
# ---------------------------------------------------------------------------
# Weights reflect what actually drives a good recommendation for a specific
# occasion: occasion/season fit and longevity matter far more than raw
# semantic similarity or shaving a few rupees off an already-affordable price.

SIM_WEIGHT = 0.07
NOTE_MATCH_WEIGHT = 0.20
SCENARIO_WEIGHT = 0.28
LONGEVITY_WEIGHT = 0.20
PROJECTION_WEIGHT = 0.10
NOTE_FAMILY_WEIGHT = 0.15
BRIDGE_WEIGHT = 0.15
PRICE_WEIGHT = 0.05
GENDER_WEIGHT = 0.08
AGE_WEIGHT = 0.05

# Scenarios/note families that signal the user wants a fresh, volatile-top
# profile - used only to detect the fresh-vs-longevity contradiction (see
# _bridge_fit), not as a general "fresh" scoring signal elsewhere.
FRESH_SCENARIOS = {"gym", "summer"}
FRESH_NOTE_FAMILIES = {"citrus", "fresh_aquatic", "green"}


def _price_fit(price_inr: float | None, budget: float | None, deal_breaker: bool = False) -> float:
    """1.0 (no-op) if no budget set. Otherwise rewards how well the price uses the
    budget the user gave us: by default, closer to the budget ceiling scores higher
    (they told us what they're willing to spend - a recommendation that uses more
    of it is usually a better perfume, not a compromise). In `deal_breaker` mode
    this flips: cheaper scores higher, since price is the user's overriding
    concern rather than one factor among several."""
    if budget is None or budget <= 0 or price_inr is None:
        return 1.0
    if price_inr > budget:
        return 0.0
    if deal_breaker:
        return 1.0 - (price_inr / budget)
    return price_inr / budget


def _gender_fit(perfume_gender: str | None, requested_gender: str | None) -> float:
    """1.0 (no-op) unless the user asked for a gender AND the perfume is explicitly
    tagged as the other gender - then a soft penalty (never zero, never excludes)."""
    if not requested_gender:
        return 1.0
    if not perfume_gender or perfume_gender == "unisex":
        return 1.0
    if perfume_gender == requested_gender:
        return 1.0
    return 0.4


def _gender_leaning_modifier(
    perfume_gender: str | None,
    requested_gender: str | None,
    notes: list[str],
    accords: list[str],
) -> float:
    """Evaluates if a unisex perfume leans masculine or feminine based on its notes
    and accords, returning a slight penalty (0.85) if it leans opposite to the
    user's requested gender. This prevents suggesting overly sweet, floral unisex
    scents to someone asking for masculine scents, and vice-versa, matching the
    leaning slider behavior of premium fragrance databases.

    Note matching uses `_notes_equivalent` (whole-word containment), not a raw
    substring check - a substring check would match masc/fem keywords inside
    unrelated compound note names (e.g. "rose" is a raw substring of both
    "Rosemary", an aromatic herb with no real feminine association, and
    "Tuberose", a genuinely feminine white floral - the former is a false
    positive, the latter only "worked" by accident). "tuberose" is listed
    explicitly below instead, so it counts on purpose rather than by luck."""
    if not requested_gender or not perfume_gender:
        return 1.0
    if perfume_gender != "unisex":
        return 1.0

    notes_set = {n.lower() for n in notes}
    accords_set = {a.lower() for a in accords}

    masc_accords = {"woody", "leather", "tobacco", "spicy", "earthy", "smoky", "animalic"}
    masc_notes = {"cedar", "vetiver", "leather", "tobacco", "pepper", "oakmoss", "patchouli", "sandalwood", "guaiac wood", "birch"}

    fem_accords = {"floral", "fruity", "sweet", "vanilla", "gourmand"}
    fem_notes = {"rose", "jasmine", "vanilla", "vanille", "peony", "gardenia", "magnolia", "peach", "coconut", "caramel", "sugar", "tuberose"}

    masc_count = len(accords_set & masc_accords) + sum(1 for n in notes_set if any(_notes_equivalent(mn, n) for mn in masc_notes))
    fem_count = len(accords_set & fem_accords) + sum(1 for n in notes_set if any(_notes_equivalent(fn, n) for fn in fem_notes))

    if requested_gender == "male" and fem_count > masc_count + 1:
        return 0.85  # leans feminine
    if requested_gender == "female" and masc_count > fem_count + 1:
        return 0.85  # leans masculine

    return 1.0


# Concentration -> (longevity_multiplier, sillage_multiplier). Ordered by
# actual oil concentration strength (Extrait/Parfum 20-40% down to Body
# Spray ~1-3%) so Eau de Parfum gets its own, more moderate adjustment
# instead of being conflated with the meaningfully stronger Extrait/pure-
# Parfum tier. Keyed on `_parse_concentration_type`'s exact (lowercased)
# output - see `_adjust_performance_by_type` for why this is an exact-match
# table rather than substring matching.
TYPE_PERFORMANCE_ADJUSTMENTS: dict[str, tuple[float, float]] = {
    "extrait de parfum": (1.15, 0.85),
    "elixir": (1.15, 0.85),
    "parfum": (1.15, 0.85),
    "eau de parfum": (1.08, 0.93),
    "eau de toilette": (0.90, 1.10),
    "eau de cologne": (0.75, 1.15),
    "body spray": (0.50, 0.70),
}


def _adjust_performance_by_type(
    longevity_score: float | None,
    sillage_score: float | None,
    perfume_type: str | None,
) -> tuple[float | None, float | None]:
    """Dynamically adjusts database longevity and sillage scores based on the
    perfume's concentration type, aligning the deterministic scorer with
    physical fragrance chemistry: higher-concentration formulations
    (Extrait/Parfum, 20-40% oil) last longer but project less (sit closer to
    the skin); lighter ones (Cologne, 2-4%) fade faster but burst brighter on
    application.

    Exact-match lookup, not substring matching: `perfume_type` only ever
    comes from `_parse_concentration_type` (db_repository.py), which returns
    exactly one of TYPE_PERFORMANCE_ADJUSTMENTS' 7 keys or None - there is no
    other producer of this field (the raw DB `type` column is always NULL
    from seeding). A substring check here previously conflated tiers that
    are meaningfully different in strength: "Eau de Parfum" (15-20%
    concentration) was matched by a bare `"parfum" in t` check and got the
    exact same +15%/-15% adjustment as Extrait/pure Parfum (20-40%
    concentration) - a real formulation-strength difference the scorer
    should reflect, not just a typo of `==` vs `in`. Each tier now has its
    own distinct, concentration-appropriate multiplier instead."""
    if not perfume_type or longevity_score is None or sillage_score is None:
        return longevity_score, sillage_score

    adjustment = TYPE_PERFORMANCE_ADJUSTMENTS.get(perfume_type.lower())
    if not adjustment:
        return longevity_score, sillage_score

    longevity_mult, sillage_mult = adjustment
    l_adj = longevity_score * longevity_mult
    s_adj = sillage_score * sillage_mult
    l_adj = min(100.0, l_adj) if longevity_mult > 1 else max(0.0, l_adj)
    s_adj = min(100.0, s_adj) if sillage_mult > 1 else max(0.0, s_adj)
    return round(l_adj, 1), round(s_adj, 1)


def _fuzzy_overlap_count(items: set[str], targets: set[str]) -> int:
    """Count how many `items` have at least one whole-word-equivalent match in
    `targets` (via `_notes_equivalent`, defined below) rather than requiring
    an exact string match. Matters here because DB note names are often more
    specific than SCENARIO_MAP's generic vocabulary (e.g. a perfume tagged
    "Sicilian Lemon" or "Indonesian Patchouli Leaf" would never exactly-match
    a scenario's plain "lemon"/"patchouli" note entry, so raw set
    intersection silently loses credit for perfumes that are a real match)."""
    count = 0
    for item in items:
        if any(_notes_equivalent(item, target) for target in targets):
            count += 1
    return count


def _scenario_fit(perfume_accords: list[str], perfume_notes: list[str], matched_scenarios: list[str]) -> float:
    """1.0 (no-op) if no occasion/season was signalled. Otherwise, a 70/30 blend
    of accord overlap and note overlap against the union of matched scenarios'
    vocab (2+ overlapping accords, or 3+ overlapping notes, = full credit on
    that axis). SCENARIO_MAP defines both an accord vocab AND a notes vocab
    per scenario, but only accords were ever read here - the notes were
    already being generated into the embedding text and displayed to the
    user, but silently ignored by this deterministic scorer."""
    if not matched_scenarios:
        return 1.0
    target_accords: set[str] = set()
    target_notes: set[str] = set()
    for s in matched_scenarios:
        if s in SCENARIO_MAP:
            target_accords.update(a.lower() for a in SCENARIO_MAP[s]["accords"])
            target_notes.update(n.lower() for n in SCENARIO_MAP[s].get("notes", []))
    if not target_accords and not target_notes:
        return 1.0
    accord_set = {a.lower() for a in (perfume_accords or [])}
    note_set = {n.lower() for n in (perfume_notes or [])}
    accord_score = min(1.0, len(accord_set & target_accords) / 2.0) if target_accords else 1.0
    note_score = min(1.0, _fuzzy_overlap_count(note_set, target_notes) / 3.0) if target_notes else 1.0
    return accord_score * 0.7 + note_score * 0.3


def _longevity_fit(
    longevity_score: float | None, longevity_requested: bool, hours_required: int | None,
) -> float:
    """1.0 (no-op) unless longevity was signalled. A soft 'long lasting' phrase scales
    with longevity_score; an explicit 'N+ hours' requirement is enforced as a real
    threshold - falling short is penalized (floored at 0.2, never zero)."""
    if not longevity_requested and not hours_required:
        return 1.0
    if longevity_score is None:
        return 0.5
    if hours_required:
        estimated = estimate_hours_numeric(longevity_score)
        if estimated >= hours_required:
            return 1.0
        return max(0.2, estimated / hours_required)
    return max(0.0, min(1.0, longevity_score / 100.0))


def _projection_fit(sillage_score: float | None, projection_preference: str | None) -> float:
    """1.0 (no-op) unless the user specified a projection preference (light/moderate/strong)."""
    if not projection_preference:
        return 1.0
    actual = sillage_label(sillage_score)
    order = ["light", "moderate", "strong"]
    if actual == "unknown" or actual not in order:
        return 0.6
    diff = abs(order.index(actual) - order.index(projection_preference))
    return {0: 1.0, 1: 0.6, 2: 0.2}[diff]


def _normalize_for_match(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace - keeps word boundaries
    intact (unlike stripping spaces entirely) so phrase matching stays accurate."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _contains_phrase(query_norm: str, phrase_norm: str) -> bool:
    """Word-boundary phrase search - NOT a raw substring check, so a perfume
    named e.g. 'Ice' can't false-positive match inside 'notice' or 'spice'."""
    if not phrase_norm:
        return False
    return re.search(rf"\b{re.escape(phrase_norm)}\b", query_norm) is not None


IDENTITY_BONUS_EXACT = 35.0    # query IS "brand perfume", nothing else (e.g. "Dior Sauvage Elixir" naming that exact flanker)
IDENTITY_BONUS_FULL = 30.0     # "brand perfume" as one contiguous phrase, but query has extra words beyond it
IDENTITY_BONUS_BOTH = 25.0     # brand and perfume both present, not contiguous
IDENTITY_BONUS_NAME = 15.0     # perfume name alone
IDENTITY_BONUS_BRAND = 8.0     # brand alone (least specific - many products share it)


def _identity_boost(raw_query: str, brand: str, perfume_name: str) -> tuple[float, str | None]:
    """Deterministic lexical boost: if the user's raw query literally names this
    exact perfume or brand, spike its score - bypassing embedding fuzziness
    entirely for the 'I want THIS specific perfume' case. Zero latency, zero new
    dependencies, zero DB/schema risk. Length guards on each tier prevent short/
    generic names from false-positive-boosting unrelated results."""
    if not raw_query:
        return 0.0, None
    q = _normalize_for_match(raw_query)
    if len(q) < 3:
        return 0.0, None
    b = _normalize_for_match(brand)
    p = _normalize_for_match(perfume_name)
    label = f"{brand} — {perfume_name}"

    combined = f"{b} {p}".strip()
    if len(combined) >= 6 and _contains_phrase(q, combined):
        # An EXACT match (query is precisely this brand+name, e.g. "Dior Sauvage
        # Elixir" naming that flanker exactly) gets a distinct, higher tier than
        # a partial match (e.g. the same query also contains "Dior Sauvage" as a
        # substring, matching the base "Sauvage" row too). Without this
        # separation both would round to the same capped 100 score and the
        # display would show a coin-flip order between the specific flanker
        # the user actually asked for and a shorter, less specific variant.
        if q == combined:
            return IDENTITY_BONUS_EXACT, label
        return IDENTITY_BONUS_FULL, label
    if len(p) >= 4 and len(b) >= 3 and _contains_phrase(q, p) and _contains_phrase(q, b):
        return IDENTITY_BONUS_BOTH, label
    if len(p) >= 4 and _contains_phrase(q, p):
        return IDENTITY_BONUS_NAME, perfume_name
    if len(b) >= 4 and _contains_phrase(q, b):
        return IDENTITY_BONUS_BRAND, brand
    return 0.0, None


def _jaccard(a: list[str], b: list[str]) -> float:
    """Real set-overlap similarity (intersection / union), 0-1. 0 if either side is empty."""
    a_set, b_set = {x.lower() for x in (a or [])}, {y.lower() for y in (b or [])}
    if not a_set or not b_set:
        return 0.0
    return len(a_set & b_set) / len(a_set | b_set)


def _notes_equivalent(a: str, b: str) -> bool:
    """Two note/accord labels count as the "same" if identical, or one is the
    other plus extra descriptive words (e.g. "Jasmine" / "Moroccan Jasmine",
    "Woody" / "Woody Notes") - a whole-word containment check, not a raw
    substring check, so "Musk" doesn't false-match "Musky" (a different
    standard Fragrantica accord category) or "Rose" match inside "Roseview".
    Deliberately NOT fuzzy/edit-distance matching: containment has no false-
    positive risk, whereas tolerating misspellings could conflate genuinely
    different short note names."""
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    return re.search(rf"\b{re.escape(shorter)}\b", longer) is not None


def _fuzzy_jaccard(a: list[str] | None, b: list[str] | None) -> float:
    """Like `_jaccard`, but treats descriptive variants of the same note/accord
    as equivalent (via `_notes_equivalent`) instead of requiring an exact
    string match. This matters for reference-composition scoring: crowd-
    tagged accord/note vocabularies are inconsistent across data sources, so
    two perfumes the fragrance community considers near-identical can still
    have near-zero *exact*-string overlap in our data purely from tagging
    differences (one tagged "Jasmine", the other "Moroccan Jasmine").
    Reduces to standard Jaccard when only exact matches exist. Uses greedy
    (not maximum) bipartite matching - fine at this list size (a handful of
    notes/accords per perfume) and keeps the logic simple and deterministic."""
    a_norm = [x.lower().strip() for x in (a or []) if x and x.strip()]
    b_norm = [y.lower().strip() for y in (b or []) if y and y.strip()]
    if not a_norm or not b_norm:
        return 0.0
    used_b = [False] * len(b_norm)
    matches = 0
    for x in a_norm:
        for i, y in enumerate(b_norm):
            if not used_b[i] and _notes_equivalent(x, y):
                used_b[i] = True
                matches += 1
                break
    union = len(a_norm) + len(b_norm) - matches
    return matches / union if union else 0.0


def _reference_fit(
    candidate_accords: list[str], candidate_notes: list[str],
    reference_accords: list[str] | None, reference_notes: list[str] | None,
) -> float:
    """Real, quantitative composition similarity to a named reference perfume
    (the 'dupe engine' case) - accords weighted higher than notes since they
    summarize the perfume's overall character, notes are granular ingredients.
    This replaces guessing via raw-text embedding similarity with an actual
    calculated overlap between the two perfumes' real compositions."""
    accord_sim = _fuzzy_jaccard(candidate_accords, reference_accords)
    note_sim = _fuzzy_jaccard(candidate_notes, reference_notes)
    return accord_sim * 0.65 + note_sim * 0.35


def _note_family_fit(
    perfume_notes: list[str], perfume_accords: list[str], note_families: list[str] | None,
) -> float:
    """1.0 (no-op) unless the user picked "Scent Preference" note families in
    the search form. Otherwise, the fraction of the requested families that
    this perfume has at least one matching note/accord for (whole-word-
    equivalent match, not exact string - same reasoning as `_scenario_fit`'s
    note overlap). Previously `note_families` was only ever used to expand
    the embedding query text (see ml_engine.build_context_query) and then
    silently dropped by this deterministic scorer - a result could rank highly
    on text similarity alone while containing zero notes from a family the
    user explicitly asked for."""
    if not note_families:
        return 1.0
    valid_families = [f for f in note_families if f in NOTE_FAMILIES]
    if not valid_families:
        return 1.0
    haystack = [n.lower() for n in (perfume_notes or [])] + [a.lower() for a in (perfume_accords or [])]
    matched = 0
    for family in valid_families:
        family_terms = [t.lower() for t in NOTE_FAMILIES[family]]
        if any(_notes_equivalent(term, h) for term in family_terms for h in haystack):
            matched += 1
    return matched / len(valid_families)


def _bridge_fit(
    top_notes: list[str], base_notes: list[str], perfume_accords: list[str],
    wants_fresh: bool, wants_longevity: bool,
) -> float:
    """1.0 (no-op) unless the user wants BOTH a fresh/energetic profile (gym/
    summer scenario, or a citrus/fresh_aquatic/green note-family preference)
    AND explicit long-lasting performance - a real chemical contradiction:
    volatile fresh molecules (citrus, aquatic) evaporate fast, so a query
    like "fresh gym scent that lasts 12 hours" can't be satisfied by a
    single-tier match. Rewards perfumes built as a "bridge": a genuinely
    fresh TOP paired with a dense, long-lasting BASE (ambroxan/musk/woody/
    vetiver) - rather than silently recommending a heavy oud (satisfies
    longevity, fails the fresh ask) or a pure citrus (satisfies fresh, fades
    in under an hour). `top_notes`/`base_notes` are the pyramid tier arrays
    populated at seed time (see seed_data.resolve_note_tiers) - real
    Fragrantica tags where available, otherwise inferred from note family.

    Falls back to `perfume_accords` for whichever side notes couldn't answer:
    21% of the catalog (8,721 rows) has no notes at all, but 96% of those
    still have main_accords - without this fallback, a perfume would score
    the worst possible bridge fit (0.2) purely because notes data happens to
    be missing, not because it's actually a poor fresh-top/dense-base match.
    Accords are a coarser signal than notes (a summary tag, not a specific
    ingredient), so they only fill a gap - they never override a real
    notes-derived answer on the side that already has one."""
    if not (wants_fresh and wants_longevity):
        return 1.0
    has_fresh_top = any(get_note_family(n) in TOP_TIER_FAMILIES for n in (top_notes or []))
    has_dense_base = any(get_note_family(n) in BASE_TIER_FAMILIES for n in (base_notes or []))
    if not has_fresh_top or not has_dense_base:
        # main_accords are already family-level labels ("citrus", "woody"),
        # not member notes - get_note_family expects the latter (it looks up
        # whether a note NAME belongs to a family, not whether a string IS a
        # family), so accords need their own direct membership check here
        # via TOP_ACCORDS/BASE_ACCORDS instead.
        accords_lower = {a.lower() for a in (perfume_accords or [])}
        if not has_fresh_top:
            has_fresh_top = bool(accords_lower & TOP_ACCORDS)
        if not has_dense_base:
            has_dense_base = bool(accords_lower & BASE_ACCORDS)
    if has_fresh_top and has_dense_base:
        return 1.0
    if has_fresh_top or has_dense_base:
        return 0.5
    return 0.2


def _negation_penalty(
    perfume_accords: list[str], perfume_notes: list[str], negated_terms: list[str] | None,
) -> tuple[float, str | None]:
    """1.0 (no-op) unless the user named notes/accords they explicitly don't
    want (e.g. "no vanilla", "not sweet"). Heavily scales down - rather than
    zeroing out - a candidate whose own accords/notes contain a negated term:
    a perfume can list a trace note without being dominated by it, so this is
    a strong deprioritization, not a hard exclusion. Reuses `_notes_equivalent`
    (whole-word containment) so "no vanilla" also catches a candidate tagged
    "Vanilla Bean", not just an exact string match. Returns the matched term
    too, so the caller can surface which negated note actually hit."""
    if not negated_terms:
        return 1.0, None
    haystack = [a.lower() for a in (perfume_accords or [])] + [n.lower() for n in (perfume_notes or [])]
    for term in negated_terms:
        for h in haystack:
            if _notes_equivalent(term, h) or _notes_equivalent(h, term):
                return 0.25, term
    return 1.0, None


def _age_fit(perfume_accords: list[str], age: int | None) -> float:
    """1.0 (no-op) unless age was provided. A small, floored (0.6+) nudge toward
    accords that skew toward that age bracket per industry consumer research -
    a population-level trend, not a rule, so it can never dominate the score."""
    bracket = age_to_bracket(age)
    if not bracket:
        return 1.0
    perfume_set = {a.lower() for a in (perfume_accords or [])}
    if not perfume_set:
        return 0.8
    target = set(AGE_BRACKET_ACCORDS[bracket])
    overlap = perfume_set & target
    ratio = len(overlap) / len(perfume_set)
    return 0.6 + 0.4 * min(1.0, ratio * 2)


def hybrid_score(
    cosine_similarity: float,
    price_fit: float = 1.0,
    note_match: float = 0.0,
    gender_fit: float = 1.0,
    longevity_fit: float = 1.0,
    scenario_fit: float = 1.0,
    projection_fit: float = 1.0,
    age_fit: float = 1.0,
    note_family_fit: float = 1.0,
    bridge_fit: float = 1.0,
    has_budget: bool = False,
    has_gender: bool = False,
    has_longevity: bool = False,
    has_scenario: bool = False,
    has_projection: bool = False,
    has_age: bool = False,
    has_note_family: bool = False,
    has_bridge: bool = False,
) -> float:
    """
    Final Score = (sim*0.07 + note_match*0.20 + [scenario_fit*0.28] + [longevity_fit*0.20]
                + [projection_fit*0.10] + [note_family_fit*0.15] + [bridge_fit*0.15]
                + [price_fit*0.05] + [gender_fit*0.05] + [age_fit*0.05])
                / (0.27 + sum of included bracketed weights)

    Only the baseline scent-profile signal (similarity + note match) is always
    weighted; every other *_fit term - and its slice of the denominator - only
    counts when the user actually signalled that preference (has_budget,
    has_gender, etc). Previously every unsignalled term still contributed its
    neutral 1.0 default to a FIXED denominator of 1.0, so a query with zero
    occasion/longevity/projection/gender/age/budget intent still scored a
    flat 73% (the combined weight of those six neutral terms) before a single
    real note/similarity point was added - compressing every result into a
    narrow 73%-100% band regardless of actual match quality. Rescaling the
    denominator to only the active terms restores full 0%-100% contrast.
    """
    weights = {"sim": SIM_WEIGHT, "note": NOTE_MATCH_WEIGHT}
    weighted_sum = cosine_similarity * weights["sim"] + note_match * weights["note"]

    if has_budget:
        weights["price"] = PRICE_WEIGHT
        weighted_sum += price_fit * PRICE_WEIGHT
    if has_gender:
        weights["gender"] = GENDER_WEIGHT
        weighted_sum += gender_fit * GENDER_WEIGHT
    if has_longevity:
        weights["longevity"] = LONGEVITY_WEIGHT
        weighted_sum += longevity_fit * LONGEVITY_WEIGHT
    if has_scenario:
        weights["scenario"] = SCENARIO_WEIGHT
        weighted_sum += scenario_fit * SCENARIO_WEIGHT
    if has_projection:
        weights["projection"] = PROJECTION_WEIGHT
        weighted_sum += projection_fit * PROJECTION_WEIGHT
    if has_age:
        weights["age"] = AGE_WEIGHT
        weighted_sum += age_fit * AGE_WEIGHT
    if has_note_family:
        weights["note_family"] = NOTE_FAMILY_WEIGHT
        weighted_sum += note_family_fit * NOTE_FAMILY_WEIGHT
    if has_bridge:
        weights["bridge"] = BRIDGE_WEIGHT
        weighted_sum += bridge_fit * BRIDGE_WEIGHT

    scale = sum(weights.values())
    total = weighted_sum / scale if scale > 0 else 0.0
    return round(total * 100, 1)


# ---------------------------------------------------------------------------
# 2. Deterministic Explanation Generator
# ---------------------------------------------------------------------------

MATCH_STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "of", "in", "on", "for", "with", "without",
    "to", "is", "it", "its", "my", "your", "some", "any", "no", "not", "want", "wants",
    "need", "needs", "looking", "smell", "smells", "scent", "scents",
    "perfume", "perfumes", "fragrance", "fragrances", "notes", "note", "accord", "accords",
}


def _filter_match_terms(query_terms: list[str]) -> list[str]:
    """Drops generic descriptors ("notes", "scent", "perfume") and short stop
    words before note/accord matching - otherwise every perfume with a note
    literally named "green notes" or "woody notes" false-positive matches any
    query containing the word "notes", regardless of what's actually being
    searched for."""
    return [q for q in query_terms if q and q not in MATCH_STOP_WORDS and len(q) >= 3]


def _word_prefix_match(term: str, text: str) -> bool:
    """True if `term` begins at a word boundary inside `text` (not mid-word).
    Deliberately NOT end-anchored, so "bergamot" still matches inside
    "bergamots" - but this stops false positives like query term "men"
    matching inside the note "pimento" (the "men" there starts mid-word,
    with no boundary before it: pi-men-to)."""
    if not term:
        return False
    return re.search(rf"\b{re.escape(term)}", text) is not None


def _match_notes(query_terms: list[str], perfume_notes: list[str]) -> list[str]:
    """Find which perfume notes semantically match the query terms."""
    terms = _filter_match_terms([q.lower() for q in query_terms])
    matched = []
    for note in perfume_notes:
        n_lower = note.lower()
        for qt in terms:
            if _word_prefix_match(qt, n_lower) or _word_prefix_match(n_lower, qt):
                matched.append(note)
                break
    return matched


def _match_accords(query_terms: list[str], perfume_accords: list[str]) -> list[str]:
    """Find which accords match the query terms."""
    terms = _filter_match_terms([q.lower() for q in query_terms])
    matched = []
    for accord in perfume_accords:
        a_lower = accord.lower()
        for qt in terms:
            if _word_prefix_match(qt, a_lower) or _word_prefix_match(a_lower, qt):
                matched.append(accord)
                break
    return matched


SKIN_TYPE_PHRASES = {
    "dry": "Its rich base notes perform exceptionally well on dry skin, lasting longer than average.",
    "oily": "Its fresh top notes stay balanced on oily skin without becoming overwhelming.",
    "normal": "",
}


def _inr(amount: float) -> str:
    """Whole-rupee formatting - no trailing '.0' on prices/savings."""
    return f"₹{round(amount):,}"


def _pick_template(templates: list[str], seed: str) -> str:
    """Deterministically picks one template from a list using a hash of the given
    seed string - no randomness involved, just stable cross-platform hashing. The
    same seed (typically the perfume's own identity, or a signal-specific
    discriminator like 'price_phrase') always selects the same template, so every
    run of the same query produces identical explanation text."""
    return templates[hash(seed) % len(templates)]


def _price_phrase(price_inr: float | None, budget: float | None, perfume_name: str) -> str:
    """Budget is a threshold, not something to optimize - only call out exact
    savings when the price is a meaningful fraction of the budget; otherwise
    just confirm it's comfortably affordable."""
    if not price_inr:
        return ""
    if not budget or budget <= 0:
        return f" Priced at {_inr(price_inr)}."
    ratio = price_inr / budget
    seed = f"price_phrase_{perfume_name}_{_inr(price_inr)}_{budget}"
    if ratio <= 0.7:
        return _pick_template([
            f" Comfortably within your {_inr(budget)} budget.",
            f" Well inside your {_inr(budget)} budget, with room to spare.",
        ], seed)
    if price_inr < budget:
        return _pick_template([
            f" Priced at {_inr(price_inr)}, it provides luxury-tier quality while keeping {_inr(budget - price_inr)} under your budget.",
            f" At {_inr(price_inr)}, it saves you {_inr(budget - price_inr)} against your {_inr(budget)} budget.",
        ], seed)
    return f" At {_inr(price_inr)}, it sits right at your {_inr(budget)} budget ceiling."


SIGNATURE_TEMPLATES = [
    "Its {parts} anchor the profile.",
    "The chemistry leans on {parts}.",
    "It opens and develops around {parts}.",
]

LONGEVITY_MET_TEMPLATES = [
    "Estimated wear: {hours} — comfortably covers the {required}+ hours you need.",
    "Expect around {hours} of wear, well past the {required}+ hours you're after.",
]
LONGEVITY_SHORT_TEMPLATES = [
    "Estimated wear: {hours} — a bit short of the {required}+ hours you asked for; a reapplication may help.",
    "Realistically {hours} on skin — under your {required}+ hour target, so pack a travel spray if you need the full stretch.",
]
LONGEVITY_SOFT_TEMPLATES = ["Estimated wear: {hours}.", "On skin, expect roughly {hours}."]

PROJECTION_MET_TEMPLATES = [
    "Projects at a {label} level, matching what you asked for.",
    "Sillage sits at {label} — right where you wanted it.",
]
PROJECTION_MISS_TEMPLATES = [
    "Projects {label}ly — a bit different from the {wanted} projection you wanted.",
    "Its {label} sillage runs a little off your requested {wanted} projection.",
]

SCENARIO_MET_TEMPLATES = ["Well suited for {labels}.", "A natural fit for {labels}."]
SCENARIO_SOFT_TEMPLATES = ["Leans toward {labels} more than a perfect match.", "Reasonably suited for {labels}."]

GENDER_TEMPLATES = ["Tailored to the gender you specified.", "Formulated with your specified gender in mind."]


def _build_highlights(
    perfume_name: str,
    perfume_accords: list[str],
    scenario_labels: list[str], scenario_fit: float,
    matched_notes: list[str], matched_accords: list[str],
    longevity_requested: bool, hours_required: int | None, longevity_fit: float, longevity_score: float | None,
    projection_preference: str | None, projection_fit: float, sillage_score: float | None,
    gender_matched: bool,
    identity_label: str | None = None,
) -> list[str]:
    """The accord/note signature is ALWAYS this specific perfume's own composition
    (never generic), so it anchors every explanation and guarantees cards differ
    even when scenario/longevity/gender all tie at a perfect fit. A second slot
    then surfaces whichever other signal is most notable - prioritizing a
    shortfall (honesty about what's NOT fully met) over a redundant confirmation
    of something already true for every result. Phrasing is picked from small
    template pools seeded by the perfume's own identity, so cards vary in
    sentence rhythm as well as content."""
    highlights = []
    if identity_label:
        highlights.append(f"This is an exact match for **{identity_label}** you searched for.")

    signature_parts = []
    if matched_notes:
        signature_parts.append(f"prominent {', '.join(matched_notes[:3])} notes")
    accord_display = matched_accords[:3] if matched_accords else (perfume_accords or [])[:3]
    if accord_display:
        signature_parts.append(f"{', '.join(accord_display)} character")
    if signature_parts:
        highlights.append(_pick_template(SIGNATURE_TEMPLATES, f"sig_{perfume_name}").format(parts=" and ".join(signature_parts)))

    # Second slot: prefer a genuine shortfall (honesty), else the most specific
    # remaining detail (hour count is more informative than a repeated label).
    secondary: list[tuple[float, str]] = []

    if hours_required:
        hours_label = estimate_wear_hours(longevity_score)
        if longevity_fit >= 0.9:
            secondary.append((0.7, _pick_template(LONGEVITY_MET_TEMPLATES, f"long_met_{perfume_name}").format(hours=hours_label, required=hours_required)))
        else:
            secondary.append((0.99, _pick_template(LONGEVITY_SHORT_TEMPLATES, f"long_short_{perfume_name}").format(hours=hours_label, required=hours_required)))
    elif longevity_requested:
        secondary.append((0.6, _pick_template(LONGEVITY_SOFT_TEMPLATES, f"long_soft_{perfume_name}").format(hours=estimate_wear_hours(longevity_score))))

    if projection_preference:
        actual_label = sillage_label(sillage_score)
        if projection_fit >= 0.9:
            secondary.append((0.5, _pick_template(PROJECTION_MET_TEMPLATES, f"proj_met_{perfume_name}").format(label=actual_label)))
        else:
            secondary.append((0.95, _pick_template(PROJECTION_MISS_TEMPLATES, f"proj_miss_{perfume_name}").format(label=actual_label, wanted=projection_preference)))

    if scenario_labels:
        labels = ", ".join(scenario_labels)
        if scenario_fit >= 0.9:
            secondary.append((0.4, _pick_template(SCENARIO_MET_TEMPLATES, f"sc_met_{perfume_name}").format(labels=labels)))
        else:
            secondary.append((0.9, _pick_template(SCENARIO_SOFT_TEMPLATES, f"sc_soft_{perfume_name}").format(labels=labels)))

    if gender_matched:
        secondary.append((0.2, _pick_template(GENDER_TEMPLATES, f"gender_{perfume_name}")))

    if secondary:
        secondary.sort(key=lambda c: c[0], reverse=True)
        highlights.append(secondary[0][1])

    return highlights[:2]


OPENING_TEMPLATES_HIGH = [
    "We selected **{brand} — {perfume}** because its {vibe} profile closely matches what you're after.",
    "**{brand} — {perfume}** stands out as a {vibe} option that lines up with your criteria.",
    "For a {vibe} signature, **{brand} — {perfume}** is an exceptional match.",
]
OPENING_TEMPLATES_MID = [
    "**{brand} — {perfume}** brings a {vibe} character that matches several of your criteria.",
    "We recommend **{brand} — {perfume}** for its {vibe} profile, matching much of what you described.",
]
OPENING_TEMPLATES_LOW = [
    "**{brand} — {perfume}** shares some {vibe} qualities with what you're looking for.",
    "**{brand} — {perfume}** is a partial match, leaning toward a {vibe} character.",
]

CONFIDENCE_HIGH = ["This is a top-tier recommendation.", "A standout pick from the shortlist.", "Hard to go wrong with this one."]
CONFIDENCE_MID = ["A highly recommended option.", "Well worth a closer look.", "A strong contender for your shortlist."]
CONFIDENCE_LOW = ["A solid choice worth considering.", "Worth a sample before committing.", "A reasonable option to explore."]

DEFAULT_VIBE = "carefully tailored"


def _vibe_phrase(scenarios: list[str] | None) -> str:
    """Evocative adjective pair drawn from the actually-detected scenario(s), not a
    crude keyword guess - reuses the same scenario detection already driving the score."""
    vibes = [SCENARIO_MAP[s]["vibe"] for s in (scenarios or []) if s in SCENARIO_MAP and "vibe" in SCENARIO_MAP[s]]
    if not vibes:
        return DEFAULT_VIBE
    return vibes[0]


def generate_explanation(
    perfume_name: str,
    brand: str,
    match_score: float,
    perfume_notes: list[str],
    perfume_accords: list[str],
    query: str = "",
    scenarios: list[str] | None = None,
    skin_type: str | None = None,
    budget: float | None = None,
    price_inr: float | None = None,
    gender_matched: bool = False,
    longevity_requested: bool = False,
    hours_required: int | None = None,
    longevity_score: float | None = None,
    longevity_fit: float = 1.0,
    projection_preference: str | None = None,
    projection_fit: float = 1.0,
    sillage_score: float | None = None,
    scenario_fit: float = 1.0,
    identity_label: str | None = None,
) -> str:
    """Deterministic explanation that reads like an LLM wrote it. No API calls, ~0.001s.

    Every template choice is made via `_pick_template`, which uses a stable hash
    of the perfume's own identity - so the same perfume always gets the same
    phrasing choices, and different perfumes naturally get different selections."""
    query_terms = query.lower().split()
    matched_notes = _match_notes(query_terms, perfume_notes)
    matched_accords = _match_accords(query_terms, perfume_accords)
    scenario_labels = [SCENARIO_MAP[s]["label"] for s in (scenarios or []) if s in SCENARIO_MAP]
    vibe = _vibe_phrase(scenarios)

    seed = f"{brand}|{perfume_name}"
    if match_score >= 80:
        opening = _pick_template(OPENING_TEMPLATES_HIGH, f"open_high_{seed}")
        confidence = _pick_template(CONFIDENCE_HIGH, f"conf_high_{seed}")
    elif match_score >= 65:
        opening = _pick_template(OPENING_TEMPLATES_MID, f"open_mid_{seed}")
        confidence = _pick_template(CONFIDENCE_MID, f"conf_mid_{seed}")
    else:
        opening = _pick_template(OPENING_TEMPLATES_LOW, f"open_low_{seed}")
        confidence = _pick_template(CONFIDENCE_LOW, f"conf_low_{seed}")

    highlights = _build_highlights(
        perfume_name, perfume_accords,
        scenario_labels, scenario_fit, matched_notes, matched_accords,
        longevity_requested, hours_required, longevity_fit, longevity_score,
        projection_preference, projection_fit, sillage_score, gender_matched,
        identity_label,
    )
    highlight_text = " ".join(highlights)

    skin_phrase = f" {SKIN_TYPE_PHRASES[skin_type]}" if skin_type in SKIN_TYPE_PHRASES and SKIN_TYPE_PHRASES[skin_type] else ""
    price_phrase = _price_phrase(price_inr, budget, perfume_name)

    opening_text = opening.format(brand=brand, perfume=perfume_name, vibe=vibe)

    return (
        f"{opening_text} {highlight_text}{skin_phrase}{price_phrase} {confidence}"
    ).replace("  ", " ").strip()


def _breakdown_status(fit: float, met: float = 0.85, partial: float = 0.5) -> str:
    if fit >= met:
        return "met"
    if fit >= partial:
        return "partial"
    return "unmet"


def _build_breakdown(
    scenario_labels: list[str], scenario_fit: float, note_match: float,
    longevity_requested: bool, hours_required: int | None, longevity_fit: float,
    projection_preference: str | None, projection_fit: float,
    gender: str | None, gender_matched: bool, gender_fit: float,
    price_inr: float | None, budget: float | None,
    identity_label: str | None = None,
    has_reference: bool = False,
    negated_hit: str | None = None,
    note_families: list[str] | None = None,
    note_family_fit: float = 1.0,
    has_bridge: bool = False,
    bridge_fit: float = 1.0,
    age: int | None = None,
    age_fit: float = 1.0,
) -> list[dict]:
    """Only lists criteria the user actually signalled - matches the 'why it
    scored highly' checklist, not every possible scoring dimension."""
    items = []
    if negated_hit:
        items.append({"label": f"Contains excluded note: {negated_hit}", "status": "unmet"})
    if identity_label:
        items.append({"label": f"Exact match: {identity_label}", "status": "met"})
    if scenario_labels:
        items.append({"label": f"Occasion: {', '.join(scenario_labels)}", "status": _breakdown_status(scenario_fit)})
    if has_reference:
        items.append({"label": f"Composition overlap: {round(note_match * 100)}%", "status": _breakdown_status(note_match, 0.5, 0.2)})
    elif note_match > 0.15:
        items.append({"label": "Scent profile match", "status": _breakdown_status(note_match, 0.6, 0.25)})
    if note_families:
        family_labels = [NOTE_FAMILY_LABELS.get(f, f.replace("_", " ").title()) for f in note_families]
        items.append({"label": f"Scent preference: {', '.join(family_labels)}", "status": _breakdown_status(note_family_fit, 0.75, 0.4)})
    if has_bridge:
        items.append({"label": "Fresh opening, long-lasting base", "status": _breakdown_status(bridge_fit, 0.9, 0.4)})
    if hours_required:
        items.append({"label": f"{hours_required}+ hour longevity", "status": _breakdown_status(longevity_fit)})
    elif longevity_requested:
        items.append({"label": "Long-lasting", "status": _breakdown_status(longevity_fit)})
    if projection_preference:
        items.append({"label": f"{projection_preference.title()} projection", "status": _breakdown_status(projection_fit)})
    if gender:
        items.append({"label": f"Gender: {gender}", "status": "met" if gender_matched else _breakdown_status(gender_fit, 0.9, 0.5)})
    if age is not None:
        # age_fit is floored at 0.6 (see _age_fit - a population-level nudge,
        # never a hard rule), so "met"/"partial" thresholds sit above that
        # floor rather than reusing the default (0.85/0.5) scale.
        items.append({"label": f"Age-appropriate profile ({age})", "status": _breakdown_status(age_fit, 0.9, 0.65)})
    if budget:
        items.append({"label": f"Within ₹{budget:,.0f} budget", "status": "met" if (price_inr and price_inr <= budget) else "unmet"})
    return items


# ---------------------------------------------------------------------------
# 3. Pipeline orchestration (keeps routing layer clean)
# ---------------------------------------------------------------------------

def rank_and_explain(
    results: list[dict],
    query: str = "",
    budget: float | None = None,
    scenarios: list[str] | None = None,
    skin_type: str | None = None,
    gender: str | None = None,
    age: int | None = None,
    longevity_requested: bool = False,
    hours_required: int | None = None,
    projection_preference: str | None = None,
    limit: int | None = None,
    reference_accords: list[str] | None = None,
    reference_notes: list[str] | None = None,
    deal_breaker: bool = False,
    negated_terms: list[str] | None = None,
    note_families: list[str] | None = None,
) -> list[dict]:
    """
    Takes raw DB results (already a widened ANN candidate pool), applies hybrid
    scoring + reranking, generates explanations, and truncates to `limit`.

    `reference_accords`/`reference_notes` are the REAL composition of a named
    target perfume (the 'find a cheaper alternative to X' case) - when present,
    the scent-profile score is a real calculated overlap against that specific
    perfume rather than fuzzy text-vs-query matching.

    When a `budget` is given, the FINAL display order is driven by price rather
    than by `match_score` alone: by default, the perfume priced nearest the
    budget ceiling is shown first (they told us their limit; a recommendation
    that uses more of it is usually the better pick, not a compromise).
    `deal_breaker=True` flips this to cheapest-first - price becomes the user's
    overriding concern instead of one signal among several. `match_score` is
    still used as the pool has already been filtered to relevant candidates
    (ANN similarity + the SQL price/exclude filters), and breaks ties between
    same/similar-priced results. With no budget, there's no price ceiling to
    be "near" or "under", so it falls back to pure match_score ranking.

    Two-phase deliberately: `results` here is the full ANN candidate pool,
    which db_repository._candidate_pool_size now widens to as much as 1,000
    rows (up from an earlier 50-200 cap) so the correctly low-weighted vector-
    similarity signal has a real field to be out-competed on. Phase 1 below
    scores every one of those rows - cheap, numeric-only work. Phase 2 (the
    natural-language `_build_breakdown`/`generate_explanation` calls - regex
    note/accord matching, template selection, string building) only runs on
    the post-sort, post-truncation slice that's actually returned to a
    client. Running phase 2 on the full pool would have multiplied its cost
    5-20x for candidates guaranteed to be discarded before this function even
    returns.
    """
    query_terms = query.lower().split()
    scenario_labels = [SCENARIO_MAP[s]["label"] for s in (scenarios or []) if s in SCENARIO_MAP]
    has_reference = bool(reference_accords or reference_notes)
    has_budget = budget is not None and budget > 0
    has_gender = bool(gender)
    has_longevity = bool(longevity_requested or hours_required)
    has_scenario = bool(scenarios)
    has_projection = bool(projection_preference)
    has_age = age is not None
    has_note_family = bool(note_families and any(f in NOTE_FAMILIES for f in note_families))
    wants_fresh = bool(set(scenarios or []) & FRESH_SCENARIOS) or bool(set(note_families or []) & FRESH_NOTE_FAMILIES)
    wants_strong_longevity = hours_required is not None and hours_required >= 6
    has_bridge = wants_fresh and wants_strong_longevity

    for r in results:
        raw_sim = r.get("similarity")
        if raw_sim is not None:
            cos_sim = float(raw_sim)
        elif r.get("match_score") is not None:
            cos_sim = r["match_score"] / 100.0
        else:
            cos_sim = 0.0

        price = r.get("price_inr")
        perfume_notes = r.get("notes", [])
        perfume_accords = r.get("main_accords", [])

        if has_reference:
            note_match = _reference_fit(perfume_accords, perfume_notes, reference_accords, reference_notes)
            matched_notes = [n for n in perfume_notes if n.lower() in {x.lower() for x in (reference_notes or [])}]
            matched_accords = [a for a in perfume_accords if a.lower() in {x.lower() for x in (reference_accords or [])}]
        else:
            matched_notes = _match_notes(query_terms, perfume_notes)
            matched_accords = _match_accords(query_terms, perfume_accords)
            note_match = min(1.0, (len(matched_notes) + len(matched_accords)) / 5.0)

        perfume_gender = r.get("gender")
        gender_fit = _gender_fit(perfume_gender, gender)
        if gender_fit == 1.0:
            gender_fit = _gender_leaning_modifier(perfume_gender, gender, perfume_notes, perfume_accords)
        gender_matched = (perfume_gender == gender or perfume_gender == "unisex") and gender_fit >= 0.9

        perfume_type = r.get("type")
        longevity_score = r.get("longevity_score")
        sillage_score = r.get("sillage_score")
        longevity_score, sillage_score = _adjust_performance_by_type(longevity_score, sillage_score, perfume_type)

        longevity_fit = _longevity_fit(longevity_score, longevity_requested, hours_required)
        projection_fit = _projection_fit(sillage_score, projection_preference)

        scenario_fit = _scenario_fit(perfume_accords, perfume_notes, scenarios or [])
        age_fit = _age_fit(perfume_accords, age)
        price_fit = _price_fit(price, budget, deal_breaker)
        note_family_fit = _note_family_fit(perfume_notes, perfume_accords, note_families)
        bridge_fit = _bridge_fit(
            r.get("top_notes", []), r.get("base_notes", []), perfume_accords, wants_fresh, wants_strong_longevity,
        )

        base_score = hybrid_score(
            cos_sim, price_fit=price_fit, note_match=note_match,
            gender_fit=gender_fit, longevity_fit=longevity_fit,
            scenario_fit=scenario_fit, projection_fit=projection_fit, age_fit=age_fit,
            note_family_fit=note_family_fit, bridge_fit=bridge_fit,
            has_budget=has_budget, has_gender=has_gender, has_longevity=has_longevity,
            has_scenario=has_scenario, has_projection=has_projection, has_age=has_age,
            has_note_family=has_note_family, has_bridge=has_bridge,
        )
        identity_bonus, identity_label = _identity_boost(query, r.get("brand", ""), r.get("perfume", ""))
        negation_fit, negated_hit = _negation_penalty(perfume_accords, perfume_notes, negated_terms)
        # Keep the uncapped score for sorting - two results that both exceed
        # 100 and get capped to the same displayed value would otherwise tie
        # and fall back to incidental input order, silently discarding a real
        # difference (e.g. a more specific flanker match vs. a partial one).
        r["_raw_score"] = (base_score + identity_bonus) * negation_fit
        r["match_score"] = min(100.0, round((base_score + identity_bonus) * negation_fit, 1))
        r["savings"] = round(budget - price, 2) if budget and price and price < budget else None
        r["estimated_wear_hours"] = estimate_wear_hours(longevity_score)
        r["projection_label"] = sillage_label(sillage_score)
        r["best_for"] = scenario_labels
        # Stashed for phase 2 below - everything a candidate's breakdown/
        # explanation needs that isn't already sitting on `r` itself or in
        # this function's own outer-scope variables (query/scenarios/budget/
        # etc, which phase 2 can read directly since it's the same call).
        r["_explain_ctx"] = {
            "scenario_fit": scenario_fit, "note_match": note_match,
            "longevity_fit": longevity_fit, "projection_fit": projection_fit,
            "gender_matched": gender_matched, "gender_fit": gender_fit,
            "identity_label": identity_label, "negated_hit": negated_hit,
            "note_family_fit": note_family_fit, "bridge_fit": bridge_fit,
            "longevity_score": longevity_score, "sillage_score": sillage_score,
            "age_fit": age_fit,
        }

    apply_price_order(results, budget, deal_breaker, score_key="_raw_score")
    for r in results:
        r.pop("_raw_score", None)
    truncated = results[:limit] if limit else results

    # Phase 2: natural-language explanation/breakdown, only for the slice
    # that's actually returned - see this function's docstring.
    for r in truncated:
        ctx = r.pop("_explain_ctx")
        r["match_breakdown"] = _build_breakdown(
            scenario_labels, ctx["scenario_fit"], ctx["note_match"],
            longevity_requested, hours_required, ctx["longevity_fit"],
            projection_preference, ctx["projection_fit"],
            gender, ctx["gender_matched"], ctx["gender_fit"],
            r.get("price_inr"), budget, ctx["identity_label"], has_reference, ctx["negated_hit"],
            note_families, ctx["note_family_fit"], has_bridge, ctx["bridge_fit"],
            age, ctx["age_fit"],
        )
        r["explanation"] = generate_explanation(
            perfume_name=r.get("perfume", ""),
            brand=r.get("brand", ""),
            match_score=r["match_score"],
            perfume_notes=r.get("notes", []),
            perfume_accords=r.get("main_accords", []),
            query=query,
            scenarios=scenarios,
            skin_type=skin_type,
            budget=budget,
            price_inr=r.get("price_inr"),
            gender_matched=ctx["gender_matched"],
            longevity_requested=longevity_requested,
            hours_required=hours_required,
            longevity_score=ctx["longevity_score"],
            longevity_fit=ctx["longevity_fit"],
            projection_preference=projection_preference,
            projection_fit=ctx["projection_fit"],
            sillage_score=ctx["sillage_score"],
            scenario_fit=ctx["scenario_fit"],
            identity_label=ctx["identity_label"],
        )

    return truncated


def apply_price_order(
    results: list[dict], budget: float | None, deal_breaker: bool = False, score_key: str = "match_score",
) -> list[dict]:
    """Sorts `results` in place by the same budget-aware rule `rank_and_explain`
    uses, and also returns it (for chaining). Exposed separately so callers can
    re-apply it AFTER the optional LLM re-ranking layer, which re-orders by its
    own relevance judgment and would otherwise silently discard the
    nearest-to-budget/cheapest-first ordering the user asked for."""
    if budget:
        if deal_breaker:
            # Cheapest first. match_score as tiebreaker for equal/near-equal prices.
            results.sort(key=lambda x: (x.get("price_inr") if x.get("price_inr") is not None else float("inf"), -(x.get(score_key) or 0)))
        else:
            # Nearest the budget ceiling first (all candidates are already <= budget).
            results.sort(key=lambda x: (-(x.get("price_inr") or 0), -(x.get(score_key) or 0)))
    else:
        # No budget given at all - nothing to be "near" or "under", so pure quality ranking.
        results.sort(key=lambda x: x.get(score_key) or 0, reverse=True)
    return results


def cap_per_brand(results: list[dict], limit: int, max_per_brand: int = 2, backfill: bool = True) -> list[dict]:
    """Enforces a maximum number of results per brand while preserving rank
    order.

    Why this exists: for a low-signal query (no scent/budget/gender given -
    just an occasion), deterministic scores cluster very close together
    (e.g. 59.4-59.6%), so a brand with several near-identically-scored SKUs
    can legitimately dominate the top of the ranking on pure score alone.
    The optional LLM re-ranking layer's prompt asks it to prefer variety
    across brands, but that is advisory, not enforced - verified empirically
    across many live runs of the same query, which kept returning 3-4-of-6
    results from a single brand despite the instruction.

    `backfill=True` (the default - use for the *final* result set, at the
    real user-facing `limit` like 6): if the strict cap leaves fewer than
    `limit` results, relax the cap by one and re-scan, repeating only as many
    times as actually needed, spreading any forced extra fairly across every
    over-represented brand rather than dumping it all on whichever one
    happens to have the most leftovers.

    `backfill=False` (use for the *wide pre-LLM candidate pool*, e.g. 25):
    just the strict cap, nothing more. Backfilling this stage doesn't make
    sense - relaxing to fill a large `fetch_limit` (25) when only a handful
    of distinct brands score well for this query would relax the cap far
    more than the real, final `limit` (6) ever needs, handing the LLM a pool
    that's already skewed again. The actual bug this shipped with: capping
    the wide pool *with* backfill against `fetch_limit` let one brand climb
    back up to 3-4 entries in the 25-candidate pool, which the LLM (or a
    disabled-LLM truncation) could then return in full - caught by live
    testing (3-4 "All Good Scents" in several of 15 runs) even after the
    first backfill-fairness fix, and only surfaced because a real HTTP call
    was made repeatedly, not just because the unit tests passed.

    Applied twice per request regardless of which path produced the final
    results: once (strict) on the wide pool before the optional LLM ever
    sees it, and once more (with backfill) on whatever comes back - from the
    LLM or the deterministic path alike - so the guarantee holds unconditionally,
    not only when Groq happens to be configured and cooperative.

    `max_cap` must never be lower than the starting `cap` (`max_per_brand`) -
    real bug this shipped with: when `backfill=True` and `limit` is smaller
    than `max_per_brand` (e.g. `limit=1`, the default `max_per_brand=2` - a
    real, reachable case: `req.limit=1` is a valid value under both search
    schemas' `ge=1` bound, and the LLM-enabled path computes exactly this via
    `llm_pick_count = min(req.limit, llm_pool_cap)`), `max_cap` was set to
    `limit` itself (1), which is BELOW the starting `cap` (2) - so the while
    loop's own entry condition (`cap <= max_cap`) failed before a single
    iteration ran, silently returning an empty list regardless of how many
    valid results were passed in. Confirmed live: `POST /search/dupe` with
    `limit: 1` returned `[]` over HTTP while `limit: 2` through `limit: 5`
    all returned real results - not caught by any existing unit test, all of
    which used `limit >= max_per_brand`. `max(limit, max_per_brand)` keeps
    every existing case identical (limit is normally >= max_per_brand) while
    guaranteeing the first, strictest pass always gets to run at least once.

    The key is lowercased - confirmed live against the real catalog:
    "Le Labo" and "le labo" both exist as literal, distinct brand strings on
    real rows (a genuine data-casing inconsistency, not a typo isolated to
    one row), which a case-sensitive key previously counted as two different
    brands entirely - defeating the cap for exactly the brand it was most
    likely to matter for (a query where the same real house shows up under
    both castings)."""
    return _cap_by_key(results, limit, key_fn=lambda r: r.get("brand", "").lower(), max_per_key=max_per_brand, backfill=backfill)


def _cap_by_key(
    results: list[dict], limit: int, key_fn: Callable[[dict], str], max_per_key: int, backfill: bool,
) -> list[dict]:
    """The actual backfill-aware capping algorithm, extracted so cap_per_brand
    and cap_by_scent_character (below) share one implementation instead of
    two copies of a subtle loop that has already shipped two real bugs (see
    cap_per_brand's own docstring) - a second, independently-maintained copy
    would double the surface either one could silently drift out of sync on.
    `key_fn` extracts whatever should be capped from a result dict; see
    cap_per_brand's docstring for what every parameter means and why.

    `key_counts` is maintained incrementally (initialized once, incremented
    exactly once per append) rather than rebuilt from scratch by rescanning
    all of `output` at the top of every cap-relaxation iteration - `output`
    only ever grows, so a from-scratch rebuild was always redundant with
    what the running counts already reflected. This turns the per-iteration
    cost from O(len(output) + len(results)) into O(len(results))."""
    output: list[dict] = []
    added = [False] * len(results)
    key_counts: dict[str, int] = {}
    cap = max_per_key
    max_cap = max(limit, max_per_key) if backfill else max_per_key
    while len(output) < limit and cap <= max_cap:
        progressed = False
        for i, r in enumerate(results):
            if added[i] or len(output) >= limit:
                continue
            key = key_fn(r)
            if key_counts.get(key, 0) < cap:
                output.append(r)
                added[i] = True
                key_counts[key] = key_counts.get(key, 0) + 1
                progressed = True
        if not backfill:
            break
        if not progressed:
            cap += 1
    return output[:limit]


def _dominant_accord(r: dict) -> str:
    """Best-effort scent-character cluster key: a perfume's first-listed
    main_accord, lowercased. Fragrantica-style accord lists are ordered by
    relative prominence, so main_accords[0] is the closest single-value
    proxy for "what this perfume smells most like" already present on every
    row - not a curated classification, and not always a guarantee of true
    ordering across every ingestion source, just the cheapest real signal
    available without introducing a second taxonomy to maintain."""
    accords = r.get("main_accords") or []
    return accords[0].lower() if accords else ""


def cap_by_scent_character(results: list[dict], limit: int, max_per_accord: int = 3, backfill: bool = True) -> list[dict]:
    """Same backfill-aware capping as cap_per_brand, clustered by dominant
    scent accord instead of brand. cap_per_brand alone still lets N
    near-identical "citrus aromatic" results from N *different* brands read
    as one undifferentiated cluster to a user who wanted variety in scent
    character, not just label diversity - brand-capping has no way to catch
    that, since it only ever looks at the brand field. A looser cap than
    brand's default (3 vs 2): this constraint is coarser and less exact than
    "the same brand twice" - over-restricting it risks discarding genuinely
    strong matches just for accord variety, which isn't the goal; the goal
    is avoiding total homogeneity, not banning any accord repetition."""
    return _cap_by_key(results, limit, key_fn=_dominant_accord, max_per_key=max_per_accord, backfill=backfill)
