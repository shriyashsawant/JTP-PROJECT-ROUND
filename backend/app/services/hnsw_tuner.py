"""
AuraMatch AI - HNSW Index Auto-Tuner
Calibrates `hnsw.ef_search` dynamically per-query based on selectivity and
budget stringency, rather than using a single fixed heuristic.

The tradeoff: higher ef_search -> better recall (more candidates survive the
ANN filter) but slower queries. Lower ef_search -> faster but riskier for
selective filters (tight budgets, brand exclusions).

Caches a base ef_search from a startup calibration sweep against a held-out
eval set, then adjusts per-query by a selectivity multiplier.
"""

import structlog

import numpy as np

from app.core.config import settings

logger = structlog.get_logger(__name__)

# Postgres hard limit for hnsw.ef_search
EF_SEARCH_MAX = 1000
EF_SEARCH_MIN = 100

# Calibration: eval queries to run at startup.
# These are embedded and compared against the full perfume collection to
# measure how many of the true (brute-force) top-100 are captured at each
# ef_search level.
EVAL_QUERIES = [
    "fresh citrus scent for the office",
    "warm woody fragrance for winter",
    "long lasting sweet perfume for parties",
    "affordable daily wear masculine cologne",
    "cheaper alternative to Bleu de Chanel",
]

_BASE_EF_SEARCH: int = 400


async def calibrate(embed_fn, execute_fn, execute_with_ef_fn=None) -> int:
    """Run calibration at startup to find the best base ef_search.

    `embed_fn(query: str) -> list[float]` — generates an embedding for
    each eval query.

    `execute_fn(sql: str, *args) -> list[dict]` — runs raw SQL and
    returns rows (used instead of depending on asyncpg machinery at
    import time).

    `execute_with_ef_fn(ef_search: int, sql: str, *args) -> list[dict]` —
    runs raw SQL after setting `SET LOCAL hnsw.ef_search = ef_search`.
    If not provided, ef_search sweep is skipped and the default is kept.

    Strategy: sweeps ef_search = [100, 200, 400, 600, 800, 1000] and
    picks the lowest value with recall@100 >= 0.95 (or the max if no
    value achieves it).
    """
    global _BASE_EF_SEARCH

    if execute_with_ef_fn is None:
        logger.info("hnsw_autotune_skipped_no_executor")
        return _BASE_EF_SEARCH

    try:
        candidate_efs = [100, 200, 400, 600, 800, 1000]

        # Get brute-force (no index) top-100 ids for each eval query
        brute_force_ids: list[set[int]] = []
        for query in EVAL_QUERIES:
            emb = await embed_fn(query)
            if emb is None:
                continue
            rows = await execute_fn(
                """
                SELECT id FROM perfumes
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> $1::vector
                LIMIT 100
                """,
                str(emb),
            )
            brute_force_ids.append({r["id"] for r in rows})

        if not brute_force_ids:
            logger.warning("hnsw_autotune_no_data")
            return _BASE_EF_SEARCH

        best = candidate_efs[-1]
        for ef in candidate_efs:
            recall_sum = 0.0
            query_count = 0
            for qi, query in enumerate(EVAL_QUERIES):
                if qi >= len(brute_force_ids):
                    continue
                emb = await embed_fn(query)
                if emb is None:
                    continue
                rows = await execute_with_ef_fn(
                    ef,
                    """
                    SELECT id FROM perfumes
                    WHERE embedding IS NOT NULL
                    ORDER BY embedding <=> $1::vector
                    LIMIT 100
                    """,
                    str(emb),
                )
                ann_ids = {r["id"] for r in rows}
                if len(ann_ids) > 0:
                    recall = len(ann_ids & brute_force_ids[qi]) / len(ann_ids)
                else:
                    recall = 0.0
                recall_sum += recall
                query_count += 1

            avg_recall = recall_sum / max(query_count, 1)
            logger.info(
                "hnsw_autotune_ef",
                ef_search=ef,
                recall=round(avg_recall, 4),
            )
            if avg_recall >= 0.95:
                best = ef
                break

        _BASE_EF_SEARCH = best
        logger.info("hnsw_autotune_done", ef_search=best, method="sweep")
    except Exception:
        logger.warning("hnsw_autotune_failed", exc_info=True, ef_search=_BASE_EF_SEARCH)

    return _BASE_EF_SEARCH


def dynamic_ef_search(
    pool_size: int,
    budget: float | None = None,
    has_exclusions: bool = False,
) -> int:
    """Compute per-query ef_search based on pool_size, budget stringency,
    and whether exclusion filters (brand, negated terms) are active.

    The formula:
    1. Start from the calibrated base (_BASE_EF_SEARCH)
    2. Scale by pool_size / 500 (larger pools need wider search)
    3. Scale up by 1.5x if there are exclusions (brand filters, negated terms)
    4. Scale up by 1.3x if budget is tight (< 2000 INR)
    5. Clamp to [EF_SEARCH_MIN, EF_SEARCH_MAX]
    """
    ef = _BASE_EF_SEARCH
    ef = ef * max(1.0, pool_size / 500.0)
    if has_exclusions:
        ef *= 1.5
    if budget is not None and budget < 2000:
        ef *= 1.3
    return max(EF_SEARCH_MIN, min(EF_SEARCH_MAX, int(ef)))


def get_base_ef_search() -> int:
    return _BASE_EF_SEARCH
