"""Backfill perfume type column from name using concentration patterns.

The seeder (seed_data.py) never populated the `type` column on the perfumes
table even though Fragrantica data has concentration info embedded in perfume
names (eau de parfum, eau de toilette, cologne, etc). Until now the backend
has been parsing this on-the-fly at request time in
db_repository._parse_concentration_type (a regex per row) - a per-request cost
that scales linearly with the candidate pool size (up to 1,000 rows).

This migration runs the same parsing logic as a one-time SQL UPDATE so the
column has real values and the request-time fallback only ever fires for the
tiny fraction of rows whose name has no recognizable concentration marker
(~5-8% of the catalog - flankers named by descriptor alone like "Intense",
"Le Parfum" which is the Parfum concentration in French).

Revision ID: 0005_backfill_type
Revises: 0004_api_keys
Create Date: 2026-07-15

"""
from collections.abc import Sequence

from alembic import op

revision: str = "0005_backfill_type"
down_revision: str | Sequence[str] | None = "0004_api_keys"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        UPDATE perfumes
        SET type = CASE
            WHEN perfume ILIKE '%eau de toilette%' OR perfume ~* '\yedt\y' THEN 'Eau de Toilette'
            WHEN perfume ILIKE '%eau de parfum%' OR perfume ~* '\yedp\y' THEN 'Eau de Parfum'
            WHEN perfume ILIKE '%extrait de parfum%' OR perfume ILIKE '%extrait%' THEN 'Extrait de Parfum'
            WHEN perfume ILIKE '%cologne%' OR perfume ~* '\yedc\y' THEN 'Eau de Cologne'
            WHEN perfume ILIKE '%elixir%' THEN 'Elixir'
            WHEN perfume ILIKE '%parfum%' THEN 'Parfum'
            WHEN perfume ILIKE '%body spray%' OR perfume ILIKE '%deodorant%' OR perfume ILIKE '%body mist%' OR perfume ILIKE '%mist%' THEN 'Body Spray'
            ELSE NULL
        END
        WHERE type IS NULL
    """)


def downgrade() -> None:
    op.execute("UPDATE perfumes SET type = NULL WHERE type IS NOT NULL")
