# AuraMatch AI 🧪

AuraMatch is an AI-powered, deterministic fragrance recommendation engine. It translates natural language human contexts (e.g., *"I need a summer scent for the gym because I sweat"*) into semantic vector embeddings to match users with high-end fragrances and budget-friendly formulation alternatives (dupes).

![AuraMatch Stack](https://img.shields.io/badge/Stack-React%20%7C%20FastAPI%20%7C%20PostgreSQL%20%7C%20Docker-1A1A1A?style=for-the-badge)

## 🎯 Why This Project?

Traditional e-commerce recommendation systems rely on rigid keyword tags (e.g., `SELECT * WHERE tag='aquatic'`). This fails to capture the nuanced, subjective nature of olfactory profiles. 

I chose to build AuraMatch to solve this friction point using **Machine Learning and Semantic Vector Search**. Instead of building another generic movie or book recommender, I engineered a highly niche domain (fragrance chemistry) that requires complex hybrid scoring: weighing **Semantic Cosine Similarity** against a dynamic **Price Optimization Decay** algorithm.

## ✨ What Makes It Special? (Deterministic-First, LLM-Optional)

AuraMatch's core pipeline is a **Retrieval-Augmented Generation (RAG) pipeline that works fully *without* an external LLM** - this is what makes it a genuinely plug-and-play Docker deployment with zero paid-API dependency.

1. The backend embeds the user's natural language query locally using `all-MiniLM-L6-v2`.
2. It queries PostgreSQL (`pgvector`) for sub-50ms cosine similarity searches across 40,000+ real fragrances.
3. A Hybrid Scorer algorithm ranks the results on occasion/longevity/projection/note-match/gender/age/price fit.
4. A deterministic heuristic engine cross-references the matched olfactory notes against the user's scenario to dynamically generate a human-readable explanation of *why* the perfume was chosen.

**Optional LLM enrichment layer.** If a `GROQ_API_KEY` is set, an additional layer (`app/services/llm_enrichment.py`) sends the deterministic engine's own wider candidate pool (real accords/notes/scores already computed - never invented) to Groq's LLM, which can reorder/drop weak picks and write a richer, more natural explanation grounded strictly in that data. This is a pure enhancement: a strict 3-second timeout wraps the call, and *any* failure (missing key, timeout, network error, malformed response) silently falls back to the deterministic result untouched. `docker compose up` with no `.env` file at all runs the full app correctly in pure-deterministic mode - the LLM layer is additive, never required.

It provides the UX benefits of a Generative AI pipeline with the speed and reliability of a localized microservice, and an optional, fail-safe path to genuine LLM-quality explanations when a key is available.

## 🏗️ Architecture & Tech Stack

This project is built using a decoupled, containerized architecture connected via a custom Docker bridge network (`auramatch_net`). There is no external cloud dependency of any kind — the Postgres/pgvector container is the sole, self-contained source of truth, pre-loaded with real data on first boot.

| Layer | Technology | Role |
|---|---|---|
| **Frontend** | Next.js 16 (App Router), TypeScript, Tailwind CSS v4, shadcn/ui, framer-motion | Brutalist luxury UI with staggered card reveals |
| **Backend API** | Python 3.11, FastAPI, asyncpg, Pydantic v2, SentenceTransformers | Async vector search + intent detection + deterministic explanation engine |
| **Database** | PostgreSQL 16 + pgvector (HNSW index) | 384-d vector storage, sub-50ms ANN queries, gender/longevity/sillage columns |
| **Containerization** | Docker Compose (custom `auramatch_net` bridge network) | 3 services: db, backend, frontend |

## 🔧 How It Works (Data Flow)

```
User Input ("22 male, office commute, gym in the evening, long lasting")
        │
        ▼
[Frontend] POST /api/v1/search/context
        │
        ▼
[Backend] 1. Detect scenarios/gender/longevity intent from the raw text (intent_detector.py)
          2. Merge with any explicit scenario/gender/scent-preference selections
          3. Enrich query with the union of matched scenarios' notes/accords
          4. Generate 384-d embedding via all-MiniLM-L6-v2
          5. pgvector ANN search over a widened candidate pool
          6. Hybrid Score = sim×0.50 + note_match×0.20 + price_fit×0.15 + gender_fit×0.07 + longevity_fit×0.08
          7. Deterministic explanation generator (~0.001s, no LLM)
        │
        ▼
[Frontend] Results grid with match scores + savings + explanations
```

## 🚀 How to Run (Plug and Play)

This application is strictly self-contained. No external API keys, cloud database, or Kaggle credentials are required.

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/auramatch-ai.git
   cd auramatch-ai
   ```

2. Spin up the ecosystem:
   ```bash
   docker compose up --build -d
   ```

3. Access the interfaces:
   - **Web Application (UI):** http://localhost:3000
   - **API Swagger Docs:** http://localhost:8000/docs

> **Note:** The database container initializes with `01_schema.sql` and auto-loads a pre-seeded `02_seed_data.sql.gz` (40K+ perfumes with embeddings already computed) via Postgres's `docker-entrypoint-initdb.d` — no manual seeding step needed. To regenerate or expand the dataset yourself, run `python backend/seed_data.py --da-only --max 8000` (local CSV, no Kaggle needed) or without `--da-only` for the full Kaggle pipeline (requires `kagglehub`).

> **Optional:** to enable the LLM re-ranking/explanation layer, copy `backend/.env.example` to `backend/.env` (for local runs) or drop a `.env` file with `GROQ_API_KEY=...` in the project root next to `docker-compose.yml` (Docker Compose reads it automatically for variable substitution). Without it, the app runs fully and correctly on the deterministic engine alone — this is optional, not required for "plug and play."

## 📂 Project Structure

```
auramatch-ai/
├── backend/
│   ├── app/
│   │   ├── api/               # FastAPI Routes (/search/context, /search/dupe, /perfume/{id}, /health)
│   │   │   ├── routes_search.py
│   │   │   └── routes_dupe.py
│   │   ├── core/
│   │   │   └── config.py      # Pydantic settings (local Postgres only)
│   │   ├── models/
│   │   │   └── schemas.py     # Request/response validation
│   │   └── services/
│   │       ├── ml_engine.py         # SentenceTransformer singleton + query builders
│   │       ├── db_repository.py     # asyncpg vector SQL queries
│   │       ├── decision_engine.py   # Hybrid scorer + deterministic explanation generator
│   │       ├── scenario_map.py      # 12 scenarios, 11 note families, keyword banks, accord weights
│   │       └── intent_detector.py   # Deterministic scenario/gender/longevity extraction from free text
│   ├── data/
│   │   ├── 01_schema.sql      # Database schema + vector indexes (runs first)
│   │   └── 02_seed_data.sql.gz # Pre-seeded 31K+ perfumes with embeddings (runs second, auto-loaded)
│   ├── seed_data.py           # ETL pipeline: merges datasets, generates embeddings, batch upserts
│   └── Dockerfile             # Multi-stage: model cached at build time
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx           # Landing: "Find your signature. Or steal theirs."
│   │   │   ├── search/page.tsx    # Vibe Check: free-text + scenario + skin type + budget
│   │   │   ├── dupe/page.tsx      # Dupe Engine: input luxury name + budget
│   │   │   ├── perfume/[id]/page.tsx  # Perfume detail with notes, accords, score
│   │   │   └── about/page.tsx
│   │   ├── components/
│   │   │   ├── PerfumeCard.tsx    # Reusable card with match score + explanation
│   │   │   ├── Navbar.tsx
│   │   │   └── Footer.tsx
│   │   └── lib/
│   │       └── api.ts            # TypeScript API client
│   ├── next.config.ts         # Standalone output for lean Docker image
│   └── Dockerfile             # Multi-stage: deps → builder → runner
├── docker-compose.yml         # 3 services + pgvector + healthchecks
├── .gitignore
└── README.md
```

## 📊 Data Pipeline

The seed engine merges up to **4 datasets** (131K raw records → ~50K deduplicated perfumes when run with the full Kaggle pipeline):

| Dataset | Source | Rows | Key Contribution |
|---|---|---|---|
| DA Fragrance Analysis | Fragrantica (scraped), local CSV | 38K | Base: brand, perfume, accords, notes |
| Fragrantica Perfumes | Kaggle | 70K | Volume + structured accords + gender |
| Fragrantica Cleaned | Kaggle | 24K | Top/middle/base notes, ratings, gender |
| Nandini Perfumes | Kaggle | 2.2K | Rich descriptions, image URLs |

The committed `02_seed_data.sql.gz` ships **31K+ deduplicated perfumes** so `docker compose up` works with zero manual steps and no Kaggle credentials.

**Gender:** Inferred deterministically from the source `Gender` field where present, and from name-based qualifiers (`Homme`/`Femme`/`for Men`/`for Women`) otherwise — never fabricated when absent.
**Longevity/Sillage:** No dataset provides real longevity/sillage ratings, so both are computed heuristically at seed time from each perfume's accord composition (heavier accords like oud/amber/leather score higher, fleeting ones like citrus/aquatic score lower), position-weighted by accord prominence.
**INR Pricing:** Estimated via brand-tier heuristics (Luxury ₹8K–30K → Indian Designer ₹299–2K). All prices in ₹.

## 🧠 Hybrid Scoring Formula

```
Final Score = sim×0.50 + note_match×0.20 + price_fit×0.15 + gender_fit×0.07 + longevity_fit×0.08

- sim: pgvector cosine similarity between the enriched query and the perfume
- note_match: fraction of query terms found verbatim in this perfume's notes/accords
- price_fit: 1.0 at/below budget/2, linear decay to 0 at budget, 1.0 if no budget set
- gender_fit / longevity_fit: neutral 1.0 unless the user explicitly signalled that
  preference (via a field or detected from free text) - never penalizes queries
  that don't care about gender/longevity
```

Scenario, gender, and "long lasting" intent are also auto-detected from the raw free-text query (`intent_detector.py`) and merged with any explicit selections, so a single compound sentence like *"22 male, office commute, gym in the evening, long lasting"* blends office + gym scenario notes, infers male, and rewards higher-longevity results — without the user having to fill out a form.

## 🌐 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/search/context` | Natural language vibe check with scenario(s) + gender + skin type + scent preference + budget |
| `POST` | `/api/v1/search/dupe` | Dupe finder: affordable alternatives within budget |
| `GET` | `/api/v1/perfume/{id}` | Full perfume details |
| `GET` | `/api/v1/health` | Health check (DB connectivity) |

## 🧪 E2E Validation

The full pipeline was validated end-to-end:
1. Query: *"summer perfume for gym because I sweat a lot"*
2. Enriched with gym scenario notes/accords
3. Embedded → pgvector cosine search → 6 results with 0.67–0.70 similarity
4. Hybrid scored and explained (deterministic, ~0.001s)
5. Top result: **love for 3 oranges** (score 76.0, ₹1,087, saves ₹1,913)

## 🧰 Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local seed)
- Node.js 20+ (for local frontend dev)

## 📝 License

MIT
