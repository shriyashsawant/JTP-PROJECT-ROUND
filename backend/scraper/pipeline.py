import json
import time
import re
from pathlib import Path
from typing import Optional

from .models import PerfumeProduct
from .brand_scraper import scrape_all_brands
from .review_scraper import scrape_product_reviews, analyze_sentiment, extract_review_insights
from .enricher import AIEnricher
from .utils import save_json, load_json, chunk_list
from .config import RAW_DIR, PROCESSED_DIR, AI_ENRICHMENT_CONFIG


REVIEW_SCRAPE_LIMIT = 20
FRAGRANTICA_LIMIT = 100
AMAZON_LIMIT = 50


def safe_print(msg: str):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', errors='replace').decode('ascii'))


def enrich_product_batch(enricher: AIEnricher, products: list[PerfumeProduct]) -> list[PerfumeProduct]:
    for product in products:
        enricher.enrich(product)
    return products


def attach_review_insights(product: PerfumeProduct, reviews_dir: Path = None):
    if reviews_dir is None:
        from .config import REVIEWS_DIR
        reviews_dir = REVIEWS_DIR

    safe = f"{product.brand}_{product.name}".replace(" ", "_").lower()
    safe = re.sub(r"[^a-z0-9_]", "", safe)
    review_file = reviews_dir / f"{safe}.json"

    if review_file.exists():
        try:
            data = load_json(review_file)
            ins = data.get("insights", {})

            product.review_summary = f"Based on {data.get('reviews_count', 0)} reviews"
            avg_r = ins.get("avg_rating")
            if avg_r:
                product.rating = avg_r

            sent = ins.get("sentiment", {})
            from .models import ReviewSentiment
            product.review_sentiment = ReviewSentiment(**sent)

            lim = ins.get("longevity_mentions")
            if lim:
                product.longevity = lim[0]
            proj = ins.get("projection_mentioned")
            if proj:
                product.projection = proj

            seasons = ins.get("season_mentions", [])
            if seasons:
                product.season = list(dict.fromkeys(product.season + seasons))

            occasions = ins.get("occasion_mentions", [])
            if occasions:
                product.occasion = list(dict.fromkeys(product.occasion + occasions))
        except Exception:
            pass


