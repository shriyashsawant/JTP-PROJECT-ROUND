# AuraMatch AI - Third-Party API Integration Guide

This document covers how an external application authenticates against, and integrates with, the AuraMatch AI search API - the auth model, rate limits, error format, and versioning commitment.

---

## 1. Why This Exists

Before this phase, the API had **zero authentication anywhere**. CORS (`main.py`) restricts which *browser* origins may call it, but CORS is a browser-enforced policy only - it does nothing to stop a server-to-server or `curl`/Postman caller. In practice, anyone who found the URL could call it for free, unlimited, forever.

**The constraint that shapes the whole design**: `frontend/src/lib/api.ts` calls this API directly from the browser (`"use client"` components, bundled client JS - there is no Next.js server-side proxy anywhere in the frontend). A secret credential embedded there would be visible to anyone who opens devtools. Rather than add a server-side proxy layer to the frontend (a bigger, riskier change than this integration needed), AuraMatch AI uses the same two-tier key model Stripe, Google Maps, and Mapbox use to solve exactly this problem.

---

## 2. Two Key Types

| | `publishable` | `secret` |
|---|---|---|
| **Safe to embed in browser JS?** | Yes | **No - never** |
| **Restricted by** | `Origin` header allowlist | Nothing (server callers don't reliably send `Origin`) |
| **Intended caller** | The AuraMatch AI web frontend itself, or any first-party browser client | A genuine third-party backend integrating server-to-server |
| **Rate-limit bucket** | `(key, client_ip)` - see §4 | `(key,)` |

Both key types are stored identically: only `sha256(raw_key)` is ever persisted (`api_keys.key_hash`). The raw key is shown **exactly once**, at issuance, and cannot be recovered afterward - only revoked and reissued.

> **Important**: the `Origin` allowlist on a `publishable` key is an *abuse deterrent*, not a real security boundary - a non-browser caller can set any `Origin` header it likes. Its actual purpose is stopping *other websites* from reusing a publishable key scraped out of AuraMatch's own bundled JS in a browser context, the same reasoning behind a Google Maps browser key.

### Requesting a key

There is no self-serve key issuance yet (that's a separate admin/ops phase). An operator issues keys via:

```bash
# Publishable (frontend-safe) key, restricted to one or more origins:
python backend/scripts/issue_api_key.py --type publishable \
    --label "Acme Web App" --origin https://app.acme.example

# Secret (server-to-server) key, no origin restriction:
python backend/scripts/issue_api_key.py --type secret \
    --label "Acme Corp integration" --rate-limit 300
```

The script prints the raw key once. Save it immediately - it is never shown again.

---

## 3. Authenticating a Request

Send the raw key in the `X-API-Key` header on every request:

```bash
curl -X POST https://api.auramatch.example/api/v1/search/context \
  -H "X-API-Key: sk_live_..." \
  -H "Content-Type: application/json" \
  -d '{"query": "fresh citrus scent for the gym", "limit": 5}'
```

Authenticated routes: `POST /api/v1/search/context`, `POST /api/v1/search/dupe`, `GET /api/v1/perfume/{id}`. `GET /api/v1/health` stays open (standard liveness-probe convention - no key required).

### Error responses

| Status | Meaning |
|---|---|
| `401` | Missing `X-API-Key` header, or the key is unknown/revoked |
| `403` | A `publishable` key was used from a non-allowlisted `Origin` |
| `429` | Rate limit exceeded for this key (and, for publishable keys, this client IP) |

All error bodies follow the existing convention: `{"detail": "<message>"}`.

---

## 4. Rate Limiting

Each key has its own `rate_limit_per_minute` (set at issuance, default 60). Enforcement is a **token bucket**: a full minute's worth of requests is allowed as a burst, refilling continuously afterward - not a hard reset every 60 seconds, which would otherwise let a caller burst twice as fast right at a window boundary.

A `publishable` key is shared by every real visitor of whatever frontend embeds it, so its bucket is keyed by `(key, client_ip)` - one scraped-key abuser hammering the endpoint throttles out only themselves, not every legitimate user of that frontend. A `secret` key is one partner, one bucket (`(key,)`) - a partner's IP may legitimately rotate, so it isn't part of the key.

This is enforced in-memory, per backend process (`backend/app/services/rate_limiter.py`) - correct for the current single-process deployment; would need to move to a shared store (Redis) only if the backend ever becomes multi-process/multi-instance.

---

## 5. Versioning Commitment

The current API is `/api/v1` and is considered stable: existing endpoints, request fields, and response shapes will not change in a breaking way under this prefix. Any breaking change (removed/renamed fields, changed status-code semantics, removed endpoints) ships under a new `/api/v2` prefix instead, with `/api/v1` continuing to work unchanged until it is explicitly deprecated and announced.

Full request/response schemas (including optional fields not covered above) are available via FastAPI's auto-generated interactive docs at `/docs`.
