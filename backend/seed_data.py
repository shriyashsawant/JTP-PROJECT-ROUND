"""
AuraMatch AI - Data Seeder (v2)
Merges 4 datasets into PostgreSQL/pgvector with 384-d embeddings.
  - DA_Fragrance_Analysis (38K) — base
  - Fragrantica Perfumes (70K) — volume + accords
  - Fragrantica Cleaned (24K) — structured notes + metadata
  - Nandini (2.2K) — rich descriptions + image URLs

Usage:
  python seed_data.py                    # local Docker pgvector DB
  python seed_data.py --cuda             # local + GPU
  python seed_data.py --max 5000         # limit rows (for testing)
  python seed_data.py --da-only --max 8000   # local CSV only, no Kaggle downloads
"""
import csv, ast, os, sys, math, random, re, argparse
from typing import Optional
from collections import defaultdict

from app.ingestion.contracts import normalize_name

# Priority: scraper_merged (5) > nandini (4) > fra_cleaned (3) > fra_perfumes (2)
# > da_fragrance (1) > indian_brands (0, unlisted -> default). Used both by the
# one-time in-memory batch dedup below (load_all_datasets) and by the
# persisted per-row upsert (seed_local -> app.ingestion.upsert), so a live/
# repeated ingestion run enforces the exact same source-trust ordering a
# single batch run always has.
SOURCE_PRIORITY = {"scraper_merged": 5, "nandini": 4, "fra_cleaned": 3, "fra_perfumes": 2, "da_fragrance": 1}

EMBEDDING_MODEL_VERSION = "all-MiniLM-L6-v2"

# ---------------------------------------------------------------------------
# INR pricing tiers
# ---------------------------------------------------------------------------
INDIAN_LUXURY = {"chanel", "dior", "creed", "tom ford", "louis vuitton", "gucci",
    "versace", "dolce & gabbana", "givenchy", "ysl", "prada", "valentino",
    "burberry", "jean paul gaultier", "mugler", "nishane", "roja",
    "parfums de marly", "byredo", "le labo", "jo malone", "dipytique",
    "kilian", "mfk", "amouage", "xerjoff", "hermes", "giorgio armani",
    "armani", "montale", "mancera", "lalique", "serge lutens", "profumum",
    "fragrance du bois", "carolina herrera", "hugo boss"}
INDIAN_MID = {"calvin klein", "davidoff", "diesel", "bentley", "nike", "adidas",
    "tommy hilfiger", "zara", "h&m", "bath & body works", "victoria's secret",
    "avon", "oriflame", "natura", "o-boticario", "guerlain"}
MIDDLE_EASTERN = {"armaf", "lattafa", "rasasi", "al rehab", "swiss arabian",
    "ajmal", "al haramain", "maison alhambra", "afnan", "paris corner"}
INDIAN_DESIGNER = {"wild stone", "engage", "skinn by titan", "titan", "nykaa",
    "muse", "fogg", "denver", "park avenue", "set wet", "bella vita", "the man company",
    "ustraa", "villain", "belliora"}

def estimate_inr_price(brand: str) -> int:
    b = brand.lower().strip()
    for kw in INDIAN_LUXURY:
        if kw in b: return random.randint(8000, 30000)
    for kw in INDIAN_MID:
        if kw in b: return random.randint(2500, 7000)
    for kw in MIDDLE_EASTERN:
        if kw in b: return random.randint(1200, 4000)
    for kw in INDIAN_DESIGNER:
        if kw in b: return random.randint(299, 2000)
    return random.randint(500, 3500)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------
def parse_ast_list(val: str) -> list[str]:
    if not val or val == "Unknown":
        return []
    try:
        parsed = ast.literal_eval(val)
        if isinstance(parsed, dict):
            result = []
            for k in parsed:
                if isinstance(parsed[k], list):
                    result.extend(parsed[k])
                elif isinstance(parsed[k], str):
                    result.append(parsed[k])
            return result
        elif isinstance(parsed, list):
            return [str(n).strip() for n in parsed if str(n).strip()]
    except:
        if isinstance(val, str):
            return [n.strip() for n in val.split(",") if n.strip()]
    return []

