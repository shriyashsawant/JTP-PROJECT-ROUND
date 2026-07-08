# AuraMatch AI — User Manual

Welcome to **AuraMatch AI**, an olfactory matching and fragrance recommendation platform. This manual explains how to use the web application, interpret fragrance metrics, navigate the developer dashboard, and issue API keys.

> **Summary:** describe a scent in plain English in the Vibe Check chat, or ask for a "dupe" of a specific perfume, and AuraMatch returns ranked matches from a database of 40,000+ fragrances with full note pyramids and pricing.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Using the Web Interface](#2-using-the-web-interface)
   - [2.1 Vibe Check (Conversational Matching)](#21-vibe-check-conversational-matching)
   - [2.2 Dupe Engine (Budget Alternatives)](#22-dupe-engine-budget-alternatives)
   - [2.3 Reading Scent Detail Cards](#23-reading-scent-detail-cards)
3. [Developer Metrics & Admin Dashboard](#3-developer-metrics--admin-dashboard)
4. [Using the REST API Directly](#4-using-the-rest-api-directly)
5. [Sample Queries & Scenarios](#5-sample-queries--scenarios)

---

## 1. Introduction

AuraMatch AI addresses the difficulty of finding the right perfume by replacing standard keyword search with **semantic vector search** combined with a **deterministic olfactory decision engine**.

Instead of searching by tag lists, users describe a vibe or a scent memory in natural language. The system matches that query against a database of 40,000+ scents, computing a hybrid score from notes, concentration level, gender leaning, and budget constraints.

---

## 2. Using the Web Interface

Open [http://localhost:3000](http://localhost:3000) in a browser. The AuraMatch home page is the entry point into the discovery engine.

### 2.1 Vibe Check (Conversational Matching)

Click **Start Chatting**, or navigate to the **Chat** tab in the navbar.

**Initial query** — enter a vibe in plain English. Examples:
* *"I want a fresh, citrusy perfume for office commute that lasts all day"*
* *"A dark, cozy woody fragrance for winter nights"*

**Conversational clarification** — the system tracks conversation history, so you can refine your search with follow-up messages at any point:
* *"Can you make it more masculine?"*
* *"Show me only options under ₹4,000."*
* *"Add some leather or tobacco notes."*

**Interactive controls** — sliders and dropdowns in the sidebar/search bar let you adjust:

| Control | Purpose |
| :--- | :--- |
| **Budget Limit** | Maximum price in INR (₹) |
| **Gender Bias** | Unisex leaning, leaning masculine, leaning feminine |
| **Concentration Level** | EDT, EDP, Extrait, Cologne, etc. |
| **Longevity & Sillage Weights** | Prioritize scents that last longer or project further |

### 2.2 Dupe Engine (Budget Alternatives)

If you love a high-end designer or luxury perfume but want an affordable alternative, AuraMatch has a dedicated **Dupe Engine**.

**How to trigger** — ask for a dupe directly in the Chat interface:
* *"Show me affordable alternatives to Creed Aventus under ₹5000"*
* *"Suggest a dupe for Chanel No. 5"*

**How it works** — the system looks up the original luxury perfume, extracts its exact scent profile, main accords, and notes pyramid, then runs a nearest-neighbor vector search to surface matches with a similar smell profile at a fraction of the price.

### 2.3 Reading Scent Detail Cards

Each search result is displayed as a card containing:

| Element | Description |
| :--- | :--- |
| **Fragrance Name & Brand** | The designer or perfume house |
| **Price (INR)** | Calculated using standardized pricing rules |
| **Main Accords** | Badges indicating dominant scent notes (e.g. Citrus, Woody, Vanilla, Leather) |
| **Longevity & Sillage** | Derived from chemical note volatility — *Longevity* is how long the scent lasts on skin (e.g. "8.5 / 10 hours"); *Sillage* is how far it projects (e.g. "Strong", "Intimate") |
| **Notes Pyramid** | Interactive breakdown — **Top notes** (sensed immediately, volatile citruses/herbs), **Heart notes** (the main character — flowers, fruits, spices), **Base notes** (the dry-down — musks, woods, resins, amber) |
| **AI-Generated Explanation** | If Groq LLM re-ranking is enabled, a short explanation of *why* this fragrance matches the query |

---

## 3. Developer Metrics & Admin Dashboard

AuraMatch includes built-in real-time monitoring, available at the **Developer Metrics Dashboard**: [http://localhost:3000/admin](http://localhost:3000/admin).

The dashboard reads directly from the backend's Prometheus `/metrics` endpoint:

| Metric | What It Shows |
| :--- | :--- |
| **Circuit Breaker State** | Status of the Groq API connection — `CLOSED` (working), `OPEN` (failed over to offline mode), `HALF-OPEN` (testing recovery) |
| **Rate Limit Rejections** | Requests rejected by the token-bucket rate limiter |
| **Average Latency** | Average response time in milliseconds |
| **Route Breakdown** | Request counts and response status codes per API route |

---

## 4. Using the REST API Directly

Developers integrating AuraMatch AI with external tools can use the fully documented REST API. See [http://localhost:8000/docs](http://localhost:8000/docs) for the interactive Swagger schema.

### Core Endpoints

| Endpoint | Description |
| :--- | :--- |
| `POST /api/v1/search/context` | Evaluates a query string and returns matched scents with explanation scores |
| `POST /api/v1/search/dupe` | Given a perfume ID and target budget, returns cheaper alternatives |
| `GET /api/v1/perfume/{id}` | Returns complete metadata, description, pricing, and note structures for a single perfume |

### Authenticating Requests

With the exception of `/api/v1/health`, every endpoint requires an `X-API-Key` header.

Generate a key:

```bash
docker compose exec backend python scripts/issue_api_key.py --type secret --label "My Client"
```

Add it to your request headers:

```http
X-API-Key: sk_live_your_generated_secret_key
```

---

## 5. Sample Queries & Scenarios

Recommended inputs for exploring AuraMatch AI's matching logic:

| Query Type | Input | What the Decision Engine Evaluates |
| :--- | :--- | :--- |
| **Simple Vibe** | *"Fresh clean laundry smell"* | Matches light aldehydes, musks, and laundry-clean accords |
| **Occasion-Based** | *"Seductive date night fragrance"* | Prioritizes amber, vanilla, spices, and heavier base notes with higher sillage |
| **Negative Search** | *"Fresh woody scent without any rose or patchouli"* | Detects "without" and applies a negative penalty filter, removing candidates containing rose or patchouli notes |
| **Weather/Season** | *"Crisp summer scent"* | Boosts citruses, marine notes, and mint; filters out heavy winter notes |
| **Dupe Request** | *"Dupes for Tom Ford Tobacco Vanille under ₹3000"* | Finds perfumes matching Tom Ford's profile (tobacco, cacao, spices, vanilla) within the ₹3000 limit |
