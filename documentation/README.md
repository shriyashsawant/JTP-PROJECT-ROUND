# AuraMatch AI - System Documentation Hub

Welcome to the engineering documentation hub for AuraMatch AI. This documentation is designed to give technical evaluators (JTP) a comprehensive, Google-level deep dive into the architecture, design trade-offs, algorithms, and data structures powering the platform.

---

## 1. Documentation Index

### 1.0 [Architecture Diagrams (visual)](architecture-diagram.html)
* System topology, request lifecycle, data model, and the scoring/diversity pipeline - illustrated, for a faster first read than the prose guides below. Open the linked HTML file directly in a browser (no server needed); static copies of all four plates are also embedded in the root [README.md](../README.md).

### 1.1 [Installation Guide](../INSTALLATION_GUIDE.md)
* Detailed step-by-step instructions on setting up and running the application (using Docker Compose or local host setups), environment files configuration, and database seeding details.

### 1.2 [User Manual](../USER_MANUAL.md)
* Complete guide explaining how to navigate the Vibe Check Chat, Dupe Engine, read the Scent Detail Cards, use the Developer Dashboard, and issue API keys.

### 1.3 [System Architecture](SYSTEM_ARCHITECTURE.md)
* Detailed description of system components, database schemas, pgvector indices, Next.js page layouts, and Docker containers.

### 1.4 [Decision & Scoring Engine](DECISION_ENGINE.md)
* In-depth documentation of the olfactory matching algorithms, hybrid scoring formulas, scenario maps, negation boundary logic, chemical bridge matches, sillage/longevity concentration scaling, and unisex gender modifiers.

### 1.5 [Data Ingestion & Migration Pipeline](DATA_INGESTION_PIPELINE.md)
* Explanation of database migrations (Alembic), input boundary contracts, validation filters, case-insensitive duplicate lookups, source-priority updates, and db backup processes.

### 1.6 [Frontend Architecture](FRONTEND_ARCHITECTURE.md)
* Page-by-page walkthrough, the conversational clarification flow, state management (`localStorage`-based multi-conversation persistence), API integration (typed error handling, API key wiring), and the UI decisions behind the result cards and scent pyramid.

### 1.7 [Quality Assurance, Testing & Observability](TESTING_AND_OBSERVABILITY.md)
* System test coverage, database connection doubles, API mocks, logging middleware, performance tracking, and the observability metrics roadmap.

### 1.8 [Third-Party API Integration Guide](THIRD_PARTY_API.md)
* Two-tier API key model (publishable vs. secret), token-bucket rate limiting, error format, key issuance, and the `/api/v1` versioning commitment.

### 1.9 [Groq LLM Setup & Configuration Guide](GROQ_SETUP.md)
* How to obtain, configure, and verify the optional Groq API key for fail-safe LLM re-ranking.

---

## 2. Technical Stack Summary

AuraMatch AI combines semantic search with deterministic olfactory rules and database constraints to surface matches.

*   **Frontend**: Next.js 16 (App Router), TypeScript, Tailwind CSS 4, shadcn/ui, Framer Motion.
*   **Backend**: FastAPI (Python 3.11), PostgreSQL with `pgvector` extension for ANN (Approximate Nearest Neighbor) cosine distance searches.
*   **Vector Models**: `all-MiniLM-L6-v2` locally hosted SentenceTransformer generating 384-dimensional dense vectors.
*   **LLM Layer**: Groq Cloud SDK (Llama 3) for explanation enrichment, wrapped inside a custom circuit breaker to ensure 100% service uptime even if external APIs experience downtime.
*   **Database Migrations**: Alembic tracking schema changes dynamically.

---

## 3. Development Process & AI Tool Usage

This project was built with substantial use of AI coding assistants (Claude Code) across the full development lifecycle - architecture decisions, implementation, test writing, and this documentation set itself. Every AI-assisted change in this codebase followed the same discipline: a claim or plan proposed by the AI tool was verified against the actual running system (live database queries, real HTTP requests against the containers, full test/lint/type-check runs) before being accepted, not taken on faith. Several early AI-generated architectural proposals in this project's history were explicitly rejected or scaled back (e.g. a generic "enterprise blueprint" - hexagonal architecture, Redis caching, a full OpenTelemetry mesh - was assessed as disproportionate for this system's actual scale and only its one genuinely justified piece was implemented) precisely because that verify-before-trust discipline was applied throughout, not skipped for convenience. The author remains able to explain and justify every decision and every line of code in this repository, per the project's own AI-tool usage policy.
