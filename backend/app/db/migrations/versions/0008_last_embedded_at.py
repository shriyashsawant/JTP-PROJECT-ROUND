"""
AuraMatch AI - Incremental Embedding Support
Adds `updated_at` and `last_embedded_at` columns to track which perfumes need
re-embedding, plus an auto-trigger to bump `updated_at` on row modification.
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_last_embedded_at"
down_revision = "0007_fts_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE perfumes
            ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
    """)
    op.execute("""
        ALTER TABLE perfumes
            ADD COLUMN IF NOT EXISTS last_embedded_at TIMESTAMPTZ;
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION bump_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        DROP TRIGGER IF EXISTS trg_perfumes_updated_at ON perfumes;
    """)
    op.execute("""
        CREATE TRIGGER trg_perfumes_updated_at
            BEFORE UPDATE ON perfumes
            FOR EACH ROW
            EXECUTE FUNCTION bump_updated_at();
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_perfumes_needs_embedding
            ON perfumes (last_embedded_at NULLS FIRST)
            WHERE embedding IS NULL OR last_embedded_at IS NULL
               OR last_embedded_at < updated_at;
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_perfumes_needs_embedding;")
    op.execute("DROP TRIGGER IF EXISTS trg_perfumes_updated_at ON perfumes;")
    op.execute("DROP FUNCTION IF EXISTS bump_updated_at;")
    op.execute("ALTER TABLE perfumes DROP COLUMN IF EXISTS last_embedded_at;")
    op.execute("ALTER TABLE perfumes DROP COLUMN IF EXISTS updated_at;")
