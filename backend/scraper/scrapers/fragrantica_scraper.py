import re
import json
import time
import random
import requests
from pathlib import Path
from typing import Optional
from bs4 import BeautifulSoup

from ..config import DATA_DIR
from ..utils import save_json, load_json


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:126.0) Gecko/20100101 Firefox/126.0",
]


def is_challenge_page(html: str) -> bool:
    if not html:
        return True
    if "<title>Just a moment...</title>" in html or "Just a moment..." in html:
        return True
    if "cf-challenge-" in html or 'id="cf-challenge-' in html:
        return True
    return False


class FragranticaScraper:
    BASE_URL = "https://www.fragrantica.com"

    def __init__(self, delay: float = 8.0, use_playwright: bool = False):
        self.delay = delay
        self.use_playwright = use_playwright
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.fragrantica.com/",
        })
        self.cache_dir = DATA_DIR / "fragrantica_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = None
        self._browser = None
        self._browser_context = None

    def _get_playwright_browser(self):
        if self._browser:
            return self._browser
        try:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()
            user_data_dir = str(DATA_DIR / "chrome_profile")
            # Launch persistent context using system Chrome to bypass Turnstile blocks
            self._browser_context = self._playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                headless=False,
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                locale="en-US",
                timezone_id="America/New_York",
                args=["--disable-blink-features=AutomationControlled"]
            )
            self._browser = self._browser_context
        except Exception as e:
            print(f"Failed to start Playwright: {e}")
            self.use_playwright = False
        return self._browser_context

    def close(self):
        if self._browser_context:
            try:
                self._browser_context.close()
            except:
                pass
        self._browser_context = None
        self._browser = None
        if self._playwright:
            try:
                self._playwright.stop()
            except:
                pass
        self._playwright = None

    def __del__(self):
        self.close()

    def _fetch_with_playwright(self, url: str) -> Optional[str]:
        browser = self._get_playwright_browser()
        if not browser or not self._browser_context:
            return None
        page = None
        try:
            page = self._browser_context.new_page()
            # Remove automated browser flags
            page.add_init_script("delete navigator.__proto__.webdriver")
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            # Wait for Cloudflare Turnstile if it's there
            for i in range(15):
                title = page.title()
                if "Just a moment" not in title and "Cloudflare" not in title and "Security Check" not in title:
                    break
                if i % 3 == 0:
                    print(f"    [INFO] Cloudflare challenge detected (Title: '{title}'). Please solve the challenge in the browser window...")
                page.wait_for_timeout(3000)
                
            content = page.content()
            page.close()
            return content
        except Exception as e:
            print(f"    Playwright error: {e}")
            if page:
                try:
                    page.close()
                except:
                    pass
            return None

    def _rotate_ua(self):
        self.session.headers.update({"User-Agent": random.choice(USER_AGENTS)})

    def _pause(self):
        time.sleep(self.delay + random.uniform(0, 2))

    def _cache_path(self, key: str) -> Path:
        safe = re.sub(r"[^a-z0-9_]", "_", key.lower())
        return self.cache_dir / f"{safe}.json"

    def _load_cache(self, key: str):
        path = self._cache_path(key)
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return None
        return None

    def _save_cache(self, key: str, data):
        self._cache_path(key).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _extract_notes(self, html: str) -> dict:
        notes = {"top_notes": [], "middle_notes": [], "base_notes": []}
        # Try combined: "Top notes are X; middle notes are Y; base notes are Z"
        m = re.search(
            r"(?:Top|Head|Opening)\s*Notes?\s*(?:are|:)\s*(.+?)\.\s*"
            r"(?:Middle|Heart|Mid)\s*Notes?\s*(?:are|:)\s*(.+?)\.\s*"
            r"(?:Base|Bottom|Dry\s*[Dd]own)\s*Notes?\s*(?:are|:)\s*(.+?)(?:\.|$)",
            html, re.I | re.DOTALL,
        )
        if m:
            notes["top_notes"] = [n.strip().title() for n in re.split(r"[,;/&]+", m.group(1)) if n.strip()]
            notes["middle_notes"] = [n.strip().title() for n in re.split(r"[,;/&]+", m.group(2)) if n.strip()]
            notes["base_notes"] = [n.strip().title() for n in re.split(r"[,;/&]+", m.group(3)) if n.strip()]
            return notes
        # Individual
        for key, pat in [("top_notes", r"Top\s*Notes?[:\s]+(.+?)(?:<|\.)"),
                          ("middle_notes", r"Middle\s*Notes?[:\s]+(.+?)(?:<|\.)"),
                          ("base_notes", r"Base\s*Notes?[:\s]+(.+?)(?:<|\.)")]:
            m2 = re.search(pat, html, re.I)
            if m2:
                notes[key] = [n.strip().title() for n in re.split(r"[,/&]+", m2.group(1)) if n.strip()]
        # Meta fallback
        if not any(notes.values()):
            desc = ""
            meta_m = re.search(r'<meta[^>]*description[^>]*content="([^"]*)"', html, re.I)
            if meta_m:
                desc = meta_m.group(1)
            for key, pat in [("top_notes", r"Top\s*Notes?[:\s]+(.+?)(?:\.|;)"),
                              ("middle_notes", r"Middle\s*Notes?[:\s]+(.+?)(?:\.|;)"),
                              ("base_notes", r"Base\s*Notes?[:\s]+(.+?)(?:\.|;|$)")]:
                m2 = re.search(pat, desc, re.I)
                if m2:
                    notes[key] = [n.strip().title() for n in re.split(r"[,/&]+", m2.group(1)) if n.strip()]
        return notes

    def fetch_page(self, perfume_slug: str, perfume_id: str) -> Optional[str]:
        cache_key = f"perfume_html_{perfume_id}"
        cached = self._load_cache(cache_key)
        if cached and isinstance(cached, dict) and "html" in cached:
            return cached["html"]

        url = f"{self.BASE_URL}/perfume/{perfume_slug}-{perfume_id}.html"

        if self.use_playwright:
            print(f"    Fetching with Playwright: {url}")
            html = self._fetch_with_playwright(url)
            is_challenge = is_challenge_page(html)
            if html and not is_challenge and "403 Forbidden" not in html and "Security Check" not in html:
                self._save_cache(cache_key, {"html": html, "url": url})
                self._pause()
                return html
            print("    Playwright fetch failed or blocked, falling back to requests...")

        self._rotate_ua()
        try:
            r = self.session.get(url, timeout=25, allow_redirects=True)
            if r.status_code == 200:
                html = r.text
                is_challenge = is_challenge_page(html)
                if not is_challenge:
                    self._save_cache(cache_key, {"html": html, "url": url})
                    self._pause()
                    return html
            elif r.status_code in (429, 403):
                wait = 120 + random.randint(0, 60)
                print(f"    {r.status_code} - waiting {wait}s...")
                time.sleep(wait)
                self._rotate_ua()
                r2 = self.session.get(url, timeout=25, allow_redirects=True)
                if r2.status_code == 200:
                    html = r2.text
                    is_challenge = is_challenge_page(html)
                    if not is_challenge:
                        self._save_cache(cache_key, {"html": html, "url": url})
                        self._pause()
                        return html
                print(f"    Retry also {r2.status_code}")
            else:
                print(f"    HTTP {r.status_code}")
        except Exception as e:
            print(f"    Error: {e}")
        return None

    def parse_perfume(self, html: str, perfume_slug: str, perfume_id: str) -> dict:
        notes = self._extract_notes(html)
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.string if soup.title else ""
        name = re.sub(r"\s*-\s*a new fragrance.*$", "", title, flags=re.I).strip()
        meta_el = soup.find("meta", attrs={"name": "description"})
        description = meta_el.get("content", "") if meta_el else ""
        return {
            "id": perfume_id,
            "name": name,
            "notes": notes,
            "description": description,
        }

    def scrape_perfume(self, perfume_slug: str, perfume_id: str) -> Optional[dict]:
        cache_key = f"perfume_{perfume_id}"
        cached = self._load_cache(cache_key)
        if cached and "notes" in cached:
            return cached
        html = self.fetch_page(perfume_slug, perfume_id)
        if not html:
            return None
        data = self.parse_perfume(html, perfume_slug, perfume_id)
        if data:
            self._save_cache(cache_key, data)
        return data

    def scrape_url(self, url: str) -> Optional[dict]:
        m = re.search(r"/perfume/([^/]+)/(.+)-(\d+)\.html", url)
        if not m:
            return None
        return self.scrape_perfume(f"{m.group(1)}/{m.group(2)}", m.group(3))

    def scrape_urls(self, urls: list[str], cooldown_every: int = 20, cooldown_secs: int = 30) -> list[dict]:
        results = []
        for i, url in enumerate(urls):
            data = self.scrape_url(url)
            if data:
                results.append(data)
                nc = sum(len(data.get("notes", {}).get(k, [])) for k in ("top_notes", "middle_notes", "base_notes"))
                print(f"  [{i+1}/{len(urls)}] {data['name'][:45]:45s} {nc:2d} notes")
            else:
                print(f"  [{i+1}/{len(urls)}] FAIL: {url[:70]}")
            if (i + 1) % cooldown_every == 0 and i + 1 < len(urls):
                cached = len(list(self.cache_dir.glob("perfume_*.json")))
                print(f"\n  --- {cached} cached | {cooldown_secs}s cooldown ---\n")
                time.sleep(cooldown_secs)
        return results