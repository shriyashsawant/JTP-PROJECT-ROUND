"""Add source, source_priority, model_version columns to perfumes.

Supports the ingestion-hardening upsert (backend/app/ingestion/upsert.py):
`source`/`source_priority` let a live/imported/user-submitted upsert check
"does this incoming record actually outrank what's already stored" before
overwriting a row - the same source-priority invariant seed_data.py's
one-time in-memory batch dedup already enforces (curated_merged=5 >
nandini=4 > fra_cleaned=3 > fra_perfumes=2 > da_fragrance=1), now persisted
so it survives a live, one-row-at-a-time upsert instead of only existing
during a single batch run. `model_version` supports incremental
re-embedding later (Phase 1c) by tracking which embedding model produced
each row's vector.

Existing rows predate this concept entirely, so they're backfilled to
source_priority=0 ("legacy_seed", lowest priority) rather than left NULL -
`EXCLUDED.source_priority >= perfumes.source_priority` in the upsert would
otherwise compare against NULL (always UNKNOWN in SQL), meaning no live
source could ever update a legacy row at all.

Revision ID: 0002_ingestion_columns
Revises: 0001_baseline
Create Date: 2026-07-06 06:26:31.206721

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_ingestion_columns"
down_revision: str | Sequence[str] | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("perfumes", sa.Column("source", sa.Text(), nullable=True))
    op.add_column("perfumes", sa.Column("source_priority", sa.SmallInteger(), nullable=True))
    op.add_column("perfumes", sa.Column("model_version", sa.Text(), nullable=True))

    op.execute(
        "UPDATE perfumes SET source = 'legacy_seed', source_priority = 0 "
        "WHERE source_priority IS NULL"
    )


def downgrade() -> None:
    op.drop_column("perfumes", "model_version")
    op.drop_column("perfumes", "source_priority")
    op.drop_column("perfumes", "source")
