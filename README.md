# AuraMatch AI - Olfactory Matching & Suggestion Platform

AuraMatch AI is a semantic fragrance matching and recommendation application. It translates natural language context (such as, "I need a fresh summer scent for the office commute that projects well") into high-dimensional vector embeddings, conducting similarity queries against a database of over 40,000 scents to identify optimal fragrance choices and budget-friendly alternatives.

---

## 1. Project Motivation and Technical Novelty

### 1.1 Why This Project?
Traditional retail search systems rely on simple keyword matches (e.g. tag containment searches). This approach fails to capture the complex, subjective, and layered properties of fragrance profiles. AuraMatch AI solves this by combining semantic vector searching with a deterministic olfactory decision engine. The platform goes beyond simple nearest-neighbor calculations, evaluating candidate profiles on budget metrics, volatility constraints, gender indicators, and scent notes.

### 1.2 What Makes It Special?
*   **Decoupled Semantic Retrieval**: The core application runs embedding generation locally using `all-MiniLM-L6-v2`. This design handles matching without mandatory external LLM API dependencies, allowing the application to run fully offline.
*   **Fail-Safe LLM Re-Ranking**: If a Groq API key is available, an enrichment layer format prompts to generate natural language explanations. This layer is protected by a circuit breaker; if the external API times out or fails, the engine falls back to the deterministic match results instantly with zero user-facing latency.
*   **Priority-Based Ingestion**: The system handles duplicate records using case-insensitive normalized keys and source-priority hierarchies. Highly curated listings automatically override lower-quality batch CSV imports during upserts.
*   **Schema Migration Safety**: Schema modifications are tracked dynamically via Alembic migrations, allowing database structures to evolve without data loss.

---

## 2. Core Architecture and Component Layout

AuraMatch AI is built using a decoupled containerized model running on a custom Docker bridge network (`auramatch_net`).

| Tier | Component | Description |
| :--- | :--- | :--- |
| **Presentation** | Next.js 14 Web Application | Built with React, TypeScript, and TailwindCSS. Offers interfaces for context search, details, and duplicate finding. |
| **Application** | FastAPI Backend API | Written in Python 3.11, using Pydantic validation, asyncpg database pools, and locally hosted SentenceTransformers. |
| **Persistence** | PostgreSQL 16 + pgvector | Self-contained vector database, pre-loaded with over 40,000 fragrances and optimized with HNSW indices. |
| **Orchestration**| Docker Compose | Coordinates multi-container network boundaries and environment variables. |

For detailed system specs, refer to:
*   [System Architecture Guide](file:///c:/Users/SHRIYASH%20SAWANT/OneDrive/Desktop/JTP-PROJECT%20ROUND/documentation/SYSTEM_ARCHITECTURE.md)
*   [Decision Engine Scoring Logic Guide](file:///c:/Users/SHRIYASH%20SAWANT/OneDrive/Desktop/JTP-PROJECT%20ROUND/documentation/DECISION_ENGINE.md)
*   [Data Ingestion and Schema Migrations Guide](file:///c:/Users/SHRIYASH%20SAWANT/OneDrive/Desktop/JTP-PROJECT%20ROUND/documentation/DATA_INGESTION_PIPELINE.md)
*   [Third-Party API Integration Guide](file:///c:/Users/SHRIYASH%20SAWANT/OneDrive/Desktop/JTP-PROJECT%20ROUND/documentation/THIRD_PARTY_API.md)
*   [Testing & Observability Guide](file:///c:/Users/SHRIYASH%20SAWANT/OneDrive/Desktop/JTP-PROJECT%20ROUND/documentation/TESTING_AND_OBSERVABILITY.md)

---

## 3. How to Run the Application (Plug and Play)

AuraMatch AI is fully self-contained. No external API keys or cloud credentials are required to start the system.

### 3.1 Step 1: Clone the Repository
```bash
git clone https://github.com/shriyashsawant/JTP-PROJECT-ROUND.git
cd JTP-PROJECT-ROUND
```

### 3.2 Step 2: Spin Up Containers
```bash
docker compose up --build -d
```
*   **Note**: The database container is pre-loaded with schema configurations and seeding files, auto-loading 40K+ perfumes on first boot. The backend container applies any pending database migrations automatically on startup before serving requests - no manual migration step is required.
*   First boot restores ~40K rows and can take several minutes depending on disk speed; subsequent restarts are fast since the data persists in a Docker volume.

### 3.3 Step 3: Access the Interfaces
*   **Web Portal**: [http://localhost:3000](http://localhost:3000) - the intended way to use the app; no API key needed, the frontend handles this internally (see §7).
*   **Swagger API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs) - browsable schema reference. To actually call `/search/context`, `/search/dupe`, or `/perfume/{id}` here (via "Try it out"), you need an API key first - see §7.

---

## 4. Ingestion Data Structure

The ingestion pipeline deduplicates and processes data from four primary sources:
1.  **DA Fragrance Analysis (Fragrantica Scraped)**: 38,000 raw rows containing detailed accords and ingredients.
2.  **Fragrantica Cleaned**: 24,000 rows containing structured top, heart, and base notes.
3.  **Nandini Perfumes**: 2,200 rows containing image links and product descriptions.
4.  **Indian Brand Supplement**: Mass-market curated data.

*   **Pricing**: Prices are normalized into INR (₹) using brand-tier estimates (ranging from luxury designers to local brands).
*   **Longevity/Sillage**: Generated at ingestion using position-weighted accord profiles. Heavier accords (leather, woods) receive higher longevity weights, while highly volatile notes (citrus, green) receive lower weights.

---

## 5. API Reference Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/search/context` | Evaluates natural language query inputs along with explicit scenario and filter preferences. |
| `POST` | `/api/v1/search/dupe` | Identifies affordable alternative scents within the specified budget limits. |
| `GET` | `/api/v1/perfume/{id}` | Returns metadata, sillage/longevity scores, and scent pyramids for a selected perfume. |
| `GET` | `/api/v1/health` | Verifies database connectivity. |

---

## 6. QA Verification and Testing

The application is validated by a test suite comprising **210 unit and integration tests** covering matching logic, intent detection, circuit breaker/rate-limiter operations, API key authentication, schemas, and database fallbacks.

To execute tests locally:
```bash
cd backend
.venv\Scripts\python -m pytest
```

Mypy type checking and Ruff lint configurations are fully clean across core service files.

---

## 7. Authenticating API Requests

Every search/lookup endpoint (`/search/context`, `/search/dupe`, `/perfume/{id}`) requires an `X-API-Key` header - `/health` is the only exception. The web portal already has its own key baked in at build time, so using [http://localhost:3000](http://localhost:3000) works with no extra steps.

To call the API directly (via `curl`, Postman, or Swagger's "Try it out"), issue yourself a key first:
```bash
cd backend
python scripts/issue_api_key.py --type secret --label "manual testing" --rate-limit 300
```
This prints a raw key once (save it - it can't be recovered afterward). Send it as `X-API-Key: <key>` on each request. Full details - the publishable-vs-secret key model, rate limits, and error format - are in [documentation/THIRD_PARTY_API.md](file:///c:/Users/SHRIYASH%20SAWANT/OneDrive/Desktop/JTP-PROJECT%20ROUND/documentation/THIRD_PARTY_API.md).
