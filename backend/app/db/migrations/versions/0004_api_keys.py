"""Add api_keys table for third-party API authentication.

Two key types, both resolving the same underlying constraint:
frontend/src/lib/api.ts calls this API directly from the browser (bundled
client JS, no Next.js server-side proxy exists), so it cannot hold a real
secret without leaking it to anyone who opens devtools.

- 'publishable': safe to embed in frontend JS. Restricted by
  `allowed_origins` (checked against the request's Origin header by
  app.api.auth.require_api_key) - an abuse-deterrent, not a real security
  boundary, since a non-browser caller can set any Origin it likes. The
  actual point is stopping *other websites* from reusing a scraped
  publishable key in a browser context (same model as a Google Maps
  browser key).
- 'secret': for genuine server-to-server third-party integrations. No
  Origin restriction (server callers don't reliably send one), must never
  be embedded client-side.

Only `key_hash` (sha256 of the raw key) is ever persisted - see
backend/scripts/issue_api_key.py, which prints the raw key exactly once at
issuance and never stores it. `key_prefix` is a short, non-secret slice of
the raw key kept only so an operator can visually identify which key a
`key_hash` corresponds to without re-hashing every candidate.

`allowed_origins` is the first array column added via an Alembic migration
in this repo (01_schema.sql's raw DDL uses `TEXT[]` directly; migrations
0001-0003 only touched scalar columns) - needs
`sqlalchemy.dialects.postgresql.ARRAY`, not a bare `sa.Text()`.

Revision ID: 0004_api_keys
Revises: 0003_normalized_key
Create Date: 2026-07-06 18:34:26.140704

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004_api_keys"
down_revision: str | Sequence[str] | None = "0003_normalized_key"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key_prefix", sa.Text(), nullable=False),
        sa.Column("key_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("key_type", sa.Text(), nullable=False),
        sa.Column("allowed_origins", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("rate_limit_per_minute", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("key_type IN ('publishable', 'secret')", name="ck_api_keys_key_type"),
    )
    op.create_index("idx_api_keys_key_hash", "api_keys", ["key_hash"])


def downgrade() -> None:
    op.drop_index("idx_api_keys_key_hash", table_name="api_keys")
    op.drop_table("api_keys")
