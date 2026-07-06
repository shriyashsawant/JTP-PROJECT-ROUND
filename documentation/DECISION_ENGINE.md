# AuraMatch AI - Decision & Scoring Engine Guide

This document details the mathematical models, scoring algorithms, intent boundaries, and olfactory chemistry models implemented within AuraMatch AI's recommendation engine.

---

## 1. Algorithmic Overview and Design Philosophy

The AuraMatch AI recommendation engine is built on a hybrid deterministic model. Rather than relying on unstructured generative AI calls to rank products (which introduces high latency, cost, and hallucination risks), the system performs vector similarity searching at the database tier and uses a strict Python logic layer to calculate matching scores. This ensures that every recommendation is accurate, explainable, and reproducible.

The decision engine resides primarily in `backend/app/services/decision_engine.py` and relies on metadata classifications defined in `backend/app/services/scenario_map.py`.

---

## 2. The Hybrid Scoring Formula

The matching engine scores every candidate on up to ten dimensions (similarity, note match, price, gender, longevity, scenario, projection, age, note family, chemical bridge). Only two of these - vector similarity and note match - are *always* weighted; the other eight are weighted **only when the query actually signals that preference** (a budget was given, a gender was stated, longevity was requested, etc.). Both the numerator and the denominator drop a term together when it's inactive - this is the load-bearing detail, not a minor implementation note.

### 2.1 Mathematical Formulation

```
Final Score = ( sim·w_sim + note_match·w_note
              + [price_fit·w_price]        (only if a budget was given)
              + [gender_fit·w_gender]      (only if a gender was stated)
              + [longevity_fit·w_longevity] (only if longevity was requested)
              + [scenario_fit·w_scenario]   (only if an occasion was signalled)
              + [projection_fit·w_projection] (only if a sillage preference was given)
              + [age_fit·w_age]            (only if an age was given)
              + [note_family_fit·w_family] (only if a scent family was picked)
              + [bridge_fit·w_bridge]      (only if fresh+long-lasting both apply)
              ) / ( w_sim + w_note + sum of the active bracketed weights )
              × 100, rounded to 1 decimal place
```

### 2.2 Real Weight Constants (`decision_engine.py`)

| Signal | Constant | Weight | Always active? |
| :--- | :--- | ---: | :--- |
| Scenario/occasion fit | `SCENARIO_WEIGHT` | **0.28** | No |
| Note match | `NOTE_MATCH_WEIGHT` | **0.20** | **Yes** |
| Longevity fit | `LONGEVITY_WEIGHT` | **0.20** | No |
| Note family fit | `NOTE_FAMILY_WEIGHT` | **0.15** | No |
| Chemical bridge fit | `BRIDGE_WEIGHT` | **0.15** | No |
| Projection (sillage) fit | `PROJECTION_WEIGHT` | **0.10** | No |
| Vector similarity | `SIM_WEIGHT` | **0.07** | **Yes** |
| Price fit | `PRICE_WEIGHT` | **0.05** | No |
| Gender fit | `GENDER_WEIGHT` | **0.05** | No |
| Age fit | `AGE_WEIGHT` | **0.05** | No |

**The scenario/occasion signal carries the most weight (0.28), not raw vector similarity (0.07).** This is deliberate: two perfumes can have similar embeddings just from sharing generic brand/description text, but whether one is actually right for "gym, sweat, hot weather" is a much stronger, more specific correctness signal than embedding proximity alone - so it's weighted roughly 4x higher. Note match (0.20) sits second because a user naming specific ingredients ("something with oud and rose") is about as strong and unambiguous a signal as an explicit occasion.

### 2.3 Why the Denominator Also Changes (the "73% floor" bug)

Before this normalization existed, every one of the eight optional `*_fit` terms defaulted to a neutral `1.0` when unsignalled, and the denominator was always the full fixed sum of *all ten* weights - so a query with zero occasion/longevity/projection/gender/age/price intent still scored a flat **73%** (the combined weight of those six always-neutral terms) before a single real note or similarity point was ever added. Every unrelated result clustered into a narrow 73%-100% band regardless of actual match quality, making the score meaningless as a ranking signal for plain-language queries that don't specify every filter.