# ---------------------------------------------------------------------------
# Dataset loaders
# ---------------------------------------------------------------------------
def load_da_fragrance(path: str) -> list[dict]:
    """Load DA_Fragrance_Analysis CSV. Has no Gender column, but ~4% of perfume
    names embed an explicit qualifier ('for Men', 'Pour Homme'...) - infer gender
    from the name/brand text itself rather than leaving it permanently null."""
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append({
                "brand": row["brand"],
                "perfume": row["perfume"],
                "name": row["perfume"],
                "launch_year": row.get("launch_year", "Unknown"),
                "notes": parse_ast_list(row.get("notes", "")),
                "accords": parse_ast_list(row.get("main_accords", "")),
                "notes_top": [], "notes_middle": [], "notes_base": [],
                "description": "",
                "image_url": None,
                "gender": normalize_gender(f"{row['brand']} {row['perfume']}"),
                "rating": None,
                "rating_count": None,
                "source": "da_fragrance",
            })
    return rows

def load_fra_perfumes(path: str) -> list[dict]:
    """Load Fragrantica Perfumes CSV (70K)."""
    import ast
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row.get("Name", "").strip()
            if not name:
                continue
            # Extract brand from name: "9am Afnanfor women" → brand="Afnan"
            # Pattern: name ends with "for women", "for men", etc.
            brand = extract_brand_from_name(name)
            perfume_name = extract_perfume_from_name(name)
            accords_raw = row.get("Main Accords", "[]")
            try:
                accords = ast.literal_eval(accords_raw) if accords_raw else []
            except:
                accords = []
            desc = row.get("Description", "").strip()
            rating = row.get("Rating Value")
            rating_count = row.get("Rating Count")

            rows.append({
                "brand": brand,
                "perfume": perfume_name,
                "name": name,
                "launch_year": None,
                "notes": [],
                "accords": [str(a).strip() for a in accords if a],
                "notes_top": [], "notes_middle": [], "notes_base": [],
                "description": desc,
                "image_url": None,
                "gender": normalize_gender(row.get("Gender")),
                "rating": float(rating) if rating and rating not in ("N/A", "NA", "") else None,
                "rating_count": int(rating_count.replace(",", "")) if (rating_count and rating_count not in ("N/A", "NA", "") and rating_count.replace(",", "").isdigit()) else None,
                "source": "fra_perfumes",
            })
    return rows

