"""
AuraMatch AI - Decision Engine
Hybrid scoring + deterministic explanation generator.
Modular: swap `scorer` and `explainer` with an LLM later (just implement the same interface).
"""
from typing import Optional


# ---------------------------------------------------------------------------
# 1. Hybrid Scorer
# ---------------------------------------------------------------------------

SIM_WEIGHT = 0.50
NOTE_MATCH_WEIGHT = 0.20
PRICE_WEIGHT = 0.15
GENDER_WEIGHT = 0.07
LONGEVITY_WEIGHT = 0.08


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


def _longevity_fit(perfume_longevity_score: Optional[float], longevity_requested: bool) -> float:
    """1.0 (no-op) unless the user explicitly asked for a long-lasting scent -
    then reward perfumes with a higher heuristic longevity_score (0-100)."""
    if not longevity_requested:
        return 1.0
    if perfume_longevity_score is None:
        return 0.5
    return max(0.0, min(1.0, perfume_longevity_score / 100.0))


def hybrid_score(
    cosine_similarity: float,
    price_inr: Optional[float],
    budget: Optional[float] = None,
    note_match: float = 0.0,
    gender_fit: float = 1.0,
    longevity_fit: float = 1.0,
) -> float:
    """
    Final Score = similarity*0.50 + note_match*0.20 + price_fit*0.15 + gender_fit*0.07 + longevity_fit*0.08

    - similarity: pgvector cosine similarity of the embedded query vs. the perfume.
    - note_match: fraction of query terms found verbatim in this perfume's notes/accords.
    - price_fit: 1.0 at/below half the budget, linear decay to 0 at budget, 1.0 if no budget.
    - gender_fit / longevity_fit: neutral 1.0 unless the user explicitly signalled that
      preference, so queries that don't care about gender/longevity are never penalized.
    """
    price_score = _price_fit(price_inr, budget)
    total = (
        cosine_similarity * SIM_WEIGHT
        + note_match * NOTE_MATCH_WEIGHT
        + price_score * PRICE_WEIGHT
        + gender_fit * GENDER_WEIGHT
        + longevity_fit * LONGEVITY_WEIGHT
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


SCENARIO_INTROS = {
    "gym": "high-energy workouts",
    "summer": "hot summer days",
    "winter": "cold winter weather",
    "monsoon": "humid rainy weather",
    "office": "a professional office setting",
    "party": "a night out",
    "date": "a romantic date night",
    "wedding": "a celebration",
    "daily": "everyday wear",
    "evening": "the evening",
    "spring": "spring weather",
    "autumn": "crisp autumn days",
}


SKIN_TYPE_PHRASES = {
    "dry": "Its rich base notes perform exceptionally well on dry skin, lasting longer than average.",
    "oily": "Its fresh top notes stay balanced on oily skin without becoming overwhelming.",
    "normal": "",
}


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
    longevity_score: Optional[float] = None,
) -> str:
    """
    Deterministic explanation that reads like an LLM wrote it.
    No API calls. Takes ~0.001s.
    """
    query_terms = query.lower().split()
    matched_notes = _match_notes(query_terms, perfume_notes)
    matched_accords = _match_accords(query_terms, perfume_accords)
    scenario_intro = skin_phrase = price_phrase = longevity_phrase = gender_phrase = ""

    # 1. Opening — match quality
    if match_score >= 90:
        set_phrase = "perfectly aligns with your preferences"
    elif match_score >= 75:
        set_phrase = "is a strong match for what you're looking for"
    elif match_score >= 60:
        set_phrase = "matches several of your criteria"
    else:
        set_phrase = "shares some characteristics with your request"

    # 2. Scenario context (can be multiple, blended from free text)
    scenario_labels = [SCENARIO_INTROS[s] for s in (scenarios or []) if s in SCENARIO_INTROS]
    if scenario_labels:
        scenario_intro = f" — an excellent choice for {' and '.join(scenario_labels)}"

    # 3. Note/accord evidence
    evidence_parts = []
    if matched_notes:
        note_list = ", ".join(matched_notes[:3])
        evidence_parts.append(f"its prominent {note_list} notes")
    if matched_accords:
        accord_list = ", ".join(matched_accords[:3])
        evidence_parts.append(f"its {accord_list} character")

    evidence = ""
    if evidence_parts:
        evidence = f" We identified this because of {' and '.join(evidence_parts)}."

    # 4. Skin type
    if skin_type and skin_type in SKIN_TYPE_PHRASES:
        skin_phrase = f" {SKIN_TYPE_PHRASES[skin_type]}"

    # 5. Gender
    if gender_matched:
        gender_phrase = " It's tailored to the gender you specified."

    # 6. Longevity — only mentioned when actually requested, and honest about the data behind it
    if longevity_requested and longevity_score is not None:
        if longevity_score >= 70:
            longevity_phrase = f" Its note composition scores high for longevity ({round(longevity_score)}/100), so it should last through a long day."
        else:
            longevity_phrase = f" Its longevity score ({round(longevity_score)}/100) is moderate — reapplication may help it go the distance."

    # 7. Budget / value
    if budget is not None and price_inr is not None and budget > 0:
        savings = budget - price_inr
        if savings > 0:
            price_phrase = f" At ₹{price_inr:,}, it saves you ₹{savings:,} compared to your ₹{budget:,} budget."
        else:
            price_phrase = f" At ₹{price_inr:,}, it fits within your ₹{budget:,} budget."
    elif price_inr:
        price_phrase = f" Priced at ₹{price_inr:,}."

    # 8. Confidence building
    if match_score >= 90:
        confidence = "This is a top-tier recommendation."
    elif match_score >= 75:
        confidence = "A highly recommended option."
    elif match_score >= 60:
        confidence = "A solid choice worth considering."
    else:
        confidence = "A potential option to explore."

    return (
        f"We recommend **{brand} — {perfume_name}** because it {set_phrase}"
        f"{scenario_intro}.{evidence}{gender_phrase}{longevity_phrase}{skin_phrase}{price_phrase} {confidence}"
    )


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
    longevity_requested: bool = False,
    limit: Optional[int] = None,
) -> list[dict]:
    """
    Takes raw DB results (already a widened ANN candidate pool), applies hybrid
    scoring + reranking, generates explanations, and truncates to `limit`.
    """
    query_terms = query.lower().split()

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

        matched_notes = _match_notes(query_terms, perfume_notes)
        matched_accords = _match_accords(query_terms, perfume_accords)
        note_match = min(1.0, (len(matched_notes) + len(matched_accords)) / 5.0)

        perfume_gender = r.get("gender")
        gender_matched = bool(gender and perfume_gender and perfume_gender == gender)
        gender_fit = _gender_fit(perfume_gender, gender)

        longevity_score = r.get("longevity_score")
        longevity_fit = _longevity_fit(longevity_score, longevity_requested)

        r["match_score"] = hybrid_score(
            cos_sim, price, budget, note_match=note_match,
            gender_fit=gender_fit, longevity_fit=longevity_fit,
        )
        r["savings"] = round(budget - price, 2) if budget and price else None
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
            longevity_score=longevity_score,
        )

    results.sort(key=lambda x: x["match_score"], reverse=True)
    return results[:limit] if limit else results
