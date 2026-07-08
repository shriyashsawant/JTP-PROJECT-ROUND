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
| `/` | Landing page - hero + entry point into the search experience |
| `/search` | The single search surface - a conversational chat interface; free-text or guided through up to 9 clarifying questions (gender, occasion, scent, notes to avoid, longevity, projection, budget, age, skin type). Handles both "vibe" queries and dupe/reference queries ("cheaper alternative to X") through the same input - see §4 |
| `/dupe` | **Redirect only, not a real page.** The Dupe Engine used to be a separate form; it's now folded into `/search` (the backend's `detect_dupe_intent`/`find_reference_perfume` already understand "cheaper alternative to X" phrasing within the same endpoint the chat calls). Nothing in the current app links here anymore - the perfume detail page's "Find Dupes" button goes straight to `/search?prefill=...` - this route exists solely so old external links/bookmarks in the previous `/dupe?name=X` shape still resolve to something, by reading `?name=` and replacing itself with `/search?prefill=cheaper alternative to X` |
| `/perfume/[id]` | Full perfume detail: scent pyramid, accords, longevity/sillage bars, perfumer, external reference link |
| `/about` | Project summary, tech stack, data sources, how the matching actually works |
| `/admin` | Ops metrics dashboard - parses the `/metrics` Prometheus text export into request/latency/error summaries. Deliberately not in the `Navbar` link list (reachable only by direct URL) - it's an operational surface, not a user-facing feature; see [TESTING_AND_OBSERVABILITY.md §5](TESTING_AND_OBSERVABILITY.md) |

`Navbar`/`Footer` are mounted once in `src/app/layout.tsx` (shared root layout), so every route gets consistent chrome without each page re-implementing it.

---

## 3. State Management: `localStorage`, Multiple Saved Conversations

`/search` persists to `localStorage`, not `sessionStorage` - a deliberate, later change from this project's earlier history (an earlier revision of this doc described a single-conversation `sessionStorage` model; that no longer exists anywhere in the codebase). Two keys back it:

```ts
const CONVERSATIONS_KEY = "auramatch_conversations";   // every saved chat, not just the latest
const ACTIVE_ID_KEY = "auramatch_active_conversation_id";
const MAX_SAVED_CONVERSATIONS = 30;
```

**Why `localStorage`, not `sessionStorage`**: a saved chat is meant to survive a closed tab or browser, not just a back-navigation within one session - the "Chats" history panel lets a user return to an old conversation days later, which `sessionStorage` (cleared when the tab closes) can't support at all. **Why every conversation is stored, not just one**: starting a new chat must never silently discard an old one - it just stops being the active thread. The oldest conversations beyond `MAX_SAVED_CONVERSATIONS` (30, sorted by last-updated) are trimmed on save.

`/dupe`'s redirect (see §2) is the only other place client state briefly matters - it reads a `?name=` query param once, translates it to a `?prefill=` on `/search`, and renders nothing itself.

---

## 4. The Conversational Clarification Flow (`/search`)

`/search` is a chat interface, not a form: a message list (`ChatMessage[]`), a free-text input, and quick-reply chips that change based on whichever question was just asked. Two cooperating mechanisms decide, on every user message, whether to ask another clarifying question or run a real search.

### 4.1 Extracting What's Already Been Said (`extractPreferences`)

Rather than a multi-step wizard with explicit "next" buttons, the app tries to read structured preferences (gender, occasion, scent family, budget) straight out of free-text - a user who opens with *"fresh citrus scent for the gym, under ₹3,000"* should never be asked about scent family or budget again, even though they never clicked a single quick-reply chip. Each preference has its own small regex (shared, not duplicated per-call-site - see `MALE_WORDS`/`FEMALE_WORDS`/`UNISEX_WORDS` and `OCCASION_RE`/`SCENT_RE`/`BUDGET_RE`), and this vocabulary is deliberately kept in sync with the backend's own `scenario_map.py` gender hints so the frontend's off-topic detector and the backend's actual gender detection never disagree on the same word.

### 4.2 Asking What's Missing (`buildClarifyingQuestion`, `wasAsked`)

For the 4 original questions (gender/occasion/scent/budget), "already answered" means `extractPreferences` found a real signal. For the 5 newer ones (notes to avoid, longevity, projection, age, skin type), there's no reliable "positive content" pattern to regex-match - a "let AuraMatch decide" answer has no keyword to detect - so completion is tracked structurally instead: `wasAsked(messages, type)` checks whether a clarifying question of that `type` already appears anywhere in the active conversation, and *any* reply (including an explicit skip) counts as having answered it. Questions are asked in scoring-weight order (occasion and longevity before budget/age/skin-type), not the order they were originally added.

### 4.3 The Reset Boundary (`getActiveMessages`)

A search that returns zero results doesn't dead-end - the assistant sends a "couldn't find any... let's restart" message and the clarification flow starts over. But "starts over" only works if `wasAsked`/`extractPreferences` stop looking at the *entire* conversation history and scope to messages since that restart - otherwise a stale answer from before the reset (or a stale "already asked" flag) permanently blocks the flow from ever re-collecting anything, silently degrading every restart into a single-message search built from whatever the user happened to type next. `getActiveMessages(messages)` is the one shared boundary-finder (locates the last "couldn't find any" message and slices from there) that both mechanisms - and the query-building logic in `sendMessage` - are built on, specifically so the Q&A intake and the actual search agree on where the "current attempt" begins. This one function used to be three separately-maintained copies of the same slice logic; a real, shipped bug (the unscoped copy silently breaking every restart) is why it no longer is.