The fix: both the numerator *and* the denominator only include a term when the corresponding intent was actually detected in the query. A bare "fresh citrus scent" (no budget, gender, longevity, occasion, age, or scent-family signal) is scored purely on `sim` and `note_match` against a denominator of `0.07 + 0.20 = 0.27` - restoring full 0%-100% contrast instead of a floor.

### 2.4 Worked Example

Query: *"fresh scent for the gym that lasts 12 hours"* → detected: `scenario=gym` (has_scenario), `hours_required=12` (has_longevity). No budget, gender, age, or scent-family signal.

`gym` is in `FRESH_SCENARIOS` and 12h ≥ 6h, so `wants_fresh` and `wants_strong_longevity` are both true - `has_bridge` also activates here (see §3.4): this exact phrasing is precisely the "fresh top + long-lasting base" contradiction the bridge-fit dimension exists to resolve, so its weight is *not* a coincidental omission from this example - it belongs.

Active weights: `sim (0.07) + note (0.20) + scenario (0.28) + longevity (0.20) + bridge (0.15)` = denominator `0.90`.

For a candidate with `cosine_similarity=0.62`, `note_match=0.80`, `scenario_fit=1.0` (tagged for "gym"), `longevity_fit=1.0` (estimated wear ≥ 12h), `bridge_fit=1.0` (has a genuine fresh top + dense musk/woody base):

```
Final Score = (0.62·0.07 + 0.80·0.20 + 1.0·0.28 + 1.0·0.20 + 1.0·0.15) / 0.90 × 100
            = (0.0434 + 0.16 + 0.28 + 0.20 + 0.15) / 0.90 × 100
            = 0.8334 / 0.90 × 100 = 92.6%
```

Gender/price/age/note-family terms never entered the calculation at all - not "counted as neutral," genuinely absent from both sides of the division. (A perfume that satisfies "fresh" or "12 hours" alone but not both together would score `bridge_fit=0.5`; one that satisfies neither scores `0.2` - see §3.4.)

---

## 3. Olfactory Match Dimensions

### 3.1 Note Matching and Similarity (`_match_notes` & `_match_accords`)
Direct note matching compares the query terms against a perfume's ingredients and accords list.
*   **Whole-Word Containment (`_notes_equivalent`)**: To prevent false-positive matches (e.g. matching "Musk" inside "Musky", or "Rose" inside "Roseview"), the engine performs bounded whole-word matching using regular expressions (`\bterm\b`).
*   **Fuzzy Set Overlap (`_fuzzy_overlap_count`)**: Note names in databases are often highly specific (e.g. "Sicilian Lemon", "Calabrian Bergamot"). The engine matches these against scenario vocabularies (e.g. "lemon", "bergamot") by evaluating if the database term contains the scenario term as a whole-word component, rather than requiring exact string equality.

### 3.2 Negation Parsing and SQL Pushdown Filtering
A major failure mode in search engines is the parsing of compound sentences (e.g., *"no vanilla, I want musk"*). 
*   **Clause Splitting**: The parser in `intent_detector.py` uses clause-boundary detection, splitting strings at punctuation (`[,.;!?]`) and pronouns/conjunctions (` I `, ` but `, ` and `) before extracting negated terms. This isolates the negation context to its specific clause.
*   **Exclusion Execution**: Once negated terms are extracted, they are passed as a regex array to Postgres, which filters candidates out of the ANN pool:
    ```sql
    AND NOT (notes ~* ANY($6) OR main_accords ~* ANY($6))
    ```
*   **Fallback Penalty**: If a record somehow bypasses the database filter but contains trace elements of a negated note, `_negation_penalty()` applies a strict $0.25$ multiplier penalty in Python.

