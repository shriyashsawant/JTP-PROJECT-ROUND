"""
AuraMatch AI - Intent Detector
Keyword/regex extraction + semantic embedding similarity for scenario, gender and longevity.
"""
import logging
import re

import numpy as np

from app.services.scenario_map import (
    BUDGET_TEXT_PATTERNS,
    DUPE_INTENT_PHRASES,
    FEMALE_HINTS,
    LONGEVITY_HOUR_PATTERN,
    LONGEVITY_PHRASES,
    MALE_HINTS,
    PROJECTION_HINTS,
    SCENARIO_KEYWORDS,
    SCENARIO_MAP,
    UNISEX_HINTS,
)

logger = logging.getLogger(__name__)

SCENARIO_EMBEDDINGS: dict[str, list[float]] = {}

async def _init_scenario_embeddings():
    """Lazily compute scenario embeddings from label + vibe + description."""
    global SCENARIO_EMBEDDINGS
    if SCENARIO_EMBEDDINGS:
        return
    try:
        from app.services.ml_engine import generate_embedding_async
        for key, s in SCENARIO_MAP.items():
            text = f"{s['label']}. {s['vibe']}. {s['description']}"
            SCENARIO_EMBEDDINGS[key] = await generate_embedding_async(text)
    except Exception:
        logger.warning("Failed to lazily compute scenario embeddings", exc_info=True)

async def eager_init_scenario_embeddings():
    """Eagerly compute and cache scenario embeddings at app startup, so the
    first real user query doesn't pay for them on top of cold model load."""
    await _init_scenario_embeddings()

async def detect_scenarios_semantic(raw_query: str, absolute_threshold: float = 0.48, margin: float = 0.07) -> list[str]:
    """Calculate similarity scores using embeddings to detect matching scenarios.
    Uses a relative margin filter to prevent general background similarity from polluting results."""
    if not raw_query:
        return []
    await _init_scenario_embeddings()
    if not SCENARIO_EMBEDDINGS:
        return []
    try:
        from app.services.ml_engine import generate_embedding_async
        q_emb = np.array(await generate_embedding_async(raw_query))
        scores = []
        for key, s_emb in SCENARIO_EMBEDDINGS.items():
            s_emb_arr = np.array(s_emb)
            dot = np.dot(q_emb, s_emb_arr)
            norm_q = np.linalg.norm(q_emb)
            norm_s = np.linalg.norm(s_emb_arr)
            sim = dot / (norm_q * norm_s) if norm_q > 0 and norm_s > 0 else 0.0
            scores.append((key, sim))

        if not scores:
            return []

        max_score = max(s[1] for s in scores)

        matched = []
        for key, sim in scores:
            if sim >= absolute_threshold and sim >= (max_score - margin):
                matched.append((key, sim))

        # Sort by similarity score descending
        matched.sort(key=lambda x: x[1], reverse=True)
        return [m[0] for m in matched]
    except Exception:
        logger.warning("Error in semantic scenario detection", exc_info=True)
        return []

async def detect_scenarios(raw_query: str) -> list[str]:
    """Scan free text for every scenario using both keyword matching
    and semantic similarity matching to optimize accuracy."""
    if not raw_query:
        return []

    # 1. Direct keyword matching (fast, 100% confidence)
    matched = []
    q = f" {raw_query.lower()} "
    for scenario, keywords in SCENARIO_KEYWORDS.items():
        if any(kw in q for kw in keywords):
            matched.append(scenario)

    # 2. Semantic matching (handles descriptive synonyms / vibes)
    semantic_matches = await detect_scenarios_semantic(raw_query, absolute_threshold=0.48, margin=0.07)
    for m in semantic_matches:
        if m not in matched:
            matched.append(m)

    return matched


def detect_gender(raw_query: str) -> str | None:
    """Infer gender hint from free text via word-boundary regex. Checks
    explicit unisex/gender-neutral phrasing first - since MALE_HINTS/
    FEMALE_HINTS are single-word regexes, "men and women" would otherwise
    match both lists and fall through to the ambiguous None case below,
    silently dropping a query that actually stated a clear preference.
    Returns None if genuinely ambiguous (both or neither hint present) -
    never guesses."""
    if not raw_query:
        return None
    q = raw_query.lower()
    if any(p in q for p in UNISEX_HINTS):
        return "unisex"
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
    Also handles commute/travel/bike wind exposure fades by boosting to strong projection."""
    if not raw_query:
        return None
    q = raw_query.lower()
    # Wind/outdoor commute exposure causes scent to fade, requiring strong sillage.
    if any(k in q for k in ["bike", "motorcycle", "riding", "scooter", "wind", "fade"]):
        return "strong"
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


_NEGATION_TRIGGER_PATTERN = re.compile(r"\b(?:no|not|without|avoid|hate|dislike)\b\s+")
_NEGATION_CLAUSE_BOUNDARY = re.compile(r"[,.;!?]")
_NEGATION_STOP_WORDS = {
    "and", "or", "but", "with", "notes", "note", "accord", "accords",
    "scent", "scents", "perfume", "perfumes", "too", "very", "much", "a", "an", "the",
    "i", "you", "we", "he", "she", "it", "they", "my", "your", "our", "his", "her", "their",
}


def detect_negated_terms(raw_query: str) -> list[str]:
    """Parse explicitly unwanted notes/accords from phrases like 'no vanilla',
    'not sweet', 'without rose', 'avoid oud' - so the decision engine can
    penalize matching perfumes instead of the keyword engine naively treating
    the mentioned word as something to reward. Deliberately best-effort (up
    to 2 words after the trigger, stopping at a clause boundary or a small
    conjunction/pronoun/filler list): over-capturing is harmless here since
    the penalty in decision_engine only fires when a captured phrase actually
    matches a real note/accord on a candidate, so a stray non-fragrance word
    extracted from unrelated phrasing (e.g. "no idea") simply never matches
    anything and has no effect.

    The clause-boundary split matters: without it, "no vanilla, I want musk"
    - a new clause, not a continuation of what's unwanted - would capture "I"
    as if it were part of the negated phrase ("vanilla i"), a garbage term
    that then also fails to match anything, silently defeating both the SQL
    exclusion push-down and the Python penalty for the one term (vanilla)
    that genuinely should have been excluded."""
    if not raw_query:
        return []
    q = raw_query.lower()
    negated = []
    for m in _NEGATION_TRIGGER_PATTERN.finditer(q):
        rest = q[m.end():]
        clause = _NEGATION_CLAUSE_BOUNDARY.split(rest, maxsplit=1)[0]
        words = re.findall(r"[a-z][a-z\-]*", clause)[:2]
        phrase_words = []
        for w in words:
            if w in _NEGATION_STOP_WORDS:
                break
            phrase_words.append(w)
        if phrase_words:
            negated.append(" ".join(phrase_words))
    return list(dict.fromkeys(negated))