def load_fra_cleaned(path: str) -> list[dict]:
    """Load Fragrantica Cleaned CSV (24K) with semi-colon delimiter."""
    rows = []
    with open(path, "r", encoding="cp850") as f:
        for row in csv.DictReader(f, delimiter=";"):
            brand = row.get("Brand", "").strip()
            perfume = row.get("Perfume", "").strip()
            if not brand or not perfume:
                continue
            # Combine top/middle/base notes, but also keep the real per-tier
            # breakdown (this is one of only two sources - the other being
            # load_scraper_merged - with genuine Fragrantica tier tags rather
            # than an inferred approximation; see resolve_note_tiers).
            def _parse_tier(col: str) -> list[str]:
                val = row.get(col, "")
                out = []
                if val:
                    for n in val.split(","):
                        n = n.strip()
                        if n and n.lower() not in ("unknown", "none"):
                            out.append(n)
                return out

            notes_top = _parse_tier("Top")
            notes_middle = _parse_tier("Middle")
            notes_base = _parse_tier("Base")
            notes = notes_top + notes_middle + notes_base
            # Gather accords
            accords = []
            for i in range(1, 6):
                a = row.get(f"mainaccord{i}", "").strip()
                if a:
                    accords.append(a)
            rating_raw = row.get("Rating Value", "0").replace(",", ".")
            try:
                rating = float(rating_raw) if rating_raw and rating_raw not in ("N/A", "NA", "") else None
            except:
                rating = None
            rating_count_raw = row.get("Rating Count", "0")
            try:
                rating_count = int(rating_count_raw) if rating_count_raw and rating_count_raw.replace(",", "").isdigit() else None
            except:
                rating_count = None

            # Combine perfumers
            p1 = row.get("Perfumer1", "").strip()
            p2 = row.get("Perfumer2", "").strip()
            if p1 and p1.lower() != "unknown" and p2 and p2.lower() != "unknown":
                perfumer = f"{p1} and {p2}"
            elif p1 and p1.lower() != "unknown":
                perfumer = p1
            elif p2 and p2.lower() != "unknown":
                perfumer = p2
            else:
                perfumer = None

            rows.append({
                "brand": brand,
                "perfume": perfume,
                "name": f"{brand} {perfume}",
                "launch_year": row.get("Year"),
                "notes": notes,
                "accords": accords,
                "notes_top": notes_top, "notes_middle": notes_middle, "notes_base": notes_base,
                "description": "",
                "image_url": None,
                "gender": normalize_gender(row.get("Gender")),
                "rating": rating,
                "rating_count": rating_count,
                "url": row.get("url", "").strip() or None,
                "country": row.get("Country", "").strip() or None,
                "perfumer": perfumer,
                "source": "fra_cleaned",
            })
    return rows

def load_indian_brands(path: str) -> list[dict]:
    """Load the hand-curated Indian mass-market brand supplement (Fogg, Engage,
    Wild Stone, Bella Vita, The Man Company, Ustraa, Ajmal, Skinn by Titan,
    Villain, Denver, Belliora) - compiled from each brand's own published note
    lists, not present in the Fragrantica-derived datasets. `price_inr` is a
    real observed price where known; blank falls back to the brand-tier heuristic."""
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            price_raw = (row.get("price_inr") or "").strip()
            rows.append({
                "brand": row["brand"],
                "perfume": row["perfume"],
                "name": row["perfume"],
                "launch_year": "Unknown",
                "notes": [n.strip() for n in row.get("notes", "").split(",") if n.strip()],
                "accords": [a.strip() for a in row.get("accords", "").split(",") if a.strip()],
                "notes_top": [], "notes_middle": [], "notes_base": [],
                "description": "",
                "image_url": None,
                "gender": normalize_gender(row.get("gender")),
                "rating": None,
                "rating_count": None,
                "real_price_inr": int(price_raw) if price_raw.isdigit() else None,
                "source": "indian_brands",
            })
    return rows


def load_nandini(path: str) -> list[dict]:
    """Load Nandini dataset (2.2K niche + images)."""
    rows = []
    with open(path, "r", encoding="cp850") as f:
        for row in csv.DictReader(f):
            brand = row.get("Brand", "").strip()
            name = row.get("Name", "").strip()
            if not brand or not name:
                continue
            notes_raw = row.get("Notes", "").strip()
            notes = [n.strip() for n in notes_raw.split(",") if n.strip()] if notes_raw else []
            rows.append({
                "brand": brand,
                "perfume": name,
                "name": name,
                "launch_year": None,
                "notes": notes,
                "accords": [],
                "notes_top": [], "notes_middle": [], "notes_base": [],
                "description": row.get("Description", "").strip(),
                "image_url": row.get("Image URL", "").strip() or None,
                "gender": None,
                "rating": None,
                "rating_count": None,
                "source": "nandini",
            })
    return rows


