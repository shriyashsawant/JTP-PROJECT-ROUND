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
    "muse", "fogg", "denver", "park avenue", "set wet"}

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

def normalize_name(s: Optional[str]) -> str:
    if not s:
        return ""
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9\s]", "", s)
    return re.sub(r"\s+", " ", s).strip()


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
            # Combine top/middle/base notes
            notes = []
            for col in ["Top", "Middle", "Base"]:
                val = row.get(col, "")
                if val:
                    for n in val.split(","):
                        n = n.strip()
                        if n and n.lower() not in ("unknown", "none"):
                            notes.append(n)
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

            rows.append({
                "brand": brand,
                "perfume": perfume,
                "name": f"{brand} {perfume}",
                "launch_year": row.get("Year"),
                "notes": notes,
                "accords": accords,
                "description": "",
                "image_url": None,
                "gender": normalize_gender(row.get("Gender")),
                "rating": rating,
                "rating_count": rating_count,
                "source": "fra_cleaned",
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
                "description": row.get("Description", "").strip(),
                "image_url": row.get("Image URL", "").strip() or None,
                "gender": None,
                "rating": None,
                "rating_count": None,
                "source": "nandini",
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
        # Check if the last word looks like a known brand
        return words[-1]
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
    """Load all 4 datasets and merge with dedup. Priority: nandini > fra_cleaned > fra_perfumes > da_fragrance."""
    all_rows = []

    # 1. DA_Fragrance (base)
    print(f"Loading DA_Fragrance from {da_path}...")
    all_rows.extend(load_da_fragrance(da_path))
    print(f"  -> {len(all_rows)} rows")

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
    # Priority: nandini (4) > fra_cleaned (3) > fra_perfumes (2) > da_fragrance (1)
    source_priority = {"nandini": 4, "fra_cleaned": 3, "fra_perfumes": 2, "da_fragrance": 1}
    seen = {}
    deduped = []
    for row in all_rows:
        key = (normalize_name(row["brand"]), normalize_name(row["perfume"]))
        if key in seen:
            existing = seen[key]
            existing_priority = source_priority.get(existing["source"], 0)
            new_priority = source_priority.get(row["source"], 0)
            if new_priority > existing_priority:
                # Merge: keep existing fields that new row doesn't have
                for field in ["notes", "accords", "description", "image_url", "gender", "rating", "rating_count", "launch_year"]:
                    if not row.get(field) and existing.get(field):
                        row[field] = existing[field]
                # Merge notes and accords (dedup within)
                row["notes"] = list(dict.fromkeys(existing["notes"] + row["notes"]))
                row["accords"] = list(dict.fromkeys(existing["accords"] + row["accords"]))
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
    """Seed into local pgvector via asyncpg."""
    import asyncpg, asyncio
    from sentence_transformers import SentenceTransformer
    import torch

    has_cuda = torch.cuda.is_available()
    device = "cuda" if has_cuda else "cpu"
    print(f"Using device: {device}")
    model = SentenceTransformer("all-MiniLM-L6-v2", device=device)

    async def run():
        conn = await asyncpg.connect(conn_string)
        inserted = 0
        errors = 0
        batch_size = 100

        for i, row in enumerate(perfumes):
            text = build_embedding_text(row)
            embedding = generate_embedding(model, text)
            price = estimate_inr_price(row["brand"])
            longevity_score, sillage_score = compute_longevity_sillage(row["accords"], row["notes"])

            try:
                await conn.execute("""
                    INSERT INTO perfumes
                        (brand, perfume, launch_year, gender, main_accords, notes,
                         embedding, price_inr, type, image_url,
                         longevity_score, sillage_score)
                    VALUES ($1,$2,$3,$4,$5,$6,$7::vector,$8,$9,$10,$11,$12)
                    ON CONFLICT DO NOTHING
                """,
                    row["brand"], row["perfume"],
                    row.get("launch_year") or "Unknown",
                    row.get("gender"),
                    row["accords"] if row["accords"] else None,
                    row["notes"] if row["notes"] else None,
                    to_pgvector_literal(embedding), price, None,
                    row.get("image_url"),
                    longevity_score, sillage_score,
                )
                inserted += 1
            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f"  Error: {e}")

            if (i + 1) % 500 == 0:
                await conn.execute("COMMIT")
                print(f"  [{i+1}/{len(perfumes)}] inserted: {inserted}, errors: {errors}")

        await conn.execute("COMMIT")
        count = await conn.fetchval("SELECT COUNT(*) FROM perfumes")
        print(f"\nDone! Inserted: {inserted}, Errors: {errors}, Total in DB: {count}")
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
