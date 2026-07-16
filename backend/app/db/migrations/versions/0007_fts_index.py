"""
AuraMatch AI - Full-Text Search Index for Hybrid Search
Adds a TSVECTOR column and GIN index over brand + perfume + main_accords +
notes, enabling BM25-style sparse retrieval to complement the dense ANN
vector search. Hybrid score = 0.7 * dense + 0.3 * sparse (ts_rank).

Uses a trigger instead of GENERATED ALWAYS AS because array_to_string()
is not immutable across all PostgreSQL versions, and generated columns
require immutable expressions.
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_fts_index"
down_revision = "0006_feedback_events"
branch_labels = None
depends_on = None


def _tsvector_expr() -> str:
    return (
        "to_tsvector('english', "
        "COALESCE(brand, '') || ' ' || "
        "COALESCE(perfume, '') || ' ' || "
        "COALESCE(array_to_string(main_accords, ' '), '') || ' ' || "
        "COALESCE(array_to_string(notes, ' '), '')"
        ")"
    )


def upgrade() -> None:
    op.execute("""
        ALTER TABLE perfumes
            ADD COLUMN IF NOT EXISTS search_vector tsvector;
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION update_search_vector()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.search_vector = """ + _tsvector_expr() + """;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        DROP TRIGGER IF EXISTS trg_perfumes_search_vector ON perfumes;
    """)

    op.execute("""
        CREATE TRIGGER trg_perfumes_search_vector
            BEFORE INSERT OR UPDATE OF brand, perfume, main_accords, notes
            ON perfumes
            FOR EACH ROW
            EXECUTE FUNCTION update_search_vector();
    """)

    op.execute("""
        UPDATE perfumes SET search_vector = """ + _tsvector_expr() + """
        WHERE search_vector IS NULL;
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_perfumes_fts
            ON perfumes USING GIN (search_vector);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_perfumes_fts;")
    op.execute("DROP TRIGGER IF EXISTS trg_perfumes_search_vector ON perfumes;")
    op.execute("DROP FUNCTION IF EXISTS update_search_vector;")
    op.execute("ALTER TABLE perfumes DROP COLUMN IF EXISTS search_vector;")