def _clean_scraped_title(name: str, brand: str) -> str:
    """Amazon-scraped product titles carry size/pack/marketing noise the
    Fragrantica-derived datasets don't ("HONEY Oud Unisex Perfume - 100ml",
    "Mood Collection Gift Set For Her - 3 x 15ml") - strip it down to
    something that can actually dedup-match against a clean "brand perfume"
    key from the other sources."""
    n = name
    n = re.sub(r"\s*-\s*\d.*$", "", n).strip()
    if brand and n.lower().startswith(brand.lower()):
        n = n[len(brand):].strip(" -")
    n = re.sub(r"\b(unisex|for\s+men|for\s+women|for\s+her|for\s+him)\b", "", n, flags=re.IGNORECASE)
    n = re.sub(r"\bperfume\b", "", n, flags=re.IGNORECASE)
    n = re.sub(r"\s+", " ", n).strip()
    return n or name


def _extract_price_from_listing(raw: str) -> Optional[int]:
    """`prices` is a stringified list of listing dicts (mrp/discount_price/
    currency/size_ml/url) - take the first listing's discounted price, or
    its MRP if no discount is recorded."""
    if not raw:
        return None
    try:
        parsed = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        return None
    if not isinstance(parsed, list) or not parsed:
        return None
    first = parsed[0]
    if not isinstance(first, dict):
        return None
    price = first.get("discount_price") or first.get("mrp")
    try:
        return int(price) if price else None
    except (TypeError, ValueError):
        return None


def load_scraper_merged(path: str) -> list[dict]:
    """Load backend/scraper/data/processed/perfume_dataset_merged.csv - our
    own Fragrantica-enriched scrape of Amazon-listed Indian-brand perfumes
    (2.2K rows). Unlike every other source here, this one has 100% real
    accord coverage AND a genuine Top/Middle/Base note pyramid (not
    inferred) - see resolve_note_tiers, which prefers real tags like these
    over the heuristic classifier. Highest merge priority for exactly that
    reason."""
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            brand = (row.get("brand") or "").strip()
            raw_name = (row.get("name") or "").strip()
            if not brand or not raw_name:
                continue
            perfume = _clean_scraped_title(raw_name, brand)
            notes_top = parse_ast_list(row.get("notes.top_notes", ""))
            notes_middle = parse_ast_list(row.get("notes.middle_notes", ""))
            notes_base = parse_ast_list(row.get("notes.base_notes", ""))
            rows.append({
                "brand": brand,
                "perfume": perfume,
                "name": f"{brand} {perfume}",
                "launch_year": "Unknown",
                "notes": list(dict.fromkeys(notes_top + notes_middle + notes_base)),
                "accords": parse_ast_list(row.get("accords", "")),
                "notes_top": notes_top, "notes_middle": notes_middle, "notes_base": notes_base,
                "description": "",
                "image_url": None,
                "gender": normalize_gender(row.get("gender")),
                "rating": None,
                "rating_count": None,
                "real_price_inr": _extract_price_from_listing(row.get("prices", "")),
                "source": "scraper_merged",
            })
    return rows


# ---------------------------------------------------------------------------
# Brand extraction helpers
# ---------------------------------------------------------------------------
GENDER_SUFFIXES = ["for women", "for men", "for women and men", "for unisex",
                   "for her", "for him", "unisex", "women", "men"]

def extract_brand_from_name(name: str) -> str:
    """Extract brand from Fragrantica name format: 'perfume Brandfor women'."""
    # Try common patterns
    original = name
    lower = name.lower()

    # Remove gender suffix
    name_clean = name
    for suffix in sorted(GENDER_SUFFIXES, key=len, reverse=True):
        pattern = rf"\s+{re.escape(suffix)}\s*$"
        if re.search(pattern, lower):
            name_clean = name[:len(name) - len(re.search(pattern, lower).group())].strip()
            break

    # Try to find brand: last word(s) before gender suffix
    # Pattern: "9am Afnan" → perfume="9am", brand="Afnan"
    # Pattern: "9am Dive Afnan" → perfume="9am Dive", brand="Afnan"
    # Some have multi-word brands like "Jean Paul Gaultier"
    # For now, take last word as brand
    words = name_clean.split()
    if len(words) >= 2:
        brand = words[-1]
        # The raw format glues "for" directly onto the brand with no space
        # ("...Afnanfor women"), so the gender-suffix strip above only ever
        # catches the bare "women"/"men" - this trailing "for" survives onto
        # whatever the last word is. Confirmed empirically against ~90 real
        # brand names in production data (Dior, Chanel, Armani, Avon, ...)
        # with zero false positives - no legitimate brand ends in "for".
        if brand.lower().endswith("for") and len(brand) > 3:
            brand = brand[:-3]
        return brand
    return name_clean

