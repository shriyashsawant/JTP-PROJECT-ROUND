"""
AuraMatch AI - Decision Engine
Hybrid scoring + deterministic explanation generator.
Modular: swap `scorer` and `explainer` with an LLM later (just implement the same interface).
"""
import random
import re
from typing import Optional
from app.services.scenario_map import (
    SCENARIO_MAP, AGE_BRACKET_ACCORDS, age_to_bracket,
    estimate_wear_hours, estimate_hours_numeric, sillage_label,
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
PRICE_WEIGHT = 0.05
GENDER_WEIGHT = 0.05
AGE_WEIGHT = 0.05


def _price_fit(price_inr: Optional[float], budget: Optional[float]) -> float:
    """1.0 when price <= budget/2, linear decay to 0 at budget. 1.0 (no-op) if no budget set."""
    if budget is None or budget <= 0 or price_inr is None:
        return 1.0
    if price_inr <= budget / 2:
        return 1.0
    if price_inr >= budget:
        return 0.0
    return 1.0 - (price_inr - budget / 2) / (budget / 2)


def _gender_fit(perfume_gender: Optional[str], requested_gender: Optional[str]) -> float:
    """1.0 (no-op) unless the user asked for a gender AND the perfume is explicitly
    tagged as the other gender - then a soft penalty (never zero, never excludes)."""
    if not requested_gender:
        return 1.0
    if not perfume_gender or perfume_gender == "unisex":
        return 1.0
    if perfume_gender == requested_gender:
        return 1.0
    return 0.4


def _scenario_fit(perfume_accords: list[str], matched_scenarios: list[str]) -> float:
    """1.0 (no-op) if no occasion/season was signalled. Otherwise, the fraction of
    this perfume's accords that overlap with the union of matched scenarios'
    accord vocab (2+ overlapping accords = full credit)."""
    if not matched_scenarios:
        return 1.0
    target = set()
    for s in matched_scenarios:
        if s in SCENARIO_MAP:
            target.update(a.lower() for a in SCENARIO_MAP[s]["accords"])
    if not target:
        return 1.0
    perfume_set = {a.lower() for a in (perfume_accords or [])}
    overlap = perfume_set & target
    return min(1.0, len(overlap) / 2.0)


def _longevity_fit(
    longevity_score: Optional[float], longevity_requested: bool, hours_required: Optional[int],
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


def _projection_fit(sillage_score: Optional[float], projection_preference: Optional[str]) -> float:
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


def _identity_boost(raw_query: str, brand: str, perfume_name: str) -> tuple[float, Optional[str]]:
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


def _reference_fit(
    candidate_accords: list[str], candidate_notes: list[str],
    reference_accords: list[str], reference_notes: list[str],
) -> float:
    """Real, quantitative composition similarity to a named reference perfume
    (the 'dupe engine' case) - accords weighted higher than notes since they
    summarize the perfume's overall character, notes are granular ingredients.
    This replaces guessing via raw-text embedding similarity with an actual
    calculated overlap between the two perfumes' real compositions."""
    accord_sim = _jaccard(candidate_accords, reference_accords)
    note_sim = _jaccard(candidate_notes, reference_notes)
    return accord_sim * 0.65 + note_sim * 0.35


def _age_fit(perfume_accords: list[str], age: Optional[int]) -> float:
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
    price_inr: Optional[float],
    budget: Optional[float] = None,
    note_match: float = 0.0,
    gender_fit: float = 1.0,
    longevity_fit: float = 1.0,
    scenario_fit: float = 1.0,
    projection_fit: float = 1.0,
    age_fit: float = 1.0,
) -> float:
    """
    Final Score = sim*0.07 + note_match*0.20 + scenario_fit*0.28 + longevity_fit*0.20
                + projection_fit*0.10 + price_fit*0.05 + gender_fit*0.05 + age_fit*0.05

    Every *_fit term defaults to a neutral 1.0 when the user didn't signal that
    preference, so a query with no occasion/longevity/projection/gender/age intent
    is scored almost entirely on scent-profile match (note_match + similarity).
    """
    price_score = _price_fit(price_inr, budget)
    total = (
        cosine_similarity * SIM_WEIGHT
        + note_match * NOTE_MATCH_WEIGHT
        + scenario_fit * SCENARIO_WEIGHT
        + longevity_fit * LONGEVITY_WEIGHT
        + projection_fit * PROJECTION_WEIGHT
        + price_score * PRICE_WEIGHT
        + gender_fit * GENDER_WEIGHT
        + age_fit * AGE_WEIGHT
    )
    return round(total * 100, 1)


# ---------------------------------------------------------------------------
# 2. Deterministic Explanation Generator
# ---------------------------------------------------------------------------

def _match_notes(query_terms: list[str], perfume_notes: list[str]) -> list[str]:
    """Find which perfume notes semantically match the query terms."""
    query_lower = [q.lower() for q in query_terms]
    matched = []
    for note in perfume_notes:
        n_lower = note.lower()
        for qt in query_lower:
            if qt in n_lower or n_lower in qt:
                matched.append(note)
                break
    return matched


def _match_accords(query_terms: list[str], perfume_accords: list[str]) -> list[str]:
    """Find which accords match the query terms."""
    query_lower = [q.lower() for q in query_terms]
    matched = []
    for accord in perfume_accords:
        a_lower = accord.lower()
        for qt in query_lower:
            if qt in a_lower or a_lower in qt:
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


def _price_phrase(price_inr: Optional[float], budget: Optional[float], rng: random.Random) -> str:
    """Budget is a threshold, not something to optimize - only call out exact
    savings when the price is a meaningful fraction of the budget; otherwise
    just confirm it's comfortably affordable."""
    if not price_inr:
        return ""
    if not budget or budget <= 0:
        return f" Priced at {_inr(price_inr)}."
    ratio = price_inr / budget
    if ratio <= 0.7:
        return rng.choice([
            f" Comfortably within your {_inr(budget)} budget.",
            f" Well inside your {_inr(budget)} budget, with room to spare.",
        ])
    if price_inr < budget:
        return rng.choice([
            f" Priced at {_inr(price_inr)}, it provides luxury-tier quality while keeping {_inr(budget - price_inr)} under your budget.",
            f" At {_inr(price_inr)}, it saves you {_inr(budget - price_inr)} against your {_inr(budget)} budget.",
        ])
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
    rng: random.Random,
    perfume_accords: list[str],
    scenario_labels: list[str], scenario_fit: float,
    matched_notes: list[str], matched_accords: list[str],
    longevity_requested: bool, hours_required: Optional[int], longevity_fit: float, longevity_score: Optional[float],
    projection_preference: Optional[str], projection_fit: float, sillage_score: Optional[float],
    gender_matched: bool,
    identity_label: Optional[str] = None,
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
        highlights.append(rng.choice(SIGNATURE_TEMPLATES).format(parts=" and ".join(signature_parts)))

    # Second slot: prefer a genuine shortfall (honesty), else the most specific
    # remaining detail (hour count is more informative than a repeated label).
    secondary: list[tuple[float, str]] = []

    if hours_required:
        hours_label = estimate_wear_hours(longevity_score)
        if longevity_fit >= 0.9:
            secondary.append((0.7, rng.choice(LONGEVITY_MET_TEMPLATES).format(hours=hours_label, required=hours_required)))
        else:
            secondary.append((0.99, rng.choice(LONGEVITY_SHORT_TEMPLATES).format(hours=hours_label, required=hours_required)))
    elif longevity_requested:
        secondary.append((0.6, rng.choice(LONGEVITY_SOFT_TEMPLATES).format(hours=estimate_wear_hours(longevity_score))))

    if projection_preference:
        actual_label = sillage_label(sillage_score)
        if projection_fit >= 0.9:
            secondary.append((0.5, rng.choice(PROJECTION_MET_TEMPLATES).format(label=actual_label)))
        else:
            secondary.append((0.95, rng.choice(PROJECTION_MISS_TEMPLATES).format(label=actual_label, wanted=projection_preference)))

    if scenario_labels:
        labels = ", ".join(scenario_labels)
        if scenario_fit >= 0.9:
            secondary.append((0.4, rng.choice(SCENARIO_MET_TEMPLATES).format(labels=labels)))
        else:
            secondary.append((0.9, rng.choice(SCENARIO_SOFT_TEMPLATES).format(labels=labels)))

    if gender_matched:
        secondary.append((0.2, rng.choice(GENDER_TEMPLATES)))

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


def _vibe_phrase(scenarios: Optional[list[str]]) -> str:
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
    scenarios: Optional[list[str]] = None,
    skin_type: Optional[str] = None,
    budget: Optional[float] = None,
    price_inr: Optional[float] = None,
    gender_matched: bool = False,
    longevity_requested: bool = False,
    hours_required: Optional[int] = None,
    longevity_score: Optional[float] = None,
    longevity_fit: float = 1.0,
    projection_preference: Optional[str] = None,
    projection_fit: float = 1.0,
    sillage_score: Optional[float] = None,
    scenario_fit: float = 1.0,
    identity_label: Optional[str] = None,
) -> str:
    """Deterministic explanation that reads like an LLM wrote it. No API calls, ~0.001s.

    Uses a local random.Random seeded by the perfume's own identity (brand+name) -
    NOT the global `random` module, which would be unsafe to mutate in a concurrent
    FastAPI server. Deterministic per-perfume (same perfume always gets the same
    phrasing choices), but varies across different perfumes in the same result set."""
    rng = random.Random(f"{brand}|{perfume_name}")
    query_terms = query.lower().split()
    matched_notes = _match_notes(query_terms, perfume_notes)
    matched_accords = _match_accords(query_terms, perfume_accords)
    scenario_labels = [SCENARIO_MAP[s]["label"] for s in (scenarios or []) if s in SCENARIO_MAP]
    vibe = _vibe_phrase(scenarios)

    if match_score >= 80:
        opening = rng.choice(OPENING_TEMPLATES_HIGH)
        confidence = rng.choice(CONFIDENCE_HIGH)
    elif match_score >= 65:
        opening = rng.choice(OPENING_TEMPLATES_MID)
        confidence = rng.choice(CONFIDENCE_MID)
    else:
        opening = rng.choice(OPENING_TEMPLATES_LOW)
        confidence = rng.choice(CONFIDENCE_LOW)

    highlights = _build_highlights(
        rng, perfume_accords,
        scenario_labels, scenario_fit, matched_notes, matched_accords,
        longevity_requested, hours_required, longevity_fit, longevity_score,
        projection_preference, projection_fit, sillage_score, gender_matched,
        identity_label,
    )
    highlight_text = " ".join(highlights)

    skin_phrase = f" {SKIN_TYPE_PHRASES[skin_type]}" if skin_type in SKIN_TYPE_PHRASES and SKIN_TYPE_PHRASES[skin_type] else ""
    price_phrase = _price_phrase(price_inr, budget, rng)

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
    longevity_requested: bool, hours_required: Optional[int], longevity_fit: float,
    projection_preference: Optional[str], projection_fit: float,
    gender: Optional[str], gender_matched: bool, gender_fit: float,
    price_inr: Optional[float], budget: Optional[float],
    identity_label: Optional[str] = None,
    has_reference: bool = False,
) -> list[dict]:
    """Only lists criteria the user actually signalled - matches the 'why it
    scored highly' checklist, not every possible scoring dimension."""
    items = []
    if identity_label:
        items.append({"label": f"Exact match: {identity_label}", "status": "met"})
    if scenario_labels:
        items.append({"label": f"Occasion: {', '.join(scenario_labels)}", "status": _breakdown_status(scenario_fit)})
    if has_reference:
        items.append({"label": f"Composition overlap: {round(note_match * 100)}%", "status": _breakdown_status(note_match, 0.5, 0.2)})
    elif note_match > 0.15:
        items.append({"label": "Scent profile match", "status": _breakdown_status(note_match, 0.6, 0.25)})
    if hours_required:
        items.append({"label": f"{hours_required}+ hour longevity", "status": _breakdown_status(longevity_fit)})
    elif longevity_requested:
        items.append({"label": "Long-lasting", "status": _breakdown_status(longevity_fit)})
    if projection_preference:
        items.append({"label": f"{projection_preference.title()} projection", "status": _breakdown_status(projection_fit)})
    if gender:
        items.append({"label": f"Gender: {gender}", "status": "met" if gender_matched else _breakdown_status(gender_fit, 0.9, 0.5)})
    if budget:
        items.append({"label": f"Within ₹{budget:,.0f} budget", "status": "met" if (price_inr and price_inr <= budget) else "unmet"})
    return items


