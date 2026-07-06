"""
AuraMatch AI - Optional LLM Enrichment Layer
Re-ranks/re-explains the DETERMINISTIC engine's own candidate pool via Groq.
The LLM never invents perfumes, scores, or facts - it only picks which of
the real, already-scored candidates to surface (from the wider ANN pool,
not just the final top-N) and writes the explanation text, grounded
strictly in the accords/notes/scores we hand it. Fully optional: any
failure at all (missing key, timeout, network error, malformed response)
returns None, and callers fall back to the deterministic result untouched -
this layer must never be able to fail a request.
"""
import json
import logging

import httpx

from app.core.config import settings
from app.services.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_TIMEOUT = 3.0

_client: httpx.AsyncClient | None = None

# 5 consecutive failures trips the breaker; after 30s it lets one trial
# request through to probe recovery. While open, calls are rejected instantly
# (no network attempt, no timeout wait) so a Groq outage can't turn into a
# repeated ~3s latency tax on every search - the deterministic ranking is
# already a complete, correct result on its own; Groq only ever re-ranks it.
_groq_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0)


def get_http_client() -> httpx.AsyncClient:
    """Shared client so repeated Groq calls reuse a pooled TCP connection
    instead of paying a fresh connection setup on every request."""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=GROQ_TIMEOUT)
    return _client


async def close_http_client():
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def _build_prompt(query: str, candidates: list[dict], limit: int) -> str:
    lines = [
        f'User is looking for: "{query}"',
        "",
        f"Here are {len(candidates)} real candidate perfumes from our database, "
        "each with its actual accords, notes, and a computed match score "
        "(0-100) from our own scoring engine (occasion/longevity/projection/"
        "note-match/price fit already factored in):",
        "",
    ]
    for c in candidates:
        lines.append(json.dumps({
            "id": c["id"], "brand": c["brand"], "perfume": c["perfume"],
            "accords": (c.get("main_accords") or [])[:8],
            "notes": (c.get("notes") or [])[:10],
            "match_score": c.get("match_score"),
            "price_inr": c.get("price_inr"),
        }))
    lines.append("")
    lines.append(
        f"Pick the best {limit} of these (by id) for this user, in ranked "
        "order. You may reorder or drop weak matches, but ONLY choose from "
        "the ids listed above - never invent a perfume not in this list. "
        "Prefer variety across brands in your final picks - avoid choosing "
        "more than 2 from the same brand unless its match_scores are "
        "clearly and substantially higher than every other option, since a "
        "user expects a range of real choices, not one brand's catalog. "
        "For each pick, write a 1-2 sentence expert fragrance-consultant "
        "explanation using ONLY the accords/notes given above - do not "
        "invent notes, ratings, or facts not present in the data."
    )
    lines.append(
        'Respond with ONLY strict JSON: {"results": [{"id": <int>, '
        '"explanation": "<text>"}, ...]} - no markdown, no commentary.'
    )
    return "\n".join(lines)


async def _call_groq(prompt: str) -> dict:
    """The atomic unit the circuit breaker measures: a timeout, connection
    error, non-2xx status, or malformed JSON all raise from here, so every
    real failure mode counts toward tripping the breaker - not just
    network-level exceptions that would occur before `raise_for_status`."""
    client = get_http_client()
    resp = await client.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {settings.groq_api_key}"},
        json={
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": "You are a fragrance consultant. Respond with strict JSON only."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.4,
            "response_format": {"type": "json_object"},
        },
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return json.loads(content)


async def enhance_with_llm(query: str, candidates: list[dict], limit: int) -> list[dict] | None:
    """Returns a re-ranked/re-explained subset of `candidates` (the same real
    dicts, untouched except for `explanation`), or None on any failure -
    callers must fall back to the deterministic order untouched in that case."""
    if not settings.groq_api_key or not candidates:
        return None
    try:
        prompt = _build_prompt(query, candidates, limit)
        parsed = await _groq_breaker.call(_call_groq, prompt)
    except CircuitBreakerOpenError:
        # Groq has failed repeatedly and recently - skip straight to the
        # fallback without attempting the call (and its ~3s timeout) at all.
        logger.debug("Groq circuit breaker open; skipping call and using deterministic ranking")
        return None
    except Exception:
        # Deliberately broad: timeout, connection error, auth failure, rate
        # limit, malformed JSON, unexpected response shape - all degrade to
        # the deterministic result rather than ever raising. Still logged
        # (not silent) so a persistent Groq-side problem is observable
        # instead of just quietly never showing up in results.
        logger.warning("LLM enrichment failed, falling back to deterministic ranking", exc_info=True)
        return None

    by_id = {c["id"]: c for c in candidates}
    picks = parsed.get("results", []) if isinstance(parsed, dict) else []
    out = []
    for pick in picks:
        if not isinstance(pick, dict):
            continue
        cand = by_id.get(pick.get("id"))
        if not cand:
            continue
        enriched = dict(cand)
        explanation = pick.get("explanation")
        if explanation and isinstance(explanation, str):
            enriched["explanation"] = explanation
        out.append(enriched)
        if len(out) >= limit:
            break
    return out or None
