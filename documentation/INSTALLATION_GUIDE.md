# AuraMatch AI — Installation & Setup Guide

This guide covers everything needed to install, configure, and run **AuraMatch AI** — from a one-command Docker Compose boot to a fully local, non-containerized development setup. It also covers optional LLM configuration, API key issuance, and troubleshooting.

> **Summary:** `git clone` → `docker compose up --build -d` → open [localhost:3000](http://localhost:3000). No API keys required to use the web application.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Quick Start: Running with Docker](#2-quick-start-running-with-docker-recommended)
3. [Accessing the Application](#3-accessing-the-application)
4. [Configuring Environment Variables (Optional)](#4-configuring-environment-variables-optional)
5. [Issuing API Keys for Swagger / API Testing](#5-issuing-api-keys-for-swagger--api-testing)
6. [Local Developer Setup (Non-Containerized)](#6-local-developer-setup-non-containerized)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. Prerequisites

Before starting, ensure the following tools are installed on your host system:

| Dependency | Minimum Version | Required For |
| :--- | :--- | :--- |
| **Docker** | 20.10.0+ | Containerized execution |
| **Docker Compose** | 2.10.0+ | Container orchestration |
| **Git** | 2.30.0+ | Repository cloning |
| **Python** | 3.11+ | *Optional* — local (non-Docker) backend development & testing |
| **Node.js** | 18.0.0+ | *Optional* — local (non-Docker) frontend development & testing |

---

## 2. Quick Start: Running with Docker (Recommended)

AuraMatch AI is pre-configured to run out of the box with Docker Compose. Every component — frontend, backend, and database — runs in its own isolated container, connected over a shared bridge network.

### Step 1 — Clone the Repository

```bash
git clone https://github.com/shriyashsawant/JTP-PROJECT-ROUND.git
cd JTP-PROJECT-ROUND
```

### Step 2 — Spin Up the Containers

```bash
docker compose up --build -d
```

### Step 3 — First-Boot Seeding

* **First boot restores ~40,000+ rows of scent data.** On first start, the database container automatically runs `backend/data/01_schema.sql`, then unzips and loads the seed set from `backend/data/02_seed_data.sql.gz`.
* **Seeding duration:** typically **2–5 minutes**, depending on disk speed. Subsequent starts are instant — the data persists in a Docker volume (`pgvector_data`).
* **Health check:** the backend container waits for the database to report **healthy** before it starts serving requests, so there is no race condition to worry about.

---

## 3. Accessing the Application

Once the containers are up and healthy, the system is available at:

| Interface | URL | Notes |
| :--- | :--- | :--- |
| **Web UI (Frontend)** | [localhost:3000](http://localhost:3000) | Vibe Check chat, Dupe Finder, and fragrance detail cards. No API key needed — a publishable key is pre-configured. |
| **API Reference (Swagger)** | [localhost:8000/docs](http://localhost:8000/docs) | Interactive endpoint testing. Requires an `X-API-Key` header for search/match endpoints — see [Section 5](#5-issuing-api-keys-for-swagger--api-testing). |
| **Prometheus Metrics** | [localhost:8000/metrics](http://localhost:8000/metrics) | HTTP latency, DB connection pool stats, circuit-breaker state, and rate-limit rejections. |

---

## 4. Configuring Environment Variables (Optional)

AuraMatch AI runs fully offline by default, generating vector embeddings locally with `BAAI/bge-small-en-v1.5`. You can optionally enable **Groq LLM re-ranking** to get natural-language explanations alongside matches:

1. Create a `.env` file at the project root:
   ```bash
   # In JTP-PROJECT-ROUND/
   touch .env
   ```
2. Add your Groq API key:
   ```env
   GROQ_API_KEY=gsk_your_actual_groq_api_key_here
   ```
3. Restart the containers to pick up the new configuration:
   ```bash
   docker compose up -d
   ```

> **Note:** this step is entirely optional. If no key is set (or the Groq API is unreachable), the application falls back instantly to deterministic matching — there is no degraded experience for the user.

---

## 5. Issuing API Keys for Swagger / API Testing

To call `/api/v1/search/context`, `/api/v1/search/dupe`, or `/api/v1/perfume/{id}` directly via Swagger or Postman, generate a secret API key first:

* **Via host (Python installed):**
  ```bash
  cd backend
  python scripts/issue_api_key.py --type secret --label "Evaluator API Key" --rate-limit 300
  ```
* **Via Docker container:**
  ```bash
  docker compose exec backend python scripts/issue_api_key.py --type secret --label "Evaluator API Key" --rate-limit 300
  ```

Copy the printed key and pass it in the `X-API-Key` header. See [`THIRD_PARTY_API.md`](THIRD_PARTY_API.md) for the full key model and rate-limit details.

> **Important:** the key is only printed once at creation time and cannot be recovered afterward — copy it somewhere safe immediately.

---

## 6. Local Developer Setup (Non-Containerized)

Prefer running components directly on your host for development or debugging? Follow these steps.

### 6.1 Database Setup

1. Install PostgreSQL 16.
2. Install the `pgvector` extension.
3. Create a database named `auramatch` and a user with write privileges.
4. Run `backend/data/01_schema.sql` to initialize the tables.

### 6.2 Backend Setup

```bash
cd backend
```

Create and activate a virtual environment:

```bash
python -m venv .venv
# Windows (CMD/PowerShell):
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Copy `.env.example` to `.env` and set your database URL:

```env
DATABASE_URL=postgresql://<user>:<password>@localhost:5432/auramatch
```

Apply migrations and start the server:

```bash
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### 6.3 Frontend Setup

```bash
cd ../frontend
npm install
```

Create a `.env.local` file:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_KEY=pk_live_f3o8eLGSmio2iWVDzyG25ppqPVz0sCMy_5vUh6cAtZ8
```

Start the development server:

```bash
npm run dev
```

---

## 7. Troubleshooting

| Symptom | Cause & Fix |
| :--- | :--- |
| **Port 3000 or 8000 already in use** | Another local process is bound to that port. Remap the host port in `docker-compose.yml` (e.g. `"3001:80"` for the frontend). |
| **Database connection fails** | The database container may still be initializing or seeding. Tail its logs: `docker compose logs db` |
| **Vector embeddings feel slow on the first query** | The `BAAI/bge-small-en-v1.5` transformer model is loading into memory (a one-time ~2–3 second delay). Every query after that is fast. |
| **Need to reset the database from scratch** | Run `docker compose down -v` then `docker compose up --build -d` — this drops the volume and re-seeds from a clean state. |

> **Caution:** `docker compose down -v` permanently deletes the seeded database volume. Only use it when you actually intend to start over.