def extract_perfume_from_name(name: str) -> str:
    """Extract perfume name (everything before brand/gender suffix)."""
    lower = name.lower()
    for suffix in sorted(GENDER_SUFFIXES, key=len, reverse=True):
        pattern = rf"\s+{re.escape(suffix)}\s*$"
        if re.search(pattern, lower):
            part = name[:len(name) - len(re.search(pattern, lower).group())].strip()
            # Remove last word (brand)
            words = part.split()
            if len(words) >= 2:
                return " ".join(words[:-1])
            return part
    return name


# ---------------------------------------------------------------------------
# Merge & dedup
# ---------------------------------------------------------------------------
def load_all_datasets(da_path: str, max_rows: Optional[int] = None, da_only: bool = False) -> list[dict]:
    """Load all datasets and merge with dedup. Priority: scraper_merged > nandini
    > fra_cleaned > fra_perfumes > indian_brands > da_fragrance. scraper_merged
    is highest priority despite being the smallest source (2.2K rows) because
    it's one of only two sources with a genuine (not inferred) note pyramid,
    and the only one with 100% real accord coverage."""
    all_rows = []

    # 1. DA_Fragrance (base)
    print(f"Loading DA_Fragrance from {da_path}...")
    all_rows.extend(load_da_fragrance(da_path))
    print(f"  -> {len(all_rows)} rows")

    # Indian mass-market brand supplement (local file, always available regardless
    # of --da-only, since it needs no Kaggle download)
    indian_brands_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "indian_brands.csv")
    print(f"Loading Indian brands supplement from {indian_brands_path}...")
    indian_rows = load_indian_brands(indian_brands_path)
    all_rows.extend(indian_rows)
    print(f"  -> {len(indian_rows)} rows")

    # Scraper-enriched Indian-brand dataset (local file, no Kaggle download -
    # available regardless of --da-only, same as indian_brands above)
    scraper_merged_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "scraper", "data", "processed", "perfume_dataset_merged.csv"
    )
    print(f"Loading scraper-enriched dataset from {scraper_merged_path}...")
    scraper_rows = load_scraper_merged(scraper_merged_path)
    all_rows.extend(scraper_rows)
    print(f"  -> {len(scraper_rows)} rows")

    if da_only:
        print("  Skipping Fragrantica & Nandini (--da-only)")
        print(f"\nTotal: {len(all_rows)} rows (no dedup needed for single source)")
        if max_rows and max_rows < len(all_rows):
            all_rows = all_rows[:max_rows]
            print(f"  Truncated to: {max_rows}")
        return all_rows

    # kagglehub is only needed for the Fragrantica/Nandini sources below
    import kagglehub

    # 2. Fragrantica Perfumes
    print("Loading Fragrantica Perfumes...")
    fp = os.path.join(kagglehub.dataset_download("olgagmiufana1/fragrantica-com-fragrance-dataset"), "fra_perfumes.csv")
    all_rows.extend(load_fra_perfumes(fp))
    print(f"  -> {len(all_rows)} rows")

    # 3. Fragrantica Cleaned
    print("Loading Fragrantica Cleaned...")
    fp2 = os.path.join(kagglehub.dataset_download("olgagmiufana1/fragrantica-com-fragrance-dataset"), "fra_cleaned.csv")
    all_rows.extend(load_fra_cleaned(fp2))
    print(f"  -> {len(all_rows)} rows")

    # 4. Nandini (niche + images)
    print("Loading Nandini...")
    fp3 = os.path.join(kagglehub.dataset_download("nandini1999/perfume-recommendation-dataset"), "final_perfume_data.csv")
    all_rows.extend(load_nandini(fp3))
    print(f"  -> {len(all_rows)} rows")

    # Dedup by normalized brand+perfume
    seen = {}
    deduped = []
    for row in all_rows:
        key = (normalize_name(row["brand"]), normalize_name(row["perfume"]))
        if key in seen:
            existing = seen[key]
            existing_priority = SOURCE_PRIORITY.get(existing["source"], 0)
            new_priority = SOURCE_PRIORITY.get(row["source"], 0)
            if new_priority > existing_priority:
                # Merge: keep existing fields that new row doesn't have
                for field in ["notes", "accords", "notes_top", "notes_middle", "notes_base",
                               "description", "image_url", "gender", "rating", "rating_count",
                               "launch_year", "url", "country", "perfumer"]:
                    if not row.get(field) and existing.get(field):
                        row[field] = existing[field]
                # Merge list fields (dedup within) rather than a full overwrite,
                # so a lower-priority source's real tier tags aren't discarded
                # just because a higher-priority source also had some notes.
                row["notes"] = list(dict.fromkeys(existing["notes"] + row["notes"]))
                row["accords"] = list(dict.fromkeys(existing["accords"] + row["accords"]))
                row["notes_top"] = list(dict.fromkeys((existing.get("notes_top") or []) + (row.get("notes_top") or [])))
                row["notes_middle"] = list(dict.fromkeys((existing.get("notes_middle") or []) + (row.get("notes_middle") or [])))
                row["notes_base"] = list(dict.fromkeys((existing.get("notes_base") or []) + (row.get("notes_base") or [])))
                seen[key] = row
        else:
            seen[key] = row

    deduped = list(seen.values())
    print(f"\nAfter dedup: {len(deduped)} unique perfumes")
    print(f"  With images: {sum(1 for r in deduped if r['image_url'])}")
    print(f"  With descriptions: {sum(1 for r in deduped if r['description'])}")
    print(f"  With notes: {sum(1 for r in deduped if r['notes'])}")
    print(f"  With accords: {sum(1 for r in deduped if r['accords'])}")
    print(f"  With ratings: {sum(1 for r in deduped if r['rating'])}")
    print(f"  With launch_year: {sum(1 for r in deduped if r['launch_year'])}")
    print(f"  With gender: {sum(1 for r in deduped if r['gender'])}")
    print(f"  With url: {sum(1 for r in deduped if r.get('url'))}")
    print(f"  With country: {sum(1 for r in deduped if r.get('country'))}")
    print(f"  With perfumer: {sum(1 for r in deduped if r.get('perfumer'))}")

    if max_rows and max_rows < len(deduped):
        deduped = deduped[:max_rows]
        print(f"  Truncated to: {max_rows}")

    return deduped


