"""Add normalized_key column for case/punctuation-insensitive dedup matching.

The existing `uq_perfume_brand UNIQUE (brand, perfume)` constraint (see
01_schema.sql) matches on raw text, while seed_data.py's own batch-dedup
key is `normalize_name()` (lowercased, punctuation-stripped) - a live
upsert of e.g. "Dior" vs "DIOR " would pass the raw constraint as two
distinct rows even though the existing batch logic would have merged them.

This is deliberately a plain column, not a Postgres GENERATED column: it's
computed in Python by app.ingestion.upsert (reusing seed_data.normalize_name
as the single source of truth) on every write, rather than duplicating that
regex logic a second time in SQL and risking the two definitions drifting
apart. The one-time backfill below for existing rows uses a SQL
approximation of the same normalization - close enough for legacy matching,
not required to be byte-exact since it's a one-off historical backfill.

Deliberately NOT a unique constraint. Checked the live dataset before
writing this migration: one real, ambiguous pair already exists under full
normalization - "Acqua di Parma / Colonia Club" (₹2,316) vs "Acqua di Parma
/ Colonia C.L.U.B." (₹3,470, likely a different size/SKU, not obviously a
duplicate to auto-merge). A hard unique constraint would fail on this row
today and forcing a resolution here would be a data-quality judgment call
that doesn't belong in a schema migration. The ingestion upsert logic
handles 0/1/multiple normalized-key matches explicitly instead of assuming
the DB enforces uniqueness - see app/ingestion/upsert.py.

Revision ID: 0003_normalized_key
Revises: 0002_ingestion_columns
Create Date: 2026-07-06 06:29:50.724071

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_normalized_key"
down_revision: str | Sequence[str] | None = "0002_ingestion_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("perfumes", sa.Column("normalized_key", sa.Text(), nullable=True))
    op.create_index("idx_perfumes_normalized_key", "perfumes", ["normalized_key"])

    op.execute(
        """
        UPDATE perfumes SET normalized_key =
            regexp_replace(regexp_replace(lower(trim(brand)), '[^a-z0-9 ]', '', 'g'), '\\s+', ' ', 'g')
            || '|' ||
            regexp_replace(regexp_replace(lower(trim(perfume)), '[^a-z0-9 ]', '', 'g'), '\\s+', ' ', 'g')
        WHERE normalized_key IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("idx_perfumes_normalized_key", table_name="perfumes")
    op.drop_column("perfumes", "normalized_key")
