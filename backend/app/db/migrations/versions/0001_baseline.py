"""Baseline - matches backend/data/01_schema.sql exactly.

This migration is deliberately a no-op. `01_schema.sql` remains the
fresh-install bootstrap (applied automatically via Postgres's
docker-entrypoint-initdb.d on a brand-new volume, using idempotent
`CREATE TABLE/INDEX IF NOT EXISTS`), and continues to define the schema as
it exists today. This revision exists only to give Alembic a stamped
starting point that both a fresh install and an existing dev volume can
agree on - `alembic stamp head` after either path (never `upgrade`, since
there is nothing to actually run).

Every schema change *after* this point must be a real Alembic migration
under this versions/ directory - `01_schema.sql` should not be hand-edited
again except to keep it in sync with this frozen baseline.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-07-06 06:25:40.565366

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0001_baseline"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op - see module docstring."""


def downgrade() -> None:
    """No-op - see module docstring."""