# ---------------------------------------------------------------------------
# Embedding & seeding
# ---------------------------------------------------------------------------
def generate_embedding(model, text: str):
    return model.encode(text, show_progress_bar=False).tolist()

def to_pgvector_literal(embedding: list[float]) -> str:
    """asyncpg has no built-in codec for pgvector's `vector` type - a raw Python
    list fails with 'expected str, got list'. Serialize to the text literal
    Postgres' vector input parser accepts, then cast with ::vector in SQL."""
    return "[" + ",".join(str(x) for x in embedding) + "]"

POSITION_WEIGHTS = [1.0, 0.8, 0.6, 0.4, 0.2]


def compute_longevity_sillage(accords: list[str], notes: list[str]) -> tuple[float, float]:
    """Deterministic heuristic: heavier/denser accords (woody, amber, oud, leather...)
    linger and project more than light ones (citrus, fresh, aquatic...). Weighted by
    accord prominence (Fragrantica orders main_accords by strength). No ground-truth
    longevity/sillage data exists in any of the 4 source datasets, so this is derived
    entirely from the accord vocabulary already used by scenario_map.py."""
    from app.services.scenario_map import LONGEVITY_ACCORD_WEIGHTS, SILLAGE_ACCORD_WEIGHTS, POWER_NOTES

    top_accords = (accords or [])[:5]
    if not top_accords:
        return 50.0, 50.0

    total_weight = 0.0
    longevity_sum = 0.0
    sillage_sum = 0.0
    for i, accord in enumerate(top_accords):
        pw = POSITION_WEIGHTS[i] if i < len(POSITION_WEIGHTS) else 0.1
        a = accord.lower().strip()
        longevity_sum += pw * LONGEVITY_ACCORD_WEIGHTS.get(a, 0.5)
        sillage_sum += pw * SILLAGE_ACCORD_WEIGHTS.get(a, 0.5)
        total_weight += pw

    longevity = (longevity_sum / total_weight) * 100
    sillage = (sillage_sum / total_weight) * 100

    note_set = {n.lower().strip() for n in (notes or [])}
    if note_set & {p.lower() for p in POWER_NOTES}:
        longevity = min(100.0, longevity + 8)
        sillage = min(100.0, sillage + 6)

    return round(longevity, 1), round(sillage, 1)


