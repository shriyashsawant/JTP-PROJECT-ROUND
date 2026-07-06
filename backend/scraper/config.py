import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
REVIEWS_DIR = DATA_DIR / "reviews"

RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
REVIEWS_DIR.mkdir(parents=True, exist_ok=True)

SCRAPING_CONFIG = {
    "request_delay": float(os.getenv("SCRAPE_DELAY", "2.0")),
    "max_retries": int(os.getenv("SCRAPE_MAX_RETRIES", "3")),
    "timeout": int(os.getenv("SCRAPE_TIMEOUT", "30")),
    "user_agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "use_playwright": os.getenv("USE_PLAYWRIGHT", "true").lower() == "true",
    "headless": True,
}

AI_ENRICHMENT_CONFIG = {
    "enabled": os.getenv("AI_ENRICH", "true").lower() == "true",
    "model_name": os.getenv("AI_MODEL", "all-MiniLM-L6-v2"),
    "embedding_dim": 384,
    "batch_size": 32,
}

OUTPUT_FORMATS = ["json", "csv", "parquet"]
DEFAULT_OUTPUT_FORMAT = "json"
