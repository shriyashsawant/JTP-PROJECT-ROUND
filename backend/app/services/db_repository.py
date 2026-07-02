from app.services.ml_engine import generate_embedding
from app.services.decision_engine import rank_and_explain


def _candidate_pool_size(limit: int) -> int:
    """Fetch a wider ANN candidate pool than requested so gender/note/longevity
    reranking in rank_and_explain has something real to reorder."""
    return min(max(limit * 5, 25), 50)


def _to_pgvector_literal(embedding: list[float]) -> str:
    """asyncpg has no built-in codec for pgvector's `vector` type - a raw Python
    list fails with 'expected str, got list'. Serialize to the text literal
    Postgres' vector input parser accepts, then cast with ::vector in SQL."""
    return "[" + ",".join(str(x) for x in embedding) + "]"


def _format_perfume_row(r) -> dict:
    return {
        "id": r["id"],
        "brand": r["brand"],
        "perfume": r["perfume"],
        "price_inr": float(r["price_inr"]) if r["price_inr"] else None,
        "notes": r["notes"] or [],
        "main_accords": r["main_accords"] or [],
        "type": r["type"],
        "gender": r["gender"],
        "longevity_score": float(r["longevity_score"]) if r["longevity_score"] else None,
        "sillage_score": float(r["sillage_score"]) if r["sillage_score"] else None,
        "similarity": float(r["similarity"]) if r.get("similarity") else 0,
        "match_score": round(float(r["similarity"]) * 100, 1) if r.get("similarity") else 0,
        "savings": None,
    }


async def search_by_context(
    db, query: str, budget: float = None, limit: int = 5,
    scenarios: list[str] = None, skin_type: str = None, raw_query: str = "",
    gender: str = None, longevity_requested: bool = False,
) -> list[dict]:
    embedding = generate_embedding(query)
    pool_size = _candidate_pool_size(limit)

    sql = """
        SELECT id, brand, perfume, price_inr, notes, main_accords, type,
               gender, longevity_score, sillage_score,
               1 - (embedding <=> $1::vector) AS similarity
        FROM perfumes
        WHERE ($2::float IS NULL OR price_inr <= $2)
        ORDER BY similarity DESC
        LIMIT $3
    """
    rows = await db.fetch(sql, _to_pgvector_literal(embedding), budget, pool_size)

    results = [_format_perfume_row(r) for r in rows]
    return rank_and_explain(
        results, query=raw_query, budget=budget, scenarios=scenarios, skin_type=skin_type,
        gender=gender, longevity_requested=longevity_requested, limit=limit,
    )


async def search_by_budget(
    db, query: str, budget: float, limit: int = 6,
    scenarios: list[str] = None, skin_type: str = None, raw_query: str = "",
    gender: str = None, longevity_requested: bool = False,
) -> list[dict]:
    embedding = generate_embedding(query)
    pool_size = _candidate_pool_size(limit)

    sql = """
        SELECT id, brand, perfume, price_inr, notes, main_accords, type,
               gender, longevity_score, sillage_score,
               1 - (embedding <=> $1::vector) AS similarity
        FROM perfumes
        WHERE price_inr <= $2
        ORDER BY similarity DESC
        LIMIT $3
    """
    rows = await db.fetch(sql, _to_pgvector_literal(embedding), budget, pool_size)

    results = [_format_perfume_row(r) for r in rows]
    return rank_and_explain(
        results, query=raw_query, budget=budget, scenarios=scenarios, skin_type=skin_type,
        gender=gender, longevity_requested=longevity_requested, limit=limit,
    )


async def get_perfume_by_id(db, perfume_id: int) -> dict | None:
    sql = """
        SELECT id, brand, perfume, launch_year, price_inr, type, gender,
               main_accords, notes, longevity_score, sillage_score, image_url
        FROM perfumes
        WHERE id = $1
    """
    r = await db.fetchrow(sql, perfume_id)
    if not r:
        return None
    return {
        "id": r["id"],
        "brand": r["brand"],
        "perfume": r["perfume"],
        "launch_year": r["launch_year"],
        "price_inr": float(r["price_inr"]) if r["price_inr"] else None,
        "currency": "INR",
        "type": r["type"],
        "gender": r["gender"],
        "main_accords": r["main_accords"] or [],
        "notes": r["notes"] or [],
        "longevity_score": float(r["longevity_score"]) if r["longevity_score"] else None,
        "sillage_score": float(r["sillage_score"]) if r["sillage_score"] else None,
        "image_url": r["image_url"],
    }


async def check_health(db) -> bool:
    try:
        await db.fetchval("SELECT 1")
        return True
    except Exception:
        return False
