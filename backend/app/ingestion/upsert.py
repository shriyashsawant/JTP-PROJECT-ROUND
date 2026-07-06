"""
AuraMatch AI - Ingestion Upsert
Replaces seed_data.py's old `INSERT ... ON CONFLICT DO NOTHING`, which
silently dropped any update to an already-seeded perfume (a corrected
price, a richer note list from a higher-priority source re-run) instead of
applying it - harmless for a one-shot batch seed, a real data-loss bug the
moment ingestion becomes live/repeated.
"""
import logging

from app.ingestion.contracts import PerfumeRecord

logger = logging.getLogger(__name__)


async def upsert_perfume(
    conn,
    record: PerfumeRecord,
    embedding_literal: str | None,
    longevity_score: float,
    sillage_score: float,
    model_version: str | None = None,
) -> None:
    """Idempotent insert-or-update for one PerfumeRecord.

    Preserves the same source-priority invariant seed_data.load_all_datasets
    already enforces in-memory during its one-time batch dedup (higher-
    priority sources' data always wins) - now persisted via the `source`/
    `source_priority` columns (migration 0002_ingestion_columns) so it holds
    for a live, one-row-at-a-time upsert too, not just a single batch run.
    A lower-priority incoming record is silently skipped (not an error -
    this is the expected, common case for a stale re-scrape).

    Matches first on the exact (brand, perfume) unique constraint (fewest
    false merges), falling back to the normalized_key index (migration
    0003_normalized_key) only when no exact match exists. If more than one
    existing row already shares that normalized_key, this is a genuinely
    ambiguous case (see that migration's docstring for a real example found
    in the live dataset) - logs a warning and falls through to a plain
    insert via the exact-match constraint rather than guessing which
    existing row to update.

    `embedding_literal=None` preserves the existing stored embedding
    (COALESCE) instead of overwriting it - the caller only needs to pass a
    freshly computed embedding when text-affecting fields actually changed,
    enabling incremental (not full-recompute) re-embedding as a natural
    follow-on; this integration always passes a real embedding for now."""
    existing = await conn.fetchrow(
        "SELECT id, source_priority FROM perfumes WHERE brand = $1 AND perfume = $2",
        record.brand, record.perfume,
    )

    if existing is None:
        normalized_matches = await conn.fetch(
            "SELECT id, source_priority FROM perfumes WHERE normalized_key = $1",
            record.normalized_key,
        )
        if len(normalized_matches) == 1:
            existing = normalized_matches[0]
        elif len(normalized_matches) > 1:
            logger.warning(
                "Ambiguous normalized_key match for %r / %r (%d existing rows share "
                "this key) - inserting as a new row rather than guessing which to update",
                record.brand, record.perfume, len(normalized_matches),
            )

    if existing is not None:
        existing_priority = existing["source_priority"] or 0
        if record.source_priority < existing_priority:
            logger.debug(
                "Skipping upsert for %r / %r: incoming source_priority=%d < existing=%d",
                record.brand, record.perfume, record.source_priority, existing_priority,
            )
            return
        await conn.execute(
            """
            UPDATE perfumes SET
                launch_year = $2, gender = COALESCE($3, gender),
                main_accords = $4, notes = $5,
                embedding = COALESCE($6::vector, embedding),
                price_inr = COALESCE($7, price_inr),
                image_url = COALESCE($8, image_url),
                longevity_score = $9, sillage_score = $10,
                url = COALESCE($11, url), country = COALESCE($12, country),
                perfumer = COALESCE($13, perfumer),
                top_notes = $14, heart_notes = $15, base_notes = $16,
                source = $17, source_priority = $18,
                normalized_key = $19, model_version = COALESCE($20, model_version)
            WHERE id = $1
            """,
            existing["id"], record.launch_year, record.gender,
            record.accords or None, record.notes or None,
            embedding_literal, record.real_price_inr, record.image_url,
            longevity_score, sillage_score, record.url, record.country,
            record.perfumer, record.notes_top or None, record.notes_middle or None,
            record.notes_base or None, record.source, record.source_priority,
            record.normalized_key, model_version,
        )
        return

    await conn.execute(
        """
        INSERT INTO perfumes
            (brand, perfume, launch_year, gender, main_accords, notes,
             embedding, price_inr, type, image_url,
             longevity_score, sillage_score, url, country, perfumer,
             top_notes, heart_notes, base_notes,
             source, source_priority, normalized_key, model_version)
        VALUES ($1,$2,$3,$4,$5,$6,$7::vector,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22)
        ON CONFLICT (brand, perfume) DO NOTHING
        """,
        record.brand, record.perfume, record.launch_year or "Unknown", record.gender,
        record.accords or None, record.notes or None, embedding_literal,
        record.real_price_inr, None, record.image_url,
        longevity_score, sillage_score, record.url, record.country, record.perfumer,
        record.notes_top or None, record.notes_middle or None, record.notes_base or None,
        record.source, record.source_priority, record.normalized_key, model_version,
    )
