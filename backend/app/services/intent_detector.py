"""
AuraMatch AI - Intent Detector
Deterministic keyword/regex extraction of scenario, gender and longevity
intent from a free-text query. No LLM calls, no ML model - pure string
matching, consistent with the project's "no external LLM" design.
"""
import re
from app.services.scenario_map import (
    SCENARIO_KEYWORDS, LONGEVITY_PHRASES, MALE_HINTS, FEMALE_HINTS,
    PROJECTION_HINTS, LONGEVITY_HOUR_PATTERN, DUPE_INTENT_PHRASES,
    BUDGET_TEXT_PATTERNS,
)


def detect_scenarios(raw_query: str) -> list[str]:
    """Scan free text for every scenario whose keywords appear. Returns matched
    scenario keys in SCENARIO_KEYWORDS iteration order (empty list if none)."""
    if not raw_query:
        return []
    q = f" {raw_query.lower()} "
    matched = []
    for scenario, keywords in SCENARIO_KEYWORDS.items():
        if any(kw in q for kw in keywords):
            matched.append(scenario)
    return matched


def detect_gender(raw_query: str) -> str | None:
    """Infer gender hint from free text via word-boundary regex. Returns None
    if ambiguous (both or neither hint present) - never guesses."""
    if not raw_query:
        return None
    q = raw_query.lower()
    is_male = any(re.search(p, q) for p in MALE_HINTS)
    is_female = any(re.search(p, q) for p in FEMALE_HINTS)
    if is_male and not is_female:
        return "male"
    if is_female and not is_male:
        return "female"
    return None


def detect_longevity_intent(raw_query: str) -> bool:
    """True if the query explicitly asks for a long-lasting scent (soft phrase, no number)."""
    if not raw_query:
        return False
    q = raw_query.lower()
    return any(phrase in q for phrase in LONGEVITY_PHRASES)


def detect_longevity_hours_required(raw_query: str) -> int | None:
    """Parse an explicit hour requirement ('8+ hours', 'lasts 6-8 hours') into a
    minimum-hours threshold. Returns None if no number is present - a soft
    'long lasting' phrase without a number is handled by detect_longevity_intent."""
    if not raw_query:
        return None
    match = re.search(LONGEVITY_HOUR_PATTERN, raw_query.lower())
    if not match:
        return None
    hours = int(match.group(1))
    return hours if 1 <= hours <= 24 else None


def detect_projection_preference(raw_query: str) -> str | None:
    """Infer a light/moderate/strong projection preference from free text.
    Returns None if nothing matches (never guesses)."""
    if not raw_query:
        return None
    q = raw_query.lower()
    for label, phrases in PROJECTION_HINTS.items():
        if any(p in q for p in phrases):
            return label
    return None


def detect_dupe_intent(raw_query: str) -> bool:
    """True if the query is asking for a cheaper/similar alternative to a named
    perfume (e.g. 'cheaper alternative to Dior Sauvage', 'dupe for Bleu de Chanel',
    'cheap dupe') - whether typed into free-text search or the dedicated dupe
    form. The bare word "dupe" is checked as its own word (not just inside
    fixed phrases like "dupe for") so any adjective in front of it ("cheap
    dupe", "a dupe", "find me a dupe") is still caught."""
    if not raw_query:
        return False
    q = raw_query.lower()
    if re.search(r"\bdupe(s)?\b", q):
        return True
    return any(phrase in q for phrase in DUPE_INTENT_PHRASES)


def detect_budget_from_text(raw_query: str) -> float | None:
    """Parse an explicit price ceiling from free text ('under Rs 500', 'within
    a 1000 budget'). This is explicit user input, distinct from any reference-
    perfume-price auto-default, and must always take priority over it."""
    if not raw_query:
        return None
    q = raw_query.lower()
    for pattern in BUDGET_TEXT_PATTERNS:
        match = re.search(pattern, q)
        if match:
            try:
                return float(match.group(1).replace(",", ""))
            except ValueError:
                continue
    return None
