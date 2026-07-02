from sentence_transformers import SentenceTransformer
from app.services.scenario_map import SCENARIO_MAP, NOTE_FAMILIES, SKIN_TYPE_MODIFIERS
from app.core.config import settings

_model = None

def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.model_name)
    return _model

def generate_embedding(text: str) -> list[float]:
    return get_model().encode(text).tolist()

def _scenario_terms(scenarios: list[str], key: str, cap: int) -> list[str]:
    """Union accords/notes across every matched scenario (deduped, capped)."""
    seen = []
    for scenario in scenarios or []:
        s = SCENARIO_MAP.get(scenario)
        if not s:
            continue
        for term in s[key]:
            if term not in seen:
                seen.append(term)
    return seen[:cap]

def build_context_query(
    query: str, scenarios: list[str] = None, skin_type: str = None,
    note_families: list[str] = None,
) -> str:
    """Build a rich search query from user input + optional scenarios + skin type + scent preference."""
    parts = [query]
    accords = _scenario_terms(scenarios, "accords", 6)
    if accords:
        parts.append(f"scents that are {', '.join(accords)}")
    if skin_type and skin_type in SKIN_TYPE_MODIFIERS:
        st = SKIN_TYPE_MODIFIERS[skin_type]
        if st["boost_families"]:
            parts.append(f"with {', '.join(st['boost_families'][:3])} notes")
    for family in note_families or []:
        if family in NOTE_FAMILIES:
            parts.append(f"with {', '.join(NOTE_FAMILIES[family][:4])} notes")
    return ". ".join(parts)

def build_budget_query(
    perfume_name: str, scenarios: list[str] = None, skin_type: str = None,
    note_families: list[str] = None,
) -> str:
    """Build a query for dupe engine: find perfumes similar to this one."""
    parts = [f"perfume similar to {perfume_name}"]
    notes = _scenario_terms(scenarios, "notes", 8)
    if notes:
        parts.append(f"with {', '.join(notes)} notes")
    if skin_type and skin_type in SKIN_TYPE_MODIFIERS:
        st = SKIN_TYPE_MODIFIERS[skin_type]
        if st["boost_families"]:
            parts.append(f"favoring {', '.join(st['boost_families'][:3])} notes")
    for family in note_families or []:
        if family in NOTE_FAMILIES:
            parts.append(f"with {', '.join(NOTE_FAMILIES[family][:4])} notes")
    return ". ".join(parts)
