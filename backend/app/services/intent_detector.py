"""
AuraMatch AI - Intent Detector
Deterministic keyword/regex extraction of scenario, gender and longevity
intent from a free-text query. No LLM calls, no ML model - pure string
matching, consistent with the project's "no external LLM" design.
"""
import re
from app.services.scenario_map import (
    SCENARIO_KEYWORDS, LONGEVITY_PHRASES, MALE_HINTS, FEMALE_HINTS,
    PROJECTION_HINTS, LONGEVITY_HOUR_PATTERN,
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