# ---------------------------------------------------------------------------
# 3. Pipeline orchestration (keeps routing layer clean)
# ---------------------------------------------------------------------------

def rank_and_explain(
    results: list[dict],
    query: str = "",
    budget: Optional[float] = None,
    scenarios: Optional[list[str]] = None,
    skin_type: Optional[str] = None,
    gender: Optional[str] = None,
    age: Optional[int] = None,
    longevity_requested: bool = False,
    hours_required: Optional[int] = None,
    projection_preference: Optional[str] = None,
    limit: Optional[int] = None,
    reference_accords: Optional[list[str]] = None,
    reference_notes: Optional[list[str]] = None,
) -> list[dict]:
    """
    Takes raw DB results (already a widened ANN candidate pool), applies hybrid
    scoring + reranking, generates explanations, and truncates to `limit`.

    `reference_accords`/`reference_notes` are the REAL composition of a named
    target perfume (the 'find a cheaper alternative to X' case) - when present,
    the scent-profile score is a real calculated overlap against that specific
    perfume rather than fuzzy text-vs-query matching.
    """
    query_terms = query.lower().split()
    scenario_labels = [SCENARIO_MAP[s]["label"] for s in (scenarios or []) if s in SCENARIO_MAP]
    has_reference = bool(reference_accords or reference_notes)

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
        gender_matched = bool(gender and perfume_gender and perfume_gender == gender)
        gender_fit = _gender_fit(perfume_gender, gender)

        longevity_score = r.get("longevity_score")
        longevity_fit = _longevity_fit(longevity_score, longevity_requested, hours_required)

        sillage_score = r.get("sillage_score")
        projection_fit = _projection_fit(sillage_score, projection_preference)

        scenario_fit = _scenario_fit(perfume_accords, scenarios or [])
        age_fit = _age_fit(perfume_accords, age)

        base_score = hybrid_score(
            cos_sim, price, budget, note_match=note_match,
            gender_fit=gender_fit, longevity_fit=longevity_fit,
            scenario_fit=scenario_fit, projection_fit=projection_fit, age_fit=age_fit,
        )
        identity_bonus, identity_label = _identity_boost(query, r.get("brand", ""), r.get("perfume", ""))
        # Keep the uncapped score for sorting - two results that both exceed
        # 100 and get capped to the same displayed value would otherwise tie
        # and fall back to incidental input order, silently discarding a real
        # difference (e.g. a more specific flanker match vs. a partial one).
        r["_raw_score"] = base_score + identity_bonus
        r["match_score"] = min(100.0, round(base_score + identity_bonus, 1))
        r["savings"] = round(budget - price, 2) if budget and price and price < budget else None
        r["estimated_wear_hours"] = estimate_wear_hours(longevity_score)
        r["projection_label"] = sillage_label(sillage_score)
        r["best_for"] = scenario_labels
        r["match_breakdown"] = _build_breakdown(
            scenario_labels, scenario_fit, note_match,
            longevity_requested, hours_required, longevity_fit,
            projection_preference, projection_fit,
            gender, gender_matched, gender_fit,
            price, budget, identity_label, has_reference,
        )
        r["explanation"] = generate_explanation(
            perfume_name=r.get("perfume", ""),
            brand=r.get("brand", ""),
            match_score=r["match_score"],
            perfume_notes=perfume_notes,
            perfume_accords=perfume_accords,
            query=query,
            scenarios=scenarios,
            skin_type=skin_type,
            budget=budget,
            price_inr=price,
            gender_matched=gender_matched,
            longevity_requested=longevity_requested,
            hours_required=hours_required,
            longevity_score=longevity_score,
            longevity_fit=longevity_fit,
            projection_preference=projection_preference,
            projection_fit=projection_fit,
            sillage_score=sillage_score,
            scenario_fit=scenario_fit,
            identity_label=identity_label,
        )

    results.sort(key=lambda x: x["_raw_score"], reverse=True)
    for r in results:
        r.pop("_raw_score", None)
    return results[:limit] if limit else results
