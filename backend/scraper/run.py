#!/usr/bin/env python3
"""
AuraMatch AI - Perfume Data Extraction Pipeline
================================================
Standalone runner script.

Usage:
    python run.py                          # Scrape a few sample brands
    python run.py --all                    # Scrape all 40+ brands
    python run.py --brands bellavita,skinn # Specific brands
    python run.py --all --no-reviews       # Skip review scraping
    python run.py --all --no-enrich        # Skip AI enrichment
    python run.py --all --format csv       # Output as CSV
    python run.py --list-brands            # List all brand keys
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.scraper.cli import main

if __name__ == "__main__":
    main()
