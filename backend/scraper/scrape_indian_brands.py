#!/usr/bin/env python3
"""
Quick-start: Scrape all Indian perfume brands using Shopify JSON endpoints
and HTML fallback for custom sites.

Usage:
    python scrape_indian_brands.py
    python scrape_indian_brands.py --no-reviews
    python scrape_indian_brands.py --no-enrich
    python scrape_indian_brands.py --format csv
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.scraper.pipeline import run_pipeline

TARGET_BRANDS = [
    # Shopify (products.json) — fast & stable
    "bellavita",
    "bellavitaluxury",  # separate luxury store with richer descriptions
    "ajmal",
    "engage",
    "villain",
    "themancompany",
    "ustraa",
    "beardo",
    "bombayperfumery",
    "allgoodscent",
    "nasoprofumi",
    "houseofem5",
    "perfumeryco",
    "scentedelic",
    "muznafragrances",
    "hasanoud",
    "fraganote",
    "aeronot",
    "scentari",
    "almaham",
    "aafiyaperfumes",
    "isakfragrances",
    "exoticscentsindia",
    "olfactorymusicfest",
    "houseofkanzan",
    "sugandhco",
    "mlramnarain",
    "gulabsinghjohrimal",
    # Custom / HTML
    "skinn",
    "fogg",
    "denver",
    "wildstone",
    "parkavenue",
    "lattafa",
    "armaf",
    "rasasi",
    "afnan",
    "pariscorner",
    "fragranceworld",
    "swissarabian",
    "alharamain",
    "ahmedalmaghribi",
    "layerrshot",
    "yardleyindia",
    "kannaujattar",
    "arochem",
    "setwet",
    "envyfragrances",
]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape Indian perfume brands")
    parser.add_argument("--no-reviews", action="store_true", help="Skip review scraping")
    parser.add_argument("--no-enrich", action="store_true", help="Skip enrichment")
    parser.add_argument("--deep", action="store_true", help="Deep scrape product pages for rich data")
    parser.add_argument("--format", choices=["json", "csv"], default="json")
    args = parser.parse_args()

    run_pipeline(
        brand_keys=TARGET_BRANDS,
        scrape_products=True,
        scrape_reviews=not args.no_reviews,
        run_enrichment=not args.no_enrich,
        output_format=args.format,
        deep_scrape=args.deep,
    )
