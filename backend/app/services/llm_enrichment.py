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
import httpx
from app.core.config import settings

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_TIMEOUT = 3.0


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
        "For each pick, write a 1-2 sentence expert fragrance-consultant "
        "explanation using ONLY the accords/notes given above - do not "
        "invent notes, ratings, or facts not present in the data."
    )
    lines.append(
        'Respond with ONLY strict JSON: {"results": [{"id": <int>, '
        '"explanation": "<text>"}, ...]} - no markdown, no commentary.'
    )
    return "\n".join(lines)


async def enhance_with_llm(query: str, candidates: list[dict], limit: int) -> list[dict] | None:
    """Returns a re-ranked/re-explained subset of `candidates` (the same real
    dicts, untouched except for `explanation`), or None on any failure -
    callers must fall back to the deterministic order untouched in that case."""
    if not settings.groq_api_key or not candidates:
        return None
    try:
        prompt = _build_prompt(query, candidates, limit)
        async with httpx.AsyncClient(timeout=GROQ_TIMEOUT) as client:
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
            parsed = json.loads(content)
    except Exception:
        # Deliberately broad: timeout, connection error, auth failure, rate
        # limit, malformed JSON, unexpected response shape - all degrade
        # silently to the deterministic result rather than ever raising.
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
