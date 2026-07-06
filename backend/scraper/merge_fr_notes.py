"""
One-off data-prep script: enriches backend/scraper/data/processed/
perfume_dataset.csv with real Top/Middle/Base note tiers from the
Fragrantica cache, producing perfume_dataset_merged.csv - the file
seed_data.py's load_scraper_merged() reads from. Already run; kept for
provenance (how the scraper-merged dataset was actually built), not part
of the live ingestion pipeline.

Run from the repository root (paths below are relative to it):
    python backend/scraper/merge_fr_notes.py
"""
import json, csv, re
from pathlib import Path
from collections import Counter

# Load our dataset
csv_path = Path("backend/scraper/data/processed/perfume_dataset.csv")
products = []
with open(csv_path, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        products.append(row)
print(f"Current dataset: {len(products)} products")

# Load FR cached notes
cache_dir = Path("backend/scraper/data/fragrantica_cache")
fr_notes = {}
for f in cache_dir.glob("perfume_*.json"):
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        pid = f.stem.replace("perfume_", "")
        if data.get("notes", {}).get("top_notes") or data.get("notes", {}).get("middle_notes") or data.get("notes", {}).get("base_notes"):
            fr_notes[pid] = data["notes"]
    except:
        pass
print(f"FR cached perfume notes: {len(fr_notes)}")

# Match FR notes to our products by name/brand
matched = 0
for p in products:
    pname = p.get("name", "").lower().strip()
    pbrand = p.get("brand", "").lower().strip()
    # Check current notes column
    current_top = p.get("notes.top_notes", "").strip("[]").replace("'", "").replace('"', "")
    current_mid = p.get("notes.middle_notes", "").strip("[]").replace("'", "").replace('"', "")
    current_base = p.get("notes.base_notes", "").strip("[]").replace("'", "").replace('"', "")
    has_good_notes = bool(current_top.strip()) and bool(current_mid.strip()) and bool(current_base.strip())
    if has_good_notes:
        continue  # Already has all 3 levels

    # Search FR notes for this product
    best = None
    best_score = 0
    for fid, notes in fr_notes.items():
        # Get name from FR data
        fname = notes.get("_name", "").lower()
        score = 0
        if pname and fname:
            # Word overlap score
            pwords = set(pname.split())
            fwords = set(fname.split())
            overlap = len(pwords & fwords)
            if overlap >= 2:
                score = overlap
        if score > best_score:
            best_score = score
            best = notes

    if best and (best.get("top_notes") or best.get("middle_notes") or best.get("base_notes")):
        # Apply FR notes where missing
        top = best.get("top_notes", [])
        mid = best.get("middle_notes", [])
        base = best.get("base_notes", [])
        if top and not current_top.strip():
            p["notes.top_notes"] = json.dumps(top)
        if mid and not current_mid.strip():
            p["notes.middle_notes"] = json.dumps(mid)
        if base and not current_base.strip():
            p["notes.base_notes"] = json.dumps(base)
        matched += 1

print(f"Products enriched with FR notes: {matched}")

# Save merged dataset
out_path = Path("backend/scraper/data/processed/perfume_dataset_merged.csv")
fieldnames = products[0].keys()
with open(out_path, "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for p in products:
        # Re-check notes
        top = p.get("notes.top_notes", "").strip("[]").replace("'", "").replace('"', "")
        mid = p.get("notes.middle_notes", "").strip("[]").replace("'", "").replace('"', "")
        base = p.get("notes.base_notes", "").strip("[]").replace("'", "").replace('"', "")
        writer.writerow(p)

# Stats
with open(out_path, "r", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

has_top = sum(1 for r in rows if r.get("notes.top_notes", "").strip())
has_mid = sum(1 for r in rows if r.get("notes.middle_notes", "").strip())
has_base = sum(1 for r in rows if r.get("notes.base_notes", "").strip())
all_three = sum(1 for r in rows if all(r.get(f"notes.{l}_notes", "").strip() for l in ["top", "middle", "base"]))
print(f"\nAfter merge:")
print(f"  Top notes:    {has_top}/{len(rows)} ({100*has_top//len(rows)}%)")
print(f"  Middle notes: {has_mid}/{len(rows)} ({100*has_mid//len(rows)}%)")
print(f"  Base notes:   {has_base}/{len(rows)} ({100*has_base//len(rows)}%)")
print(f"  All 3 levels: {all_three}/{len(rows)} ({100*all_three//len(rows)}%)")
print(f"\nSaved to: {out_path}")
