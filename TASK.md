# AuraMatch AI - State-of-the-Art Transformation Plan

Current Score: **8.5/10** -> Target: **9.5/10**

---

## CRITICAL (Blocking Scale and Trust)

### 1. Upgrade Embedding Model
- Replace all-MiniLM-L6-v2 with BAAI/bge-small-en-v1.5 (same 384-dim, drop-in)
- Future: Fine-tune on 40K catalog using Matryoshka Representation Learning
- Future: Bi-encoder to cross-encoder cascade for re-ranking

### 2. Implicit Feedback + Bayesian Weight Optimization
- Add POST /api/v1/events/click and /purchase endpoints
- Daily Bayesian optimization over the 10 scoring weights
- Click-through rate on held-out week as objective

### 3. Personalization
- Session-level: LLM sees previous query/click history in-context
- User-level: Two-tower neural network (user tower from clicks, perfume tower from existing embedding)
- Cold-start: Session embedding = average of query embeddings

### 4. A/B Testing Infrastructure
- Per-request randomized feature flags via request_id hash
- Response header: X-AuraMatch-Variant
- Metrics pipeline: variant to click_rate, purchase_rate

## HIGH Impact (Visible Quality and Speed)

### 5. Hybrid Search (BM25 + Dense)
- Add pgvector TSVECTOR / BM25 index alongside ANN
- 0.7 * dense_score + 0.3 * sparse_score for candidate pool

### 6. Auto-Tune HNSW Per-Query
- Calibration query at startup against held-out eval set
- Dynamic ef_search based on budget stringency

### 7. Extend LLM Re-Ranking
- LLM returns adjusted_score and reason alongside explanation
- Weighted blend: 0.7 * deterministic + 0.3 * llm_adjusted

### 8. Explanation Quality Feedback
- Implicit signal: click after reading explanation = positive
- LLM-enriched explanations as primary when available

## MEDIUM Impact (Polish and Rigor)

### 9. Frontend State Machine + Caching + E2E
- Finite state machine for chat flow
- React Query / SWR for client-side cache
- Playwright E2E tests for full chat flow

### 10. Structured Logging + Tracing
- structlog for JSON structured logging
- OpenTelemetry for FastAPI + httpx + asyncpg traces

### 11. Failure Injection Testing
- Middleware that injects latency/errors for a fraction of requests
- Tests slow-not-down failure mode

### 12. Incremental Embedding Index
- perfumes_embedding_queue table for incremental updates
- Background worker picks up changes

### 13. Image Similarity Search
- CLIP embeddings for bottle images
- 0.8 * scent + 0.2 * image multi-modal retrieval

### 14. Read Replica Split
- Reader pool for search, writer pool for ingestion/events
- pgvector works on replicas via WAL

## Implementation Order

| # | Item | Effort | Impact | Dependencies |
|---|------|--------|--------|-------------|
| 1 | Embedding upgrade | 1 day | High | None (drop-in) |
| 2 | Feedback + Bayesian opt | 1 week | Highest | Item 1 |
| 3 | Personalization | 2-3 weeks | High | Item 2 |
| 4 | A/B testing infra | 1 week | High | None |
| 5 | Hybrid search | 1 week | High | None |
| 6 | HNSW auto-tune | 2 days | Medium | None |
| 7 | LLM re-ranking extend | 2 days | Medium | None |
| 8 | Explanation feedback | 1 day | Low | Item 2 |
| 9 | Frontend FSM + E2E | 2 weeks | Medium | None |
| 10 | Structured logging | 2 days | Medium | None |
| 11 | Failure injection | 2 days | Medium | None |
| 12 | Incremental embedding | 2 days | Low | None |
| 13 | Image search | 1 week | Low | Item 1 |
| 14 | Read replicas | 2 days | Low | None |
