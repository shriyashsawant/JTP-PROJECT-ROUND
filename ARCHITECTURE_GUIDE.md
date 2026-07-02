# Perfume Suggestion Platform — Architecture & Implementation Guide

> **Project**: AuraMatch AI — AI-Powered Fragrance Recommendation Engine  
> **Deadline**: July 8, 2026  
> **Based on**: Problem Statement + PRD + 3 Reference Projects

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Data Layer — Database & Datasets](#3-data-layer)
4. [Backend — FastAPI Recommendation Engine](#4-backend)
5. [Frontend — Next.js User Interface](#5-frontend)
6. [Dockerization & Deployment](#6-dockerization)
7. [User Flow & Features](#7-user-flow)
8. [Reference Project Mapping](#8-reference-project-mapping)
9. [Implementation Roadmap](#9-implementation-roadmap)
10. [Key Design Decisions](#10-key-design-decisions)
11. [How to Make It Better — Enhancements & Differentiators](#11-how-to-make-it-better--enhancements--differentiators)

---

## 1. Project Overview

### What We Are Building

A perfume suggestion platform where users can **ask questions in natural language** (e.g., *"I need a summer perfume for the gym because I sweat"*) or **search for affordable dupes** of luxury fragrances. The system returns **personalized recommendations with match scores**, showing multiple options with detailed information.

### Core Requirements (from Problem Statement)

| Requirement | Specification |
|---|---|
| **Type** | Matching / Recommendation Service |
| **Backend** | Python (FastAPI) |
| **Frontend** | Modern JS framework (Next.js + TypeScript) |
| **Database** | Any (PostgreSQL with pgvector recommended) |
| **Containerization** | Docker Compose with custom network |
| **Connectivity** | Frontend ↔ Backend API ↔ Database |
| **Git** | Version control from start, public GitHub repo |
| **Documentation** | README.md + docstrings + data preparation steps |

### Features (from PRD)

1. **Vibe Check (Context Search)** — Natural language text input or 3-step questionnaire
2. **Dupe Engine** — Input a luxury perfume → get budget alternatives via AI similarity
3. **Vector Search** — Semantic similarity matching using embeddings
4. **Dockerized Ecosystem** — UI, API, and DB in separate containers

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Compose (scent_net)                │
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │   Frontend    │    │   Backend    │    │  Database    │   │
│  │  (Next.js)   │───▶│  (FastAPI)   │───▶│ (PostgreSQL  │   │
│  │   :3000      │    │   :8000      │    │  + pgvector) │   │
│  │              │    │              │    │   :5432      │   │
│  └──────────────┘    └──────────────┘    └──────────────┘   │
│         │                   │                                 │
│         │     Nginx         │     SentenceTransformer         │
│         │   Reverse Proxy   │     Model (baked into image)    │
│         └───────────────────┘                                 │
└─────────────────────────────────────────────────────────────┘
```

### Repository Structure

```
perfume-suggestion-platform/
├── docker-compose.yaml          # Orchestrates all services
├── .env                         # Environment variables
├── .gitignore
├── README.md
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── dependencies.py  # DB connection pooling
│   │   │   ├── routes_search.py # Natural language search
│   │   │   └── routes_dupe.py   # Dupe finder
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py        # Pydantic settings
│   │   │   └── security.py      # Rate limiting
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── schemas.py       # Pydantic request/response models
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── ml_engine.py     # SentenceTransformer singleton
│   │       └── db_repository.py # SQL vector queries
│   └── data/
│       └── init.sql             # DB schema + seed data
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── next.config.js
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── .env.local
│   ├── app/                     # Next.js App Router
│   │   ├── layout.tsx           # Root layout (Navbar, Footer)
│   │   ├── page.tsx             # Landing page
│   │   ├── globals.css          # Tailwind + custom styles
│   │   ├── about/
│   │   │   └── page.tsx
│   │   ├── search/
│   │   │   └── page.tsx         # Vibe Check / context search
│   │   ├── dupe/
│   │   │   └── page.tsx         # Dupe Engine
│   │   └── perfume/
│   │       └── [id]/
│   │           └── page.tsx     # Perfume detail view
│   ├── components/
│   │   ├── Navbar.tsx
│   │   ├── Footer.tsx
│   │   ├── SearchBar.tsx
│   │   ├── PerfumeCard.tsx
│   │   ├── Questionnaire.tsx    # 3-step form
│   │   ├── MatchScoreBadge.tsx
│   │   ├── LoadingState.tsx
│   │   └── ui/                  # shadcn/ui primitives
│   │       ├── button.tsx
│   │       ├── input.tsx
│   │       ├── card.tsx
│   │       └── badge.tsx
│   └── lib/
│       └── utils.ts             # cn() utility
│
└── data-preparation/            # (Reference) Jupyter notebooks
    └── README.md
```

---

## 3. Data Layer

### 3.1 Datasets (from DA_Fragrance_Analysis)

Two core datasets are already cleaned and ready:

| Dataset | Rows | Key Columns | Source |
|---|---|---|---|
| `cleaned_frag_dataset.csv` | ~38K | brand, perfume, launch_year, main_accords, notes | Fragrantica (scraped) |
| `mens_sales_cleaned_dataset.csv` | ~1K | brand, title, type, price, sold | eBay (Kaggle) |

**Indian Market Adaptation** — The dataset prices (in USD) need conversion to INR. Add Indian-specific data:
- **Indian perfume brands**: Engage, Wild Stone, Fogg, Park Avenue, Bella Vita, Skinn by Titan, The Man Company, Ustraa, Bombay Perfumery, Ajmal, Al-Rehab, Neesh
- **Indian price brackets**: Mass (~₹500-1500), Mid (~₹1500-5000), Premium (~₹5000-15000), Luxury (₹15000+)
- **Currency**: All prices stored in INR (₹). Convert USD → INR using rate ~1 USD = ₹83.

### 3.2 Key Data Insights

| Insight | Value | Use in Recommendation |
|---|---|---|
| **Top notes** | Musk (4.33%), Jasmine (3.24%), Amber (3.19%) | Note-based similarity matching |
| **Top global brands by sales** | Calvin Klein (110K), Versace (96K), Davidoff (55K) | Popularity weighting |
| **Best-selling category** | Eau de Toilette (565K units) | Category filtering |
| **Price distribution** | EDP highest median price | Budget-aware recommendations |

**Indian Market Considerations**:
- **Indian consumers prefer Eau de Toilette and Body Sprays** due to hot/humid climate — lighter fragrances last better
- **Popular Indian notes**: Sandalwood, Jasmine, Rose, Musk, Saffron, Oud, Vetiver — align well with Indian traditional scents (agarbatti, attar)
- **Festive/gifting season** (Diwali, weddings) drives peak demand — can be used for seasonal recommendations
- **Price sensitivity is high** — budget is a primary filter for Indian users, making the INR-based dupe finder especially valuable
- **International brands** (Davidoff, CK, Versace) popular in metro cities; **Indian brands** (Wild Stone, Engage, Fogg) dominate tier-2/3 markets

### 3.3 Database Schema (PostgreSQL + pgvector)

```sql
-- Perfumes table
CREATE TABLE perfumes (
    id SERIAL PRIMARY KEY,
    brand VARCHAR(255) NOT NULL,
    perfume VARCHAR(255) NOT NULL,
    launch_year VARCHAR(10) DEFAULT 'Unknown',
    main_accords TEXT[],             -- array of accord strings
    notes TEXT[],                    -- array of note strings
    longevity_score FLOAT DEFAULT 0,
    sillage_score FLOAT DEFAULT 0,
    price_inr FLOAT,                 -- price in Indian Rupees
    currency VARCHAR(5) DEFAULT 'INR',
    type VARCHAR(50),               -- Eau de Parfum, Eau de Toilette, etc.
    image_url TEXT,
    embedding VECTOR(384)           -- pgvector: sentence embedding
);

-- Create vector index for similarity search
CREATE INDEX idx_perfumes_embedding ON perfumes USING ivfflat (embedding vector_cosine_ops);

-- Sales data for popularity scoring
CREATE TABLE sales (
    id SERIAL PRIMARY KEY,
    perfume_id INT REFERENCES perfumes(id),
    brand VARCHAR(255),
    title VARCHAR(255),
    price_inr FLOAT,                 -- INR pricing
    sold INT,
    type_cleaned VARCHAR(50)
);

-- Indian perfume brands (supplementary dataset for local relevance)
CREATE TABLE indian_brands (
    id SERIAL PRIMARY KEY,
    brand VARCHAR(255) NOT NULL,
    perfume VARCHAR(255) NOT NULL,
    type VARCHAR(50),
    price_inr FLOAT,
    main_accords TEXT[],
    notes TEXT[],
    embedding VECTOR(384)
);
```

### 3.4 Embedding Strategy

- **Model**: `all-MiniLM-L6-v2` (384-dim embeddings via SentenceTransformer)
- **Text to embed**: Combine `brand + perfume + main_accords + notes` into a single description string
- **Query embedding**: Encode user's natural language query the same way
- **Similarity**: Cosine similarity between query embedding and perfume embeddings

### 3.5 Hybrid Scoring (for Dupe Finder)

The dupe finder first **strictly filters** by the user's budget (`price_inr <= budget`), then scores remaining perfumes:

```
Final Score = α × CosineSimilarity(query_emb, perfume_emb)
            + β × BudgetUtilScore(price_inr, budget)
            + γ × PopularityScore(sales_volume)

Where:
- BudgetUtilScore = 1 - (price_inr / budget) — prefers perfumes closer to the user's max budget (better value)
- price_inr <= budget is a hard filter — nothing above budget is returned
- All prices in INR (₹)
- α + β + γ = 1 (tunable weights)
```

---

## 4. Backend

### 4.1 Technology Stack

| Component | Technology | Reference |
|---|---|---|
| Framework | FastAPI | PerfumeFinder used Flask; PRD recommends FastAPI |
| ORM | SQLAlchemy + asyncpg | — |
| Vector Search | pgvector (PostgreSQL extension) | PRD spec |
| Embeddings | SentenceTransformer (`all-MiniLM-L6-v2`) | PRD spec |
| Validation | Pydantic v2 | — |

### 4.2 API Endpoints

| Method | Endpoint | Description | Request | Response |
|---|---|---|---|---|---|
| `POST` | `/api/v1/search/context` | Natural language search | `{"query": "...", "budget": 2000, "limit": 5}` | `[{id, brand, perfume, match_score, price_inr, notes, accords}]` |
| `POST` | `/api/v1/search/dupe` | Find alternatives within user's budget | `{"query": "Bleu de Chanel", "budget": 2500}` | `[{id, brand, perfume, price_inr, similarity, savings}]` |
| `GET` | `/api/v1/perfume/{id}` | Get perfume details | — | `{id, brand, perfume, notes, accords, price_inr, currency}` |
| `GET` | `/api/v1/health` | Health check | — | `{"status": "ok", "db_connected": true}` |

> **Note**: All budget/price values are in **Indian Rupees (INR)**. The frontend displays `₹` prefix. The backend stores and expects INR values.

### 4.3 Key Implementation Patterns

**ML Engine Singleton** (from `ml_engine.py`):
```python
# Model loaded once at startup — baked into Docker image to avoid 1GB download on boot
from sentence_transformers import SentenceTransformer

model = None

def get_model():
    global model
    if model is None:
        model = SentenceTransformer('all-MiniLM-L6-v2')
    return model
```

**Vector Query** (from `db_repository.py`):
```python
async def search_by_context(query: str, budget: float = None, limit: int = 5):
    model = get_model()
    query_emb = model.encode(query).tolist()
    
    sql = """
        SELECT id, brand, perfume, price_inr, notes, main_accords,
               1 - (embedding <=> $1::vector) AS similarity
        FROM perfumes
        WHERE ($2::float IS NULL OR price_inr <= $2)
        ORDER BY similarity DESC
        LIMIT $3
    """
    # Execute via asyncpg connection pool
    # budget parameter is in INR

**Dupe Search with Budget Filter** (from `db_repository.py`):
```python
async def search_dupes(query: str, budget: float, limit: int = 3):
    model = get_model()
    query_emb = model.encode(query).tolist()
    
    sql = """
        SELECT id, brand, perfume, price_inr, notes, main_accords,
               1 - (embedding <=> $1::vector) AS similarity,
               1 - (price_inr / $2::float) AS budget_util
        FROM perfumes
        WHERE price_inr <= $2                   -- strict budget filter (INR)
        ORDER BY similarity DESC
        LIMIT $3
    """
    # Execute via asyncpg connection pool
    # Only perfumes priced <= user's budget (in INR) are ever returned
```

---

## 5. Frontend

### 5.1 Technology Stack

| Component | Technology | Reference |
|---|---|---|
| Framework | Next.js 14+ (App Router) | PerfumeFinder (Next.js 14), ScentMatch (Next.js 14) |
| Language | TypeScript 5 | Both references |
| Styling | Tailwind CSS 3 | Both references |
| UI Components | shadcn/ui (Radix primitives) | PerfumeFinder |
| Icons | lucide-react | PerfumeFinder |
| Animations | Framer Motion | PRD spec |
| Fuzzy Search (client) | Fuse.js | PerfumeFinder |

### 5.2 Color Palette & Typography (from PRD)

| Role | Value |
|---|---|
| Background | `#F4F4F0` (Bone) |
| Primary Text | `#1A1A1A` (Soft Black) |
| Accents | `#8C8C8C` (Muted Stone), `#D1D1C7` (Sage/Warm Grey) |
| Heading Font | Playfair Display or Cinzel |
| Body Font | Inter or Geist |

### 5.3 Page Structure & User Flow

```
Landing Page (/)
├── Bold headline: "Find your signature. Or steal theirs."
├── Two CTAs: "Match by Lifestyle" | "Find a Dupe"
│
├── Vibe Check (/search) ← "Match by Lifestyle"
│   ├── 3-step questionnaire OR free-text input
│   ├── "Analyzing olfactory profiles..." loading state
│   └── Results grid: 3-5 perfumes with Match Score badges
│
├── Dupe Engine (/dupe) ← "Find a Dupe"
│   ├── Search/select a luxury perfume
│   ├── Set your maximum budget (required)
│   └── Results: top 3 matches within budget with similarity scores
│
└── Perfume Detail (/perfume/[id])
    ├── Full details: brand, notes, accords, price
    ├── Match score visualization (gauge/progress bar)
    └── "Find dupes for this" action
```

### 5.4 Component Architecture (from both references)

```
Layout
├── Navbar (responsive, mobile hamburger)
├── Main Content (child pages)
│   ├── Home (hero + feature cards)
│   ├── Search (questionnaire + results)
│   ├── Dupe (search + results)
│   └── PerfumeDetail (full info)
└── Footer

Reusable Components:
├── SearchBar (Fuse.js fuzzy search + autocomplete dropdown)
├── PerfumeCard (image, brand, name, match score, price)
├── Card (shadcn/ui — Card, CardHeader, CardTitle, CardContent)
├── Button (shadcn/ui — variants: default, outline, ghost)
├── Input (shadcn/ui — styled input)
├── Badge (shadcn/ui — for accord/note pills)
├── MatchScoreBadge (color-coded similarity %)
├── LoadingState ("Analyzing olfactory profiles..." with spinner)
└── Questionnaire (3-step form with fade-in animations via Framer Motion)
```

### 5.5 Key Frontend Patterns

**Client-side fuzzy search** (from PerfumeFinder):
```typescript
// SearchBar.tsx — uses Fuse.js for instant autocomplete
import Fuse from 'fuse.js'

const fuse = new Fuse(perfumes, {
  keys: ['brand', 'perfume'],
  threshold: 0.4,
  limit: 5
})
```

**API call with loading state** (from ScentMatch):
```typescript
const [results, setResults] = useState<Recommendation[]>([])
const [loading, setLoading] = useState(false)

const handleSearch = async (query: string) => {
  setLoading(true)
  try {
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/search/context`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query })
    })
    const data = await res.json()
    setResults(data)
  } catch (err) {
    console.error('Search failed:', err)
  } finally {
    setLoading(false)
  }
}
```

---

## 6. Dockerization

### 6.1 Docker Compose (from PerfumeFinder + PRD)

```yaml
# docker-compose.yaml
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: scents
      POSTGRES_USER: aura
      POSTGRES_PASSWORD: match_secret
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./backend/data/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U aura -d scents"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks:
      - scent_net

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://aura:match_secret@db:5432/scents
      MODEL_NAME: all-MiniLM-L6-v2
    depends_on:
      db:
        condition: service_healthy
    networks:
      - scent_net

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      NEXT_PUBLIC_API_URL: http://backend:8000
    depends_on:
      - backend
    networks:
      - scent_net

networks:
  scent_net:
    driver: bridge

volumes:
  pgdata:
```

### 6.2 Backend Dockerfile (Multi-stage, model baked in)

```dockerfile
# backend/Dockerfile
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Pre-download the SentenceTransformer model
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.cache /root/.cache
COPY --from=builder /root/.local /root/.local
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 6.3 Frontend Dockerfile (Multi-stage, from PerfumeFinder)

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
```

> **Note**: Set `output: 'standalone'` in `next.config.js` for lean production image.

---

## 7. User Flow & Features

### 7.1 Vibe Check (Context Search)

```
User: "I need a summer perfume for the gym because I sweat"
                        │
                        ▼
  [Frontend] Free-text input OR 3-step questionnaire:
     Step 1: "What's the occasion?" (Daily/Gym/Party/Date)
     Step 2: "What's the season?" (Summer/Winter/Spring/Fall)
     Step 3: "Any scent preference?" (Fresh/Woody/Sweet/Aquatic)
                        │
                        ▼
  POST /api/v1/search/context  {"query": "summer gym sweat aquatic", "budget": 3000}
                        │
                        ▼
  [Backend] Embed query → Cosine similarity search → 
  Apply budget filter (INR) → Sort by score → Return top 5
                        │
                        ▼
  [Frontend] Show results grid:
    ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
    │  Wild Stone    │  │  D&G Light    │  │  Nautica       │
    │  Code Ocean    │  │    Blue       │  │  Voyage        │
    │  Match: 91%    │  │  Match: 87%   │  │  Match: 82%    │
    │  ₹1,299        │  │  ₹3,999       │  │  ₹2,499        │
    └────────────────┘  └────────────────┘  └────────────────┘
```

### 7.2 Dupe Engine

```
User enters a perfume name and their budget
  Example: "Bleu de Chanel" + budget ₹2,500
                        │
                        ▼
  POST /api/v1/search/dupe  {"query": "Bleu de Chanel", "budget": 2500}
                        │
                        ▼
  [Backend] Embed the query → Cosine similarity search → 
  Filter by price_inr <= ₹2,500 → Sort by similarity → Return top 3
                        │
                        ▼
  [Frontend] Show dupe comparison:
    You searched: Bleu de Chanel (typically ₹8,000+)
    Your budget: up to ₹2,500
    ┌──────────────────────────────────────────┐
    │  Armaf Club de Nuit Intense              │
    │  Price: ₹2,299  ✓ within budget          │
    │  Scent match: 91%                        │
    ├──────────────────────────────────────────┤
    │  Wild Stone Code Ocean                   │
    │  Price: ₹1,299  ✓ within budget          │
    │  Scent match: 78%                        │
    ├──────────────────────────────────────────┤
    │  Bella Vita Homme                        │
    │  Price: ₹849  ✓ within budget            │
    │  Scent match: 72%                        │
    └──────────────────────────────────────────┘
  Note: Results are strictly filtered by your budget (₹).
  No results? Try increasing your budget or broadening your search.
```

### 7.3 Perfume Detail View

Displays:
- Brand & perfume name with image
- **Notes** as pills (from ScentMatch style)
- **Main Accords** as colored badges (from DA_Fragrance_Analysis data)
- **Longevity & Sillage** gauges (from PerfumeFinder SVG pattern)
- **Price in ₹** with category label
- **Match Score** progress bar (from PRD spec)
- "Find Dupes" action button

---

## 8. Reference Project Mapping

### What Each Reference Contributes

| Reference | Contribution to Final Project |
|---|---|
| **Problem Statement** | Requirements blueprint: Docker Compose, Python backend, JS frontend, Git, documentation |
| **PRD (AuraMatch AI)** | Product vision: natural language search, dupe finder, vector embeddings, design system, Docker topology |
| **DA_Fragrance_Analysis** | Cleaned datasets (38K perfumes), data cleaning pipeline, feature engineering (notes/accords as lists), pricing & sales insights for hybrid scoring |
| **PerfumeFinder** | Architecture: Flask backend ↔ Next.js frontend + Docker Compose. Patterns: Fuse.js search, pre-computed recommendations, SVG gauges, shadcn/ui components, multi-stage Dockerfile |
| **ScentMatch** | Frontend features: ScentMatch/ Dupe Finder/ Layering Lab pages, questionnaire flow, API route pattern with TypeScript interfaces, responsive grid layout, component CSS classes |

### Architecture Decisions Guided by References

| Decision | Source | Rationale |
|---|---|---|
| FastAPI over Flask | PRD | Better async support, auto-docs, Pydantic integration |
| PostgreSQL + pgvector | PRD | Native vector search, better than SQLite |
| SentenceTransformer | PRD | Semantic embeddings for natural language queries |
| Model baked into Docker image | PRD + PerfumeFinder | Avoids 1GB download on each container start |
| shadcn/ui + Tailwind | PerfumeFinder + PRD | Polished UI with minimal effort, aligns with "Minimalist Apothecary" design |
| Fuse.js client-side search | PerfumeFinder | Instant autocomplete without backend calls |
| Hybrid scoring (semantic + price + popularity) | DA_Fragrance_Analysis insights | Better results than pure vector similarity |
| Multi-stage Docker builds | PerfumeFinder | Lean production images |
| Custom bridge network | PerfumeFinder + PRD | Container isolation with service discovery |
| Health checks | PRD | Reliable orchestration, docker-compose dependency management |

---

## 9. Implementation Roadmap (7 Days)

| Day | Focus | Tasks |
|---|---|---|
| **Day 1** | Data Preparation | Set up PostgreSQL + pgvector, import cleaned datasets from DA_Fragrance_Analysis, generate embeddings for all perfumes, write init.sql |
| **Day 2** | Backend Core | FastAPI app skeleton, Pydantic schemas, DB connection pool, health endpoint, ML engine singleton |
| **Day 3** | Backend API | `/search/context` endpoint with vector query, `/search/dupe` endpoint with hybrid scoring, `/perfume/{id}` detail endpoint |
| **Day 4** | Frontend Setup | Next.js App Router scaffold, Tailwind config with PRD palette, shadcn/ui setup, Layout (Navbar + Footer) |
| **Day 5** | Frontend Features | Landing page, SearchBar with Fuse.js, Vibe Check questionnaire, Results grid with match scores |
| **Day 6** | Frontend Features | Dupe Engine page, Perfume Detail page, loading states, animations (Framer Motion) |
| **Day 7** | Docker + Polish | Dockerfiles, docker-compose.yaml, .gitignore, README.md, final testing, GitHub push |

---

## 10. Key Design Decisions

### Why PostgreSQL + pgvector over SQLite?

| Aspect | SQLite (PerfumeFinder) | PostgreSQL + pgvector |
|---|---|---|
| Vector Search | Not supported | Native via pgvector extension |
| Concurrency | Poor for writes | Excellent |
| Scalability | Single file | Client-server, can scale |
| Embedding Index | N/A | IVFFlat index for fast ANN search |

### Why FastAPI over Flask?

| Aspect | Flask (PerfumeFinder) | FastAPI (PRD) |
|---|---|---|
| Async | Limited (via extensions) | Native async/await |
| Validation | Manual | Pydantic auto-validation |
| Auto-docs | None | Swagger UI + ReDoc |
| Performance | WSGI (sync) | ASGI (async, faster) |

### Why Hybrid Scoring?

Pure vector similarity finds perfumes with similar scent profiles but ignores budget and popularity. The hybrid score:
- **Strict budget filter first** — only perfumes within the user's specified budget are considered; nothing above is returned
- **Semantic similarity** (α = 0.5): Finds scents that match the user's description
- **Budget utilization** (β = 0.3): Prefers perfumes closer to the user's max budget (in ₹) for best value
- **Popularity** (γ = 0.2): Favors well-loved perfumes (from eBay sales data)

### Design System Choices

Following the PRD's "Minimalist Apothecary":
- **Massive whitespace** — let content breathe
- **No heavy shadows** — use subtle 1px borders instead
- **Fade-in animations** — opacity transitions, no bounce
- **Editorial typography** — Playfair Display for headings, Inter for body
- **Muted palette** — Bone, Soft Black, Muted Stone, Sage/Grey

---

## 11. How to Make It Better — Enhancements & Differentiators

### 11.1 User-Facing Enhancements

| Enhancement | Impact | Effort |
|---|---|---|
| **Regional language support** (Hindi, Tamil, Bengali) | Massively expands reach beyond English-speaking users | Medium |
| **What's in my wardrobe?** — Let users build a digital collection of perfumes they own, then recommend layering combos and fill gaps | High stickiness, personalization | Medium |
| **Occasion-based bundles** — "Pick me a wedding perfume", "Date night scent" with curated shortlists | High utility | Low |
| **Indian attar/itra section** — Traditional oil-based perfumes popular in India, priced ₹200-2000 | Differentiator, taps into cultural preference | Low (data-dependent) |
| **Gift finder** — "My mom likes floral scents, budget ₹2000" → recommend gift-wrapped options | Drives gifting use case | Medium |
| **Seasonal alerts** — Notify users when their saved perfumes are ideal for upcoming season (e.g., "Light citrus perfumes work best in Mumbai summers") | Engagement | Medium |
| **Compare perfumes side-by-side** — Show notes, longevity, sillage, price in a comparison table | Power-user feature | Low |
| **User reviews & ratings in Indian context** — "Does it last in Indian humidity?", "Good for Delhi winters?" | Community value, authenticity | High |
| **WhatsApp share** — Share recommendations with friends/family via WhatsApp (popular in India) | Viral growth | Low |

### 11.2 Technical Enhancements

| Enhancement | How | Benefit |
|---|---|---|
| **Hybrid ML: SentenceTransformer + TF-IDF** | Combine semantic embeddings with keyword-based TF-IDF on notes/accords for better accuracy | More relevant results, handles edge cases |
| **LLM-powered chat** | Use Gemini/Claude to have a conversational agent that asks clarifying questions before recommending | Feels like talking to a perfume expert |
| **Image-based search** | Upload a photo of a perfume bottle → identify via OCR/CLIP → find similar scents | Unique differentiator |
| **Real-time pricing from Indian e-commerce** | Scrape/API from Amazon India, Nykaa, Myntra, Flipkart for live prices and availability | Practical utility, users can buy immediately |
| **Caching layer (Redis)** | Cache frequent queries and embeddings | Faster response, less DB load |
| **Feedback loop** | Let users upvote/downvote recommendations → use as implicit feedback to tune weights | Self-improving system |
| **Progressive Web App (PWA)** | Add manifest + service worker so it works offline and can be installed on mobile | Better mobile experience |
| **Analytics dashboard** | Track popular searches, most-compared perfumes, budget distribution → inform inventory/features | Data-driven decisions |

### 11.3 Indian Market Specific Differentiators

| Idea | Why It Works |
|---|---|
| **"College budget" mode** — dedicated suggestions under ₹1000 using Indian brands (Wild Stone, Engage, Bella Vita) | 65%+ of India's population is under 35, price-sensitive |
| **Climate-adaptive recommendations** — "Mumbai humidity", "Delhi winter", "Bangalore pleasant" as input options | India has diverse climates; a perfume that works in Pune may fail in Chennai |
| **Deodorant-to-perfume upgrade path** — Suggest first-time perfume buyers based on their current deodorant brand | Huge market of deodorant users who can be upsold |
| **Festive collections** — Diwali specials, wedding season picks, Raksha Bandhan gifting | Ties into Indian shopping calendar |
| **Longevity rating specifically for Indian weather** — A "lasts 8 hours in AC office" vs "2 hours in Delhi heat" distinction | Most international longevity ratings are irrelevant for Indian conditions |
| **Phygital integration** — QR code on product packaging → opens app page with recommendations for similar scents | Bridges offline discovery with online recommendations |

### 11.4 Scoring Algorithm Improvements

```
Current:   Score = α·Semantic + β·BudgetUtil + γ·Popularity

Improved:  Score = α·Semantic + β·BudgetUtil + γ·Popularity + δ·ClimateFit + ε·Seasonality

Where:
- ClimateFit  — matches perfume to user's city/region climate (humid/dry/cold)
- Seasonality  — favors perfumes suitable for current season/month
- δ, ε        — additional tunable weights

This makes recommendations truly India-specific and context-aware.
```

### 11.5 Growth & Monetization Ideas

| Idea | Description |
|---|---|
| **Affiliate links** | Link to Amazon India / Nykaa / Flipkart with affiliate tags → earn commission on purchases |
| **"Try at home" samples** | Partner with Indian decant sellers (e.g., Splash Fragrance, PerfumeKing) for sample-sized recommendations |
| **Brand partnerships** | Indian perfume brands pay for featured placement in relevant search results |
| **Subscription "Scent Profile"** | Save user preferences, send monthly personalized picks via email |

---

1. **Download datasets** from DA_Fragrance_Analysis/Datasets/
2. **Clean & normalize** (already done in notebooks, but re-run if needed):
   - `1_Data_cleaning.ipynb` → `cleaned_frag_dataset.csv`
   - `3_Sales_Data_cleaning.ipynb` → `mens_sales_cleaned_dataset.csv`
3. **Convert prices to INR**:
   ```python
   # Approximate conversion: 1 USD = ₹83
   df['price_inr'] = df['price'].apply(lambda x: round(x * 83, 2) if pd.notna(x) else None)
   ```
4. **Generate embeddings** (run once, store in DB):
   ```python
   from sentence_transformers import SentenceTransformer
   model = SentenceTransformer('all-MiniLM-L6-v2')
   
   df['text'] = df['brand'] + ' ' + df['perfume'] + ' ' + df['main_accords'] + ' ' + df['notes']
   df['embedding'] = df['text'].apply(lambda x: model.encode(x).tolist())
   ```
5. **Load into PostgreSQL** via `init.sql` + Python script
6. **Create IVFFlat index** for fast approximate nearest neighbor search

---

> This guide synthesizes the **PRD product vision**, the **Problem Statement requirements**, the **DA_Fragrance_Analysis data foundation**, the **PerfumeFinder architecture patterns**, and the **ScentMatch frontend patterns** into a cohesive, actionable implementation plan for the AuraMatch AI perfume suggestion platform.
