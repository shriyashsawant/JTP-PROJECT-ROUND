"""
AuraMatch AI - Feedback Events Table
Records implicit user signals (clicks, purchases) so the Bayesian optimizer
can learn which scoring weights drive the best engagement.
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_feedback_events"
down_revision = "0005_backfill_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS feedback_events (
            id              BIGSERIAL PRIMARY KEY,
            event_type      TEXT NOT NULL CHECK (event_type IN ('click', 'purchase', 'dismiss')),
            perfume_id      INTEGER NOT NULL REFERENCES perfumes(id) ON DELETE CASCADE,
            query_id        TEXT NOT NULL,
            query_text      TEXT NOT NULL DEFAULT '',
            session_id      TEXT,
            variant         TEXT DEFAULT 'control',
            match_score     REAL,
            position        SMALLINT,
            dwell_ms        INTEGER,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE INDEX IF NOT EXISTS idx_feedback_events_query_id
            ON feedback_events (query_id);

        CREATE INDEX IF NOT EXISTS idx_feedback_events_created_at
            ON feedback_events (created_at);

        CREATE INDEX IF NOT EXISTS idx_feedback_events_variant
            ON feedback_events (variant);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS feedback_events CASCADE;")
