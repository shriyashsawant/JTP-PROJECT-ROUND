import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.scraper.pipeline import run_pipeline
from backend.scraper.brands import BRAND_CONFIGS


def main():
    parser = argparse.ArgumentParser(
        description="AuraMatch AI - Perfume Data Extraction Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m backend.scraper.cli --brands bellavita,skinn,ajmal
  python -m backend.scraper.cli --all
  python -m backend.scraper.cli --all --no-reviews --enrich
  python -m backend.scraper.cli --all --format csv
  python -m backend.scraper.cli --all --deep
  python -m backend.scraper.cli --all --fragrantica
  python -m backend.scraper.cli --all --amazon
  python -m backend.scraper.cli --all --fragrantica --amazon --playwright
  python -m backend.scraper.cli --all --fragrantica --amazon --fragrantica-limit 50 --amazon-limit 30
        """,
    )

    parser.add_argument(
        "--brands", "-b",
        type=str,
        default="",
        help="Comma-separated brand keys to scrape (default: all)",
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Scrape all configured brands",
    )
    parser.add_argument(
        "--no-products",
        action="store_true",
        help="Skip product scraping phase",
    )
    parser.add_argument(
        "--no-reviews",
        action="store_true",
        help="Skip review scraping phase",
    )
    parser.add_argument(
        "--enrich",
        action="store_true",
        default=True,
        help="Run AI/rule-based enrichment (default: True)",
    )
    parser.add_argument(
        "--no-enrich",
        action="store_true",
        help="Disable enrichment",
    )
    parser.add_argument(
        "--deep", "-d",
        action="store_true",
        help="Deep scrape: visit each product page for full notes/accords (slower but richer)",
    )
    parser.add_argument(
        "--fragrantica",
        action="store_true",
        help="Enrich product data from Fragrantica (notes, accords, ratings, reviews)",
    )
    parser.add_argument(
        "--amazon",
        action="store_true",
        help="Enrich product data from Amazon (prices, ratings, reviews)",
    )
    parser.add_argument(
        "--fragrantica-limit",
        type=int,
        default=100,
        help="Max products to enrich from Fragrantica (default: 100)",
    )
    parser.add_argument(
        "--amazon-limit",
        type=int,
        default=50,
        help="Max products to enrich from Amazon (default: 50)",
    )
    parser.add_argument(
        "--playwright", "-p",
        action="store_true",
        help="Use Playwright for JS rendering (accords, ratings, reviews, Amazon reviews)",
    )
    parser.add_argument(
        "--format", "-f",
        choices=["json", "csv"],
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "--list-brands",
        action="store_true",
        help="List all available brand keys and exit",
    )

    args = parser.parse_args()

    if args.list_brands:
        print("Available brands:")
        for key, config in sorted(BRAND_CONFIGS.items()):
            print(f"  {key:30s} {config['name']}")
        sys.exit(0)

    brand_keys = None
    if args.brands:
        brand_keys = [b.strip() for b in args.brands.split(",") if b.strip() in BRAND_CONFIGS]
        if not brand_keys:
            print(f"Error: No valid brand keys found in '{args.brands}'")
            print("Use --list-brands to see available keys")
            sys.exit(1)
    elif args.all:
        brand_keys = list(BRAND_CONFIGS.keys())

    run_enrich = args.enrich and not args.no_enrich

    if args.fragrantica_limit or args.amazon_limit:
        import backend.scraper.pipeline as _pl
        if args.fragrantica_limit:
            _pl.FRAGRANTICA_LIMIT = args.fragrantica_limit
        if args.amazon_limit:
            _pl.AMAZON_LIMIT = args.amazon_limit

    run_pipeline(
        brand_keys=brand_keys,
        scrape_products=not args.no_products,
        scrape_reviews=not args.no_reviews,
        run_enrichment=run_enrich,
        output_format=args.format,
        deep_scrape=args.deep,
        scrape_fragrantica=args.fragrantica,
        scrape_amazon=args.amazon,
        use_playwright=args.playwright,
    )


if __name__ == "__main__":
    main()
