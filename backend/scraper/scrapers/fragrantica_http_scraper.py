import re
import json
import time
import random
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

from ..config import DATA_DIR
from ..utils import fetch_page, get_session, save_json, load_json

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]


class FragranticaHttpScraper:
    def __init__(self, delay: float = 3.0):
        self.session = get_session()
        self.delay = delay
        self.cache_dir = DATA_DIR / "fragrantica_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _random_user_agent(self):
        self.session.headers.update({"User-Agent": random.choice(USER_AGENTS)})

    def _cache_path(self, key: str) -> Path:
        safe = re.sub(r"[^\w]", "_", key)[:100]
        return self.cache_dir / f"{safe}.json"

    def _load_cache(self, key: str) -> Optional[dict]:
        path = self._cache_path(key)
        if path.exists():
            return load_json(path)
        return None

    def _save_cache(self, key: str, data: dict):
        path = self._cache_path(key)
        save_json(data, path)

    def _rate_limit(self):
        time.sleep(self.delay + random.uniform(0, 1))

    def scrape_perfume_page(self, url: str) -> Optional[dict]:
        cache_key = f"perfume_{url.split('-')[-1].replace('.html','')}"
        cached = self._load_cache(cache_key)
        if cached:
            return cached

        self._random_user_agent()
        try:
            resp = self.session.get(url, timeout=20, allow_redirects=True)
        except Exception as e:
            print(f"    [WARN] HTTP error for {url[:60]}: {e}")
            return None

        if resp.status_code != 200:
            print(f"    [WARN] HTTP {resp.status_code} for {url[:60]}")
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # Skip if challenge page (JS challenge present)
        if soup.find("script", text=re.compile(r"md5_mfga")):
            return None

        result = self._parse_page(soup, url)
        if result:
            self._save_cache(cache_key, result)
        self._rate_limit()
        return result

    def _parse_page(self, soup: BeautifulSoup, url: str) -> dict:
        data = {
            "url": url,
            "name": "",
            "brand": "",
            "gender": "",
            "perfumer": "",
            "launch_year": None,
            "top_notes": [],
            "middle_notes": [],
            "base_notes": [],
            "accords": {},
            "rating": None,
            "votes": 0,
            "longevity": None,
            "sillage": None,
            "price_value": None,
            "description": "",
        }

        # Title / breadcrumb
        title_el = soup.select_one("h1")
        if title_el:
            data["name"] = title_el.get_text(strip=True)

        # Meta description often contains notes
        meta = soup.find("meta", attrs={"name": "description"})
        if meta:
            data["description"] = meta.get("content", "")

        # Gender from page
        gender_el = soup.select_one("[class*=gender], [itemprop=gender]")
        if gender_el:
            data["gender"] = gender_el.get_text(strip=True).lower()

        # OG tags
        for og in soup.find_all("meta", attrs={"property": True}):
            prop = og.get("property", "")
            if "title" in prop and not data["name"]:
                data["name"] = og.get("content", "")

        # Try to extract notes from meta description
        desc = data.get("description", "")
        if desc:
            # "Top notes: X, Y, Z. Middle notes: ... Base notes: ..."
            patterns = {
                "top_notes": re.compile(r"(?:top|head)\s*notes?\s*[:;]\s*(.+?)(?:\s*(?:middle|heart)|\.)", re.I),
                "middle_notes": re.compile(r"(?:middle|heart)\s*notes?\s*[:;]\s*(.+?)(?:\s*(?:base|bottom|dry)|\.)", re.I),
                "base_notes": re.compile(r"(?:base|bottom|dry\s*down)\s*notes?\s*[:;]\s*(.+?)(?:\.|$)", re.I),
            }
            for key, pat in patterns.items():
                m = pat.search(desc)
                if m:
                    notes = [n.strip().title() for n in re.split(r"[,/&]+", m.group(1)) if n.strip()]
                    if len(notes) >= 2:
                        data[key] = notes

            # Alternately: "Saffron, Amber, Musk" style
            if not data["top_notes"] and not data["middle_notes"]:
                text_lower = desc.lower()
                # Known note words
                known = ["bergamot", "saffron", "amber", "musk", "vanilla", "oud", "rose", "jasmine",
                         "sandalwood", "cedar", "patchouli", "leather", "tobacco", "honey", "coconut",
                         "lavender", "iris", "vetiver", "oakmoss", "citrus", "tonka", "cinnamon"]
                found = [w.title() for w in known if w in text_lower]
                if found:
                    third = max(len(found) // 3, 1)
                    data["top_notes"] = found[:third]
                    data["middle_notes"] = found[third:2*third]
                    data["base_notes"] = found[2*third:]

        # Accords from meta / inline text
        accord_match = re.search(r"Accords\s*[:;]\s*(.+?)(?:\.|$)", desc)
        if accord_match:
            accords_text = accord_match.group(1)
            for a in re.split(r"[,/&]+", accords_text):
                a = a.strip().title()
                if a:
                    data["accords"][a] = 0

        return data

    def enrich_products_from_urls(self, products: list[dict], url_map: dict) -> list[dict]:
        """url_map: {product_index: fragrantica_url}"""
        enriched = 0
        for i, prod in enumerate(products):
            url = url_map.get(i)
            if not url:
                continue

            result = self.fetch_perfume_page(url)
            if not result:
                continue

            if result["top_notes"]:
                prod.setdefault("notes", {})["top_notes"] = result["top_notes"]
            if result["middle_notes"]:
                prod.setdefault("notes", {})["middle_notes"] = result["middle_notes"]
            if result["base_notes"]:
                prod.setdefault("notes", {})["base_notes"] = result["base_notes"]
            if result["accords"]:
                prod["accords"] = result["accords"]
            if result["description"] and not prod.get("description"):
                prod["description"] = result["description"]

            prod["fragrantica_url"] = url
            enriched += 1

            if enriched % 10 == 0:
                print(f"  ... enriched {enriched} from Fragrantica")

        return products