def run_pipeline(
    brand_keys: Optional[list[str]] = None,
    scrape_products: bool = True,
    scrape_reviews: bool = True,
    run_enrichment: bool = True,
    output_format: str = "json",
    deep_scrape: bool = False,
    scrape_fragrantica: bool = False,
    scrape_amazon: bool = False,
    use_playwright: bool = False,
):
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    elif hasattr(sys.stdout, 'encoding') and sys.stdout.encoding and sys.stdout.encoding.upper() not in ('UTF-8', 'UTF8'):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    print("=" * 60)
    print("  AURA MATCH AI - PERFUME DATA EXTRACTION PIPELINE")
    print("=" * 60)

    all_products = []

    if scrape_products:
        print("\n[Phase 1] Scraping brand websites...")
        if deep_scrape:
            print("  Deep scrape mode: will visit each product page for rich data")
        all_products = scrape_all_brands(brand_keys, deep=deep_scrape)
        print(f"  Scraped {len(all_products)} products")

    existing = RAW_DIR / "_all_brands_combined.json"
    if not all_products and existing.exists():
        print("\n[Phase 1] Loading existing scraped data...")
        raw = load_json(existing)
        all_products = [PerfumeProduct(**p) for p in raw]
        print(f"  Loaded {len(all_products)} products from cache")

    if not all_products:
        print("[SKIP] No products to process")
        return []

    phase = 2

    if scrape_reviews and all_products:
        limit = min(REVIEW_SCRAPE_LIMIT, len(all_products))
        print(f"\n[Phase {phase}] Scraping reviews for {limit}/{len(all_products)} products...")
        phase += 1
        for i, product in enumerate(all_products[:limit]):
            safe_print(f"  [{i+1}/{limit}] {product.brand} - {product.name}")
            try:
                scrape_product_reviews(product.brand, product.name)
                time.sleep(1)
            except Exception as e:
                print(f"    [WARN] Review scrape failed: {e}")

    print(f"\n[Phase {phase}] Attaching review insights...")
    phase += 1
    for product in all_products:
        attach_review_insights(product)

    if scrape_fragrantica and all_products:
        limit = min(FRAGRANTICA_LIMIT, len(all_products))
        print(f"\n[Phase {phase}] Enriching from Fragrantica ({limit} products)...")
        phase += 1
        from .scrapers.fragrantica_scraper import FragranticaScraper
        scraper = FragranticaScraper(use_playwright=use_playwright)
        scraper.enrich_many(all_products[:limit])

    if scrape_amazon and all_products:
        limit = min(AMAZON_LIMIT, len(all_products))
        print(f"\n[Phase {phase}] Enriching from Amazon ({limit} products)...")
        phase += 1
        from .scrapers.amazon_scraper import AmazonScraper
        scraper = AmazonScraper(use_playwright=use_playwright)
        scraper.enrich_many(all_products[:limit])

    # Text-based notes extraction for brands not on Fragrantica
    print(f"\n[Phase {phase}] Extracting notes from product descriptions...")
    phase += 1
    from .utils import extract_notes_from_product
    fr_brands = {"Ajmal Perfumes","Fogg","Lattafa","Maison Alhambra","Rasasi","Afnan","Paris Corner","Fragrance World","Swiss Arabian","Al Haramain","Ahmed Al Maghribi","Bombay Perfumery","All Good Scents"}
    for product in all_products:
        if product.brand in fr_brands:
            continue  # Already has Fragrantica data
        existing = product.notes
        has_top = bool(existing.top_notes if hasattr(existing, 'top_notes') else [])
        has_mid = bool(existing.middle_notes if hasattr(existing, 'middle_notes') else [])
        has_base = bool(existing.base_notes if hasattr(existing, 'base_notes') else [])
        if has_top and has_mid and has_base:
            continue  # Already has proper notes
        product_dict = product.model_dump()
        extracted = extract_notes_from_product(product_dict)
        if extracted.get("top") or extracted.get("middle") or extracted.get("base"):
            if not has_top:
                existing.top_notes = extracted["top"]
            if not has_mid:
                existing.middle_notes = extracted["middle"]
            if not has_base:
                existing.base_notes = extracted["base"]

    if run_enrichment:
        print(f"\n[Phase {phase}] Enriching with AI/rule-based features...")
        phase += 1
        enricher = AIEnricher(model_name=AI_ENRICHMENT_CONFIG["model_name"])
        for batch in chunk_list(all_products, AI_ENRICHMENT_CONFIG["batch_size"]):
            enrich_product_batch(enricher, batch)

        if enricher.model is not None:
            print(f"\n[Phase {phase}] Computing embeddings...")
            phase += 1
            for i, product in enumerate(all_products):
                if i % 50 == 0:
                    print(f"  Embedding {i}/{len(all_products)}")
                emb = enricher.generate_description_embedding(product)
                if emb:
                    product.__dict__["embedding"] = emb

    print(f"\n[Phase {phase}] Saving final dataset...")
    output_data = []
    for p in all_products:
        d = p.model_dump()
        if "embedding" in d:
            d["embedding"] = d["embedding"][:8]
        output_data.append(d)

    if output_format == "json":
        out = PROCESSED_DIR / "perfume_dataset.json"
        save_json(output_data, out)
        print(f"  Saved: {out} ({len(output_data)} records)")
    elif output_format == "csv":
        try:
            import pandas as pd
            df = pd.json_normalize(output_data)
            csv_path = PROCESSED_DIR / "perfume_dataset.csv"
            df.to_csv(csv_path, index=False)
            print(f"  Saved: {csv_path} ({len(df)} rows)")
        except ImportError:
            print("  [WARN] pandas not installed, falling back to JSON")
            out = PROCESSED_DIR / "perfume_dataset.json"
            save_json(output_data, out)

    brands_list = list(dict.fromkeys(p.brand for p in all_products))
    ratings = [p.rating for p in all_products if p.rating]
    avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0.0

    summary = {
        "total_products": len(all_products),
        "brands": brands_list,
        "brand_count": len(brands_list),
        "avg_rating": avg_rating,
        "output": str(PROCESSED_DIR),
        "ai_enriched": run_enrichment,
        "reviews_scraped": scrape_reviews,
        "fragrantica_enriched": scrape_fragrantica,
        "amazon_enriched": scrape_amazon,
    }
    save_json(summary, PROCESSED_DIR / "summary.json")

    print("\n" + "=" * 60)
    print("  PIPELINE COMPLETE")
    print(f"  Products: {len(all_products)}  |  Brands: {len(brands_list)}")
    print(f"  Avg rating: {avg_rating}")
    print(f"  Output: {PROCESSED_DIR}")
    print("=" * 60)

    return all_products