### 3.3 Longevity and Sillage Fits (`_longevity_fit` & `_projection_fit`)
*   **Longevity Fit**: A no-op (`1.0`) unless longevity was signalled at all. A soft "long lasting" phrase (no specific hour count) scales proportionally with the raw longevity score (`score / 100`). An explicit "N+ hours" requirement is a real threshold: the raw score is converted to an estimated wear time (`estimate_hours_numeric`); meeting or exceeding the requirement scores `1.0`, falling short scores `estimated / hours_required` **floored at `0.2`, never `0.0`** - a perfume that falls short of "12 hours" by an hour still ranks above one that falls short by ten, rather than both being equally zeroed out.
*   **Sillage Fit**: A no-op unless a projection preference (light/moderate/strong) was given; otherwise compares it against the database sillage rating (0-100) and penalizes mismatches (e.g., recommending a room-filling scent to someone who asked for a light skin scent).

### 3.4 Chemical Bridge Fit (`_bridge_fit`)
Queries requesting a fresh profile (gym, summer, citrus) that also lasts 8-12 hours present a physical contradiction. Fresh citrus molecules evaporate quickly, while long-lasting woody/musk molecules can be cloying in hot environments.
*   **The Bridge Model**: The engine rewards perfumes that feature a volatile fresh top note (citrus, mint, aquatic) AND a dense, persistent base note (musk, ambroxan, cedar, vetiver) to bridge the gap.
*   **Accord-Level Fallback**: If detail note data is missing, the engine evaluates the perfume's `main_accords` (e.g. checking if it features both "citrus" and "woody" accords). If a bridge exists, a `1.0` fit is returned; if missing, it is penalized.

### 3.5 Concentration Performance Adjuster (`_adjust_performance_by_type`, `TYPE_PERFORMANCE_ADJUSTMENTS`)
The raw `type` column from seeding is always `NULL` - concentration is parsed from the perfume's own name (e.g. "Bleu de Chanel EDP" → `_parse_concentration_type` → `"Eau de Parfum"`) into exactly one of the 7 keys below, or `None`. Each is an exact-match lookup (`(longevity_multiplier, sillage_multiplier)`), not a substring check:

| Concentration | Longevity × | Sillage × |
| :--- | ---: | ---: |
| Extrait de Parfum / Parfum / Elixir | `1.15` | `0.85` |
| **Eau de Parfum (EDP)** | **`1.08`** | **`0.93`** |
| Eau de Toilette (EDT) | `0.90` | `1.10` |
| Eau de Cologne (EDC) | `0.75` | `1.15` |
| Body Spray | `0.50` | `0.70` |

**Why Eau de Parfum has its own tier, distinct from Extrait/Parfum**: an earlier version used a substring check (`"parfum" in type_string`), which matched "Eau de Parfum" (15-20% concentration) and gave it the *exact same* ±15% adjustment as true Extrait/Parfum (20-40% concentration) - conflating two formulation strengths that are meaningfully different, not just a `==` vs `in` typo. EDP now sits at a distinct, smaller `1.08`/`0.93` adjustment strictly between Extrait (`1.15`/`0.85`) and EDT (`0.90`/`1.10`), reflecting its real place in the concentration spectrum. An unrecognized or absent type string returns the longevity/sillage scores unadjusted.

### 3.6 Unisex Gender Leaning Scorer (`_gender_leaning_modifier`)
Unisex perfumes match both male and female requests. However, some unisex perfumes lean strongly masculine or feminine based on their note profile.
*   **Note Profile Assessment**: The engine counts masculine notes (wood, leather, tobacco, pepper) and feminine notes (floral, sweet, vanilla, fruits).
*   **Modifier Application**: If a user requests a male scent, and the matching unisex perfume has a clear feminine note bias (feminine count > masculine count + 1), it applies a `0.85` modifier.
*   **Display Integration**: The match checklist marks the gender criterion as a **"partial"** match instead of "met" or "missed".

---

## 4. Scope of Olfactory Scaling and Future Expansion

The decision engine is structured to support future olfactory matching enhancements:
*   **Skin Chemistry Modifiers**: The engine can be expanded to scale longevity and sillage fits based on the user's skin profile (e.g. dry skin absorbs oils faster, reducing sillage, which would require a sillage boost for heavy EDPs).
*   **Ambient Weather Modifiers**: Integrating real-time weather APIs to scale scenario fits (e.g., boosting fresh, high-volatility citruses during hot, humid summer days and demoting heavy, cloying orientals).
