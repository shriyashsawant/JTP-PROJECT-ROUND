"""
AuraMatch AI - Image Embedding Column
Adds a 64-dim VECTOR column for visual similarity search (color histograms).
"""

from alembic import op
import sqlalchemy as sa

revision = "0009_image_embedding"
down_revision = "0008_last_embedded_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE perfumes
            ADD COLUMN IF NOT EXISTS image_embedding VECTOR(64);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_perfumes_image_embedding
            ON perfumes
            USING hnsw (image_embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 200);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_perfumes_image_embedding;")
    op.execute("ALTER TABLE perfumes DROP COLUMN IF EXISTS image_embedding;")