### 4.4 Building the Actual Query

The first real search after intake uses *every* answer given in the active segment (not a small sliding window) - a `CONTEXT_WINDOW`-sized tail of just the last few messages is only correct once real results have already been shown and the user is doing turn-by-turn refinement ("cheaper please", "actually more woody"), where letting an old superseded preference age out is exactly the point.

---

## 5. Result Ordering: No Client-Side Re-Sort

`/search` renders whatever order the API returns, unmodified - there is no client-side re-sort of perfume results anywhere in the frontend (an earlier revision of this project did keep a client-side mirror of the backend's price-ordering rule as a defensive safety net; it was removed once the chat rewrite landed, since the redundant copy of that logic was one more place the two could quietly drift apart). Result order is entirely the backend's responsibility - `decision_engine.apply_price_order` (nearest-to-budget by default, cheapest-first in "Deal Breaker" mode, pure match-quality with no budget), re-asserted as the final step even after the optional LLM layer reorders its own top picks by relevance - see [DECISION_ENGINE.md](DECISION_ENGINE.md) for the authoritative ordering logic. The only `.sort()` calls left in `search/page.tsx` order the saved-conversations list by `updatedAt`, unrelated to perfume results.

---

## 6. API Integration (`src/lib/api.ts`)

A single typed `fetchAPI<T>()` wrapper backs every call (`searchByContext`, `searchByDupe`, `getPerfumeById`, `checkHealth`, `getMetrics`). `/search` only ever calls `searchByContext` - dupe-style queries ("cheaper alternative to X") are detected server-side (`detect_dupe_intent`) within that same endpoint, so there's no separate client call for it anymore. `searchByDupe` is unused by the UI today; it's kept because `POST /api/v1/search/dupe` is still a real, documented endpoint for third-party API integrators (see [THIRD_PARTY_API.md](THIRD_PARTY_API.md)), and the typed client function stays a correct, ready-to-use reference for it.

**`ClarificationNeededError`**: the backend returns `422` with a structured body (`{"needs_clarification": true, "field": "budget", "message": "..."}`) when a dupe-style query names a reference perfume it can't resolve and has no budget to fall back on. `fetchAPI` throws a typed `ClarificationNeededError` rather than a generic one; the chat UI catches it like any other request failure and shows `err.message` as an assistant message bubble (`isError: true`) - there's no separate form-field-highlighting path now that `/search` is a chat interface, not a form.

**`X-API-Key` header**: every request carries a publishable API key (`NEXT_PUBLIC_API_KEY`, baked in at Docker build time - see [THIRD_PARTY_API.md](THIRD_PARTY_API.md)). This key is intentionally safe to ship in client-side JS: it's restricted server-side by an `Origin` allowlist tied to this frontend's own deployed origin, not a secret. The frontend needed zero architectural change to adopt this (no server-side proxy) precisely because of that two-tier key design.

---

## 7. Result Cards & Detail Page

**`PerfumeCard`** (rendered inline in the chat, one result grid per search turn) converts the backend's 0-100 `match_score` into a 5-star display (`Math.round(match_score / 20)`) alongside the raw percentage and a progress bar - redundant on purpose, since a star rating scans faster in a grid while the percentage gives the precise number for anyone who wants it. It also renders the backend's `match_breakdown` (a list of `{label, status: "met"|"partial"|"unmet"}` entries) as a small checklist, so a result's score isn't a black box - a user can see *why* something scored the way it did (e.g. "Occasion: Summer, Daily Wear - met", "Scent profile match - partial").

**Scent Pyramid** (perfume detail page) renders `top_notes`/`heart_notes`/`base_notes` with increasing visual weight down the pyramid (lighter/smaller badges for top notes, filled/bordered badges for base notes) to visually mirror increasing density/persistence - falling back to a flat `notes` list only if no tiered data exists at all for that perfume (see `db_repository._resolve_pyramid` in [DECISION_ENGINE.md §3.1](DECISION_ENGINE.md) for how that fallback is populated server-side).

**Limited-data notice** (`LimitedDataNotice`, shared by `PerfumeCard` and the detail page): when `has_limited_data` is true - the perfume has no verified notes at all, so its whole pyramid was inferred from accords - both surfaces show a small amber "notes inferred from accords" line instead of presenting an inferred pyramid as verified fact. One shared component, two call sites with their own copy/sizing (a compact one-liner in the grid card, a fuller sentence on the detail page).

**Image handling**: both the card thumbnail and the detail hero use an `onError` handler that flips a local `failed` state to fall back to a monogram (brand + perfume initials) rather than a broken-image icon - most rows in the ~40K-perfume catalog don't have a real `image_url`, so this is the common case, not an edge case.

---

## 8. Responsive Behavior

Single breakpoint strategy (`md:` = 768px) throughout: the navbar collapses to a hamburger menu below it, result grids go from 1 column to 2 (`sm:`) to 3 (`lg:`) columns as width increases, and the perfume detail hero stacks vertically on narrow viewports (`flex-col sm:flex-row`). No separate mobile-specific components - the same JSX reflows via Tailwind's responsive utility classes.