def resolve_note_tiers(row: dict) -> tuple[list[str], list[str], list[str]]:
    """Prefer real Top/Middle/Base tags carried through from load_fra_cleaned
    or load_scraper_merged (row["notes_top"/"notes_middle"/"notes_base"]);
    only run the heuristic classifier (scenario_map.classify_note_tiers) on
    whatever notes in the final merged `notes` union aren't already covered
    by a real tag. This matters for rows assembled from multiple sources
    during dedup - a perfume might have real tier tags for some of its notes
    (from whichever source provided them) and merged-in untagged notes from
    another source, and a row shouldn't lose the real data it does have just
    because it also has gaps."""
    from app.services.scenario_map import classify_note_tiers

    real_top = row.get("notes_top") or []
    real_middle = row.get("notes_middle") or []
    real_base = row.get("notes_base") or []
    tagged = {n.lower() for n in real_top + real_middle + real_base}
    untagged = [n for n in (row.get("notes") or []) if n.lower() not in tagged]
    inferred_top, inferred_heart, inferred_base = classify_note_tiers(untagged)
    return (
        list(dict.fromkeys(real_top + inferred_top)),
        list(dict.fromkeys(real_middle + inferred_heart)),
        list(dict.fromkeys(real_base + inferred_base)),
    )


def normalize_gender(raw: Optional[str]) -> Optional[str]:
    """Map varied source vocabularies ('for women', 'Women', 'Unisex', 'for women and
    men', 'pour homme', 'Femme'...) to a canonical male/female/unisex/None.
    Word-boundary regex avoids 'men' falsely matching inside 'women'. Also used for
    name-based inference (e.g. 'Adam Levine For Men') when a dataset has no explicit
    Gender column, since ~4% of Fragrantica perfume names embed a gender qualifier."""
    if not raw:
        return None
    r = raw.strip().lower()
    if not r or r in ("unknown", "n/a", "na"):
        return None
    has_women = bool(re.search(r"\bwomen\b|\bwoman\b|\bfemale\b|\bfemme\b|\bfor her\b", r))
    has_men = bool(re.search(r"\bmen\b|\bman\b|\bmale\b|\bhomme\b|\bfor him\b", r))
    if "unisex" in r or (has_women and has_men):
        return "unisex"
    if has_women:
        return "female"
    if has_men:
        return "male"
    return None


def build_embedding_text(row: dict) -> str:
    """Build richest possible text for embedding."""
    parts = [row["brand"], row["perfume"]]
    if row["accords"]:
        parts.append(" ".join(row["accords"][:8]))
    if row["notes"]:
        parts.append(" ".join(row["notes"][:10]))
    if row["description"]:
        parts.append(row["description"][:300])
    return ". ".join(parts)


