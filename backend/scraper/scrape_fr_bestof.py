"""
One-off data-prep script: scrapes the Fragrantica "Best of 2025" list URLs
(backend/scraper/data/fragrantica-scraped/fragrantica_bestof_urls.json)
into the local perfume_*.json cache, skipping anything already cached.
Drove the data behind the "Add perfumes referenced in Fragrantica's Best of
2025 lists" dataset addition. Kept for provenance, not part of the live
ingestion pipeline.

Run from the repository root (paths below are relative to it):
    python backend/scraper/scrape_fr_bestof.py
"""
import re, json, sys, time
from pathlib import Path
sys.path.insert(0, ".")
from backend.scraper.scrapers.fragrantica_scraper import FragranticaScraper

def main():
    cache_dir = Path("backend/scraper/data/fragrantica_cache")
    cached = len(list(cache_dir.glob("perfume_*.json")))

    with open("backend/scraper/data/fragrantica-scraped/fragrantica_bestof_urls.json") as f:
        urls = json.load(f)

    pattern = re.compile(r"https://www\.fragrantica\.com/perfume/[^/]+/.+-(\d+)\.html")
    to_scrape = []
    for url in urls:
        m = pattern.match(url)
        if m and not (cache_dir / f"perfume_{m.group(1)}.json").exists():
            to_scrape.append(url)

    print(f"Total: {len(urls)}, Cached: {cached}, To scrape: {len(to_scrape)}")
    if not to_scrape:
        print("All done!")
        return

    scraper = FragranticaScraper(delay=5.0, use_playwright=True)
    print("Starting with 15s initial cooldown...")
    time.sleep(15)
    scraper.scrape_urls(to_scrape, cooldown_every=15, cooldown_secs=30)

    final = len(list(cache_dir.glob("perfume_*.json")))
    print(f"\nDone! Total cached: {final}")

if __name__ == "__main__":
    main()
