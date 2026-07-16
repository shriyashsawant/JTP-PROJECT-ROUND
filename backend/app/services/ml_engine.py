import asyncio

from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.services.scenario_map import NOTE_FAMILIES, SCENARIO_MAP, SKIN_TYPE_MODIFIERS

_model = None
_INSTRUCTION_PREFIX = settings.query_instruction

def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.model_name)
    return _model

def _is_bge_model() -> bool:
    """BGE models (BAAI/bge-*) need instruction prefixes for optimal retrieval.
    Other SentenceTransformer models (all-MiniLM, etc) do not."""
    return "bge" in settings.model_name.lower()

def generate_embedding(text: str, is_query: bool = False) -> list[float]:
    """Generate embedding. For BGE models, prepend the query instruction
    when embedding a search query (not when embedding stored documents)."""
    if _is_bge_model() and is_query:
        text = _INSTRUCTION_PREFIX + text
    return get_model().encode(text).tolist()

async def generate_embedding_async(text: str, is_query: bool = False) -> list[float]:
    """CPU-bound SentenceTransformer inference offloaded to a worker thread.
    `is_query=True` prepends the BGE query instruction for retrieval queries."""
    return await asyncio.to_thread(generate_embedding, text, is_query)

def generate_document_embedding(text: str) -> list[float]:
    """Embed a stored document (perfume catalog text). No instruction prefix."""
    return get_model().encode(text).tolist()

async def generate_document_embedding_async(text: str) -> list[float]:
    """Embed a stored document asynchronously."""
    return await asyncio.to_thread(generate_document_embedding, text)

def _scenario_terms(scenarios: list[str] | None, key: str, cap: int) -> list[str]:
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
    query: str, scenarios: list[str] | None = None, skin_type: str | None = None,
    note_families: list[str] | None = None, reference_accords: list[str] | None = None,
    reference_notes: list[str] | None = None,
) -> str:
    """Build a rich search query from user input + optional scenarios + skin type + scent preference.

    When the free-text query names a perfume we recognize (e.g. 'cheaper
    alternative to Dior Sauvage'), `reference_accords`/`reference_notes` are
    its REAL composition - grounding the embedding in actual scent data
    instead of just hoping the model recognizes the name from text alone."""
    parts = [query]
    if reference_accords:
        parts.append(f"with {', '.join(reference_accords[:8])} character")
    if reference_notes:
        parts.append(f"featuring {', '.join(reference_notes[:10])} notes")
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
    perfume_name: str, scenarios: list[str] | None = None, skin_type: str | None = None,
    note_families: list[str] | None = None, reference_accords: list[str] | None = None,
    reference_notes: list[str] | None = None,
) -> str:
    """Build a query for dupe engine: find perfumes similar to this one.

    When the target perfume is found in our own DB, `reference_accords`/
    `reference_notes` are its REAL composition - grounding the embedding in
    actual scent data instead of just hoping the model recognizes the name.
    Without a match, this falls back to name-only best-effort search."""
    if reference_accords or reference_notes:
        parts = [f"perfume similar to {perfume_name}"]
        if reference_accords:
            parts.append(f"with {', '.join(reference_accords[:8])} character")
        if reference_notes:
            parts.append(f"featuring {', '.join(reference_notes[:10])} notes")
    else:
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
