# AuraMatch AI - Frontend Architecture Guide

This document covers the Next.js web application: page layout, state management, API integration, and the UI-specific engineering decisions that aren't visible from the backend documentation alone.

---

## 1. Tech Stack

| Layer | Choice | Version |
| :--- | :--- | :--- |
| Framework | Next.js, App Router | 16.2.9 |
| Language | TypeScript | 5.x |
| UI runtime | React | 19.2.4 |
| Styling | Tailwind CSS | 4.x |
| Components | shadcn/ui (on `@base-ui/react` primitives) | - |
| Motion | Framer Motion | 12.x |
| Icons | lucide-react | - |
| Fonts | Geist Sans/Mono (body/code), Playfair Display (headings) | via `next/font/google` |

No state management library, no data-fetching library (React Query, SWR, etc.) - the app is small enough that plain `useState`/`useEffect` plus a thin `fetch` wrapper (`src/lib/api.ts`) covers every page without adding a dependency that isn't earning its keep yet.

---

## 2. Pages & Routing

| Route | Purpose |
| :--- | :--- |
| `/` | Landing page - hero + two entry points into the two search modes |
| `/search` | **Vibe Check** - free-text query + optional structured filters (gender, age, occasion, scent family, skin type, longevity, projection, budget) |
| `/dupe` | **Dupe Engine** - name a perfume, get budget-capped alternatives scored against its real composition |
| `/perfume/[id]` | Full perfume detail: scent pyramid, accords, longevity/sillage bars, perfumer, Fragrantica link |
| `/about` | Project summary, tech stack, data sources, how the matching actually works |

`Navbar`/`Footer` are mounted once in `src/app/layout.tsx` (shared root layout), so every route gets consistent chrome without each page re-implementing it.

---

## 3. State Management: Why sessionStorage, Not a Global Store

Both `/search` and `/dupe` persist their entire form + results state to `sessionStorage` on every change (`STORAGE_KEY` constants in each page) and restore it on mount:

```ts
useEffect(() => {
  const raw = sessionStorage.getItem(STORAGE_KEY);
  if (raw) { /* restore query, filters, results */ }
}, []);
```

**Why this exists**: clicking into a result (`/perfume/[id]`) and hitting back used to always land on a blank form - a real regression fixed earlier in this project's history ("Fix frontend state loss on navigation"). Since neither page uses a global store (Redux/Zustand/Context) and Next.js App Router doesn't persist client component state across a full route unmount by default, `sessionStorage` is the simplest fix that doesn't require introducing state-management infrastructure for two pages. It's session-scoped (not `localStorage`) deliberately - a stale search shouldn't survive into the user's next visit days later.

The Dupe Engine page also reads a `?name=` query param on mount (set by the "Find Dupes for this" button on the perfume detail page) and lets it override any restored session state - a fresh, explicit navigation intent should win over old form state.

---

## 4. Client-Side Sort: A Safety Net, Not the Source of Truth

Both search pages re-sort whatever the API returns before rendering:

```ts
function sortResults(perfumes: Perfume[], budget: number | undefined, dealBreaker: boolean): Perfume[] {
  if (!budget) return sorted.sort((a, b) => (b.match_score ?? 0) - (a.match_score ?? 0));
  sorted.sort((a, b) => {
    const pa = a.price_inr ?? (dealBreaker ? Infinity : 0);
    const pb = b.price_inr ?? (dealBreaker ? Infinity : 0);
    if (pa !== pb) return dealBreaker ? pa - pb : pb - pa;
    return (b.match_score ?? 0) - (a.match_score ?? 0);
  });
  return sorted;
}
```

This deliberately mirrors `decision_engine.apply_price_order` on the backend (nearest-to-budget by default, cheapest-first in "Deal Breaker" mode, pure match-quality with no budget). It is **not** the primary sort - the backend already computes and re-asserts this same order (including after the optional LLM layer reorders its own top picks by relevance, which would otherwise silently discard the price-order guarantee). Keeping the identical rule client-side is cheap insurance against ever surfacing to the user, not a substitute for backend correctness - see [DECISION_ENGINE.md](file:///c:/Users/SHRIYASH%20SAWANT/OneDrive/Desktop/JTP-PROJECT%20ROUND/documentation/DECISION_ENGINE.md) for the authoritative ordering logic.

---

## 5. API Integration (`src/lib/api.ts`)

A single typed `fetchAPI<T>()` wrapper backs every call (`searchByContext`, `searchByDupe`, `getPerfumeById`, `checkHealth`). Two things worth calling out:

**`ClarificationNeededError`**: the backend returns `422` with a structured body (`{"needs_clarification": true, "field": "budget", "message": "..."}`) when a dupe-style query names a reference perfume it can't resolve and has no budget to fall back on. Rather than surfacing this as a generic error, `fetchAPI` throws a typed `ClarificationNeededError` carrying the `field`, so the search page can highlight the exact input that needs attention (see the `needsBudget` state and the ring-highlighted budget slider in `/search`) instead of a plain red error banner.

**`X-API-Key` header**: every request carries a publishable API key (`NEXT_PUBLIC_API_KEY`, baked in at Docker build time - see [THIRD_PARTY_API.md](file:///c:/Users/SHRIYASH%20SAWANT/OneDrive/Desktop/JTP-PROJECT%20ROUND/documentation/THIRD_PARTY_API.md)). This key is intentionally safe to ship in client-side JS: it's restricted server-side by an `Origin` allowlist tied to this frontend's own deployed origin, not a secret. The frontend needed zero architectural change to adopt this (no server-side proxy) precisely because of that two-tier key design.

---

## 6. Result Cards & Detail Page

**`PerfumeCard`** (used by both search result grids) converts the backend's 0-100 `match_score` into a 5-star display (`Math.round(match_score / 20)`) alongside the raw percentage and a progress bar - redundant on purpose, since a star rating scans faster in a grid while the percentage gives the precise number for anyone who wants it. It also renders the backend's `match_breakdown` (a list of `{label, status: "met"|"partial"|"unmet"}` entries) as a small checklist, so a result's score isn't a black box - a user can see *why* something scored the way it did (e.g. "Occasion: Summer, Daily Wear - met", "Scent profile match - partial").

**Scent Pyramid** (perfume detail page) renders `top_notes`/`heart_notes`/`base_notes` with increasing visual weight down the pyramid (lighter/smaller badges for top notes, filled/bordered badges for base notes) to visually mirror increasing density/persistence - falling back to a flat `notes` list only if no tiered data exists at all for that perfume (see `db_repository._resolve_pyramid` in [DECISION_ENGINE.md](file:///c:/Users/SHRIYASH%20SAWANT/OneDrive/Desktop/JTP-PROJECT%20ROUND/documentation/DECISION_ENGINE.md) for how that fallback is populated server-side).

**Image handling**: both the card thumbnail and the detail hero use an `onError` handler that flips a local `failed` state to fall back to a monogram (brand + perfume initials) rather than a broken-image icon - most rows in the ~40K-perfume catalog don't have a real `image_url`, so this is the common case, not an edge case.

---

## 7. Responsive Behavior

Single breakpoint strategy (`md:` = 768px) throughout: the navbar collapses to a hamburger menu below it, result grids go from 1 column to 2 (`sm:`) to 3 (`lg:`) columns as width increases, and the perfume detail hero stacks vertically on narrow viewports (`flex-col sm:flex-row`). No separate mobile-specific components - the same JSX reflows via Tailwind's responsive utility classes.
