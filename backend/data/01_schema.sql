-- =============================================
-- AuraMatch AI - Database Schema
-- Local pgvector, run automatically by docker-entrypoint-initdb.d
-- =============================================

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Main perfumes table
CREATE TABLE IF NOT EXISTS perfumes (
    id SERIAL PRIMARY KEY,
    brand TEXT NOT NULL,
    perfume TEXT NOT NULL,
    launch_year TEXT DEFAULT 'Unknown',
    gender TEXT,
    main_accords TEXT[],
    notes TEXT[],
    -- Volatility pyramid: real Fragrantica Top/Middle/Base tags where the
    -- source dataset provides them, otherwise inferred from note family
    -- (see seed_data.py's infer_note_tiers). Lets the scorer reward a
    -- fresh-top/dense-base "bridge" perfume for a contradictory request like
    -- "fresh gym scent that lasts 12 hours" instead of only having one flat
    -- `notes` list to work with.
    top_notes TEXT[],
    heart_notes TEXT[],
    base_notes TEXT[],
    embedding VECTOR(384),
    price_inr INTEGER,
    type TEXT,
    image_url TEXT,
    longevity_score FLOAT DEFAULT 0,
    sillage_score FLOAT DEFAULT 0,
    url TEXT,
    country TEXT,
    perfumer TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_perfumes_brand ON perfumes(brand);
CREATE INDEX IF NOT EXISTS idx_perfumes_price ON perfumes(price_inr);
CREATE INDEX IF NOT EXISTS idx_perfumes_gender ON perfumes(gender);
CREATE INDEX IF NOT EXISTS idx_perfumes_embedding ON perfumes USING hnsw(embedding vector_cosine_ops) WITH (m=16, ef_construction=200);
CREATE INDEX IF NOT EXISTS idx_perfumes_brand_trgm ON perfumes USING gin(brand gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_perfumes_perfume_trgm ON perfumes USING gin(perfume gin_trgm_ops);
-- GIN indexes for array containment/overlap queries (e.g. excluding perfumes
-- whose notes/accords overlap a negated-term array via the `&&` operator).
CREATE INDEX IF NOT EXISTS idx_perfumes_notes_gin ON perfumes USING gin(notes);
CREATE INDEX IF NOT EXISTS idx_perfumes_accords_gin ON perfumes USING gin(main_accords);

-- Unique constraint for upsert
ALTER TABLE perfumes ADD CONSTRAINT uq_perfume_brand UNIQUE (brand, perfume);
