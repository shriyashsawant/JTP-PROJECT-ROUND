-- =============================================
-- AuraMatch AI - Database Schema
-- Local pgvector, run automatically by docker-entrypoint-initdb.d
-- =============================================

CREATE EXTENSION IF NOT EXISTS vector;

-- Main perfumes table
CREATE TABLE IF NOT EXISTS perfumes (
    id SERIAL PRIMARY KEY,
    brand TEXT NOT NULL,
    perfume TEXT NOT NULL,
    launch_year TEXT DEFAULT 'Unknown',
    gender TEXT,
    main_accords TEXT[],
    notes TEXT[],
    embedding VECTOR(384),
    price_inr INTEGER,
    type TEXT,
    image_url TEXT,
    longevity_score FLOAT DEFAULT 0,
    sillage_score FLOAT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_perfumes_brand ON perfumes(brand);
CREATE INDEX IF NOT EXISTS idx_perfumes_price ON perfumes(price_inr);
CREATE INDEX IF NOT EXISTS idx_perfumes_gender ON perfumes(gender);
CREATE INDEX IF NOT EXISTS idx_perfumes_embedding ON perfumes USING hnsw(embedding vector_cosine_ops) WITH (m=16, ef_construction=200);

-- Unique constraint for upsert
ALTER TABLE perfumes ADD CONSTRAINT uq_perfume_brand UNIQUE (brand, perfume);