def seed_local(perfumes: list[dict], conn_string: str):
    """Seed into local pgvector via asyncpg. Upserts (not insert-only) - a
    repeated/live run updates existing rows in place (respecting each
    record's source_priority) instead of silently skipping them, so this
    same function is safe to run more than once as ingestion becomes a
    recurring/live process rather than a single one-shot batch."""
    import asyncpg, asyncio
    from sentence_transformers import SentenceTransformer
    import torch

    from app.ingestion.contracts import PerfumeRecord
    from app.ingestion.upsert import upsert_perfume
    from app.ingestion.validators import validate_record

    has_cuda = torch.cuda.is_available()
    device = "cuda" if has_cuda else "cpu"
    print(f"Using device: {device}")
    model = SentenceTransformer(EMBEDDING_MODEL_VERSION, device=device)

    async def run():
        conn = await asyncpg.connect(conn_string)
        upserted = 0
        invalid = 0
        errors = 0

        for i, row in enumerate(perfumes):
            text = build_embedding_text(row)
            embedding = generate_embedding(model, text)
            price = row.get("real_price_inr") or estimate_inr_price(row["brand"])
            longevity_score, sillage_score = compute_longevity_sillage(row["accords"], row["notes"])
            top_notes, heart_notes, base_notes = resolve_note_tiers(row)

            record = PerfumeRecord(
                brand=row["brand"], perfume=row["perfume"], name=row.get("name") or "",
                launch_year=row.get("launch_year") or "Unknown", gender=row.get("gender"),
                accords=row["accords"] or [], notes=row["notes"] or [],
                notes_top=top_notes, notes_middle=heart_notes, notes_base=base_notes,
                description=row.get("description") or "", image_url=row.get("image_url"),
                rating=row.get("rating"), rating_count=row.get("rating_count"),
                real_price_inr=price, url=row.get("url"), country=row.get("country"),
                perfumer=row.get("perfumer"), source=row.get("source", "unknown"),
                source_priority=SOURCE_PRIORITY.get(row.get("source"), 0),
            )

            issues = validate_record(record)
            if issues:
                invalid += 1
                if invalid <= 3:
                    print(f"  Invalid record skipped ({record.brand}/{record.perfume}): {issues}")
                continue

            try:
                await upsert_perfume(
                    conn, record, to_pgvector_literal(embedding),
                    longevity_score, sillage_score, model_version=EMBEDDING_MODEL_VERSION,
                )
                upserted += 1
            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f"  Error: {e}")

            if (i + 1) % 500 == 0:
                print(f"  [{i+1}/{len(perfumes)}] upserted: {upserted}, invalid: {invalid}, errors: {errors}")

        count = await conn.fetchval("SELECT COUNT(*) FROM perfumes")
        print(f"\nDone! Upserted: {upserted}, Invalid: {invalid}, Errors: {errors}, Total in DB: {count}")
        await conn.close()

    asyncio.run(run())


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="AuraMatch AI - Seed fragrance data")
    parser.add_argument("--dsn", default=os.getenv("DATABASE_URL",
                        "postgresql://auramatch:auramatch_secret@localhost:5434/auramatch"))
    parser.add_argument("--cuda", action="store_true", help="Use CUDA if available")
    parser.add_argument("--da-csv", default="../DA_Fragrance_Analysis-main/DA_Fragrance_Analysis-main/Datasets/cleaned_frag_dataset.csv")
    parser.add_argument("--max", type=int, default=None, help="Max perfumes to seed")
    parser.add_argument("--da-only", action="store_true", help="Skip Fragrantica & Nandini (DA_Fragrance only)")
    args = parser.parse_args()

    if args.cuda:
        import torch
        print(f"CUDA available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"  Device: {torch.cuda.get_device_name(0)}")

    print("Loading and merging all datasets...")
    perfumes = load_all_datasets(args.da_csv, max_rows=args.max, da_only=args.da_only)
    seed_local(perfumes, args.dsn)


if __name__ == "__main__":
    main()
