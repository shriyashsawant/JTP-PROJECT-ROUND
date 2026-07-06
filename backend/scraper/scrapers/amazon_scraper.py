import re
import time
import json
import random
from typing import Optional
from urllib.parse import quote
from pathlib import Path

from bs4 import BeautifulSoup

from ..utils import fetch_page, get_session, save_json, load_json
from ..config import SCRAPING_CONFIG, DATA_DIR
from ..models import PerfumeProduct, ReviewData


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:126.0) Gecko/20100101 Firefox/126.0",
]


class AmazonScraper:
    BASE_URL = "https://www.amazon.in"
    SEARCH_URL = f"{BASE_URL}/s?k={{query}}+perfume"
    PRODUCT_URL = "https://www.amazon.in/dp/{asin}"
    REVIEWS_URL = "https://www.amazon.in/product-reviews/{asin}/"

    def __init__(self, delay: float = 3.0, use_playwright: bool = False):
        self.session = self._create_session()
        self.delay = delay
        self.use_playwright = use_playwright and SCRAPING_CONFIG.get("use_playwright", False)
        self._playwright = None
        self._browser = None
        self.cache_dir = DATA_DIR / "amazon_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def _get_playwright_browser(self):
        if self._browser:
            return self._browser
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=SCRAPING_CONFIG.get("headless", True)
            )
        except ImportError:
            self.use_playwright = False
        return self._browser

    async def _close_playwright(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._browser = None
        self._playwright = None

    async def _fetch_with_playwright(self, url: str) -> Optional[str]:
        browser = await self._get_playwright_browser()
        if not browser:
            return None
        try:
            context = await browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                locale="en-IN",
                viewport={"width": 1920, "height": 1080},
            )
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)
            html = await page.content()
            await context.close()
            return html
        except Exception as e:
            print(f"    [WARN] Playwright fetch failed: {e}")
            return None

    def _create_session(self):
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7,hi;q=0.6",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        }
        if hasattr(self, 'session') and self.session:
            return self.session
        sess = get_session()
        sess.headers.update(headers)
        return sess

    def _rotate_user_agent(self):
        self.session.headers.update({"User-Agent": random.choice(USER_AGENTS)})

    def _rate_limit(self):
        jitter = random.uniform(0.5, 1.5)
        time.sleep(self.delay * jitter)

    def _cache_path(self, key: str) -> Path:
        safe = re.sub(r"[^a-z0-9_]", "_", key.lower())
        return self.cache_dir / f"{safe}.json"

    def _load_cache(self, key: str) -> Optional[dict]:
        path = self._cache_path(key)
        try:
            return load_json(path)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def _save_cache(self, key: str, data: dict):
        save_json(data, self._cache_path(key))

    def search(self, query: str, max_results: int = 10) -> list[dict]:
        cache_key = f"search_{query.lower().replace(' ', '_')}"
        cached = self._load_cache(cache_key)
        if cached and len(cached.get("results", [])) >= max_results:
            return cached["results"]

        self._rotate_user_agent()
        url = self.SEARCH_URL.format(query=quote(query))
        html = fetch_page(url, self.session)
        if not html:
            return []

        results = self._parse_search_results(html, max_results)
        self._save_cache(cache_key, {"results": results, "query": query})
        self._rate_limit()
        return results

    def _parse_search_results(self, html: str, max_results: int) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        results = []

        for card in soup.select("[data-component-type='s-search-result'], .s-result-item"):
            asin = card.get("data-asin", "")
            if not asin:
                continue

            title_el = card.select_one(".a-text-normal, h2 a, span[class*='title'] a")
            title = title_el.get_text(strip=True) if title_el else ""
            if not title or "sponsored" in title.lower():
                continue

            price_el = card.select_one(".a-price .a-offscreen, .a-price-whole")
            price = None
            if price_el:
                try:
                    price = float(re.sub(r"[^\d.]", "", price_el.get_text(strip=True)))
                except ValueError:
                    pass

            rating_el = card.select_one("[class*='rating'] i, .a-icon-star, .a-icon-alt")
            rating = None
            if rating_el:
                text = rating_el.get_text(strip=True) or rating_el.get("alt", "") or rating_el.get("aria-label", "")
                match = re.search(r"([\d.]+)", text)
                if match:
                    try:
                        rating = float(match.group(1))
                    except ValueError:
                        pass

            reviews_el = card.select_one("[class*='rating'] ~ .a-size-small, .a-size-small, [class*='rating'] + *")
            review_count = 0
            if reviews_el:
                match = re.search(r"(\d+)", reviews_el.get_text(strip=True).replace(",", ""))
                if match:
                    review_count = int(match.group(1))

            image_el = card.select_one("img.s-image")
            image = image_el.get("src", "") if image_el else ""

            results.append({
                "asin": asin,
                "title": title,
                "price": price,
                "rating": rating,
                "review_count": review_count,
                "image": image,
                "url": self.PRODUCT_URL.format(asin=asin),
            })

            if len(results) >= max_results:
                break

        return results

    def get_product_details(self, asin: str, use_playwright: bool = False) -> Optional[dict]:
        cache_key = f"product_{asin}"
        cached = self._load_cache(cache_key)
        if cached:
            return cached

        html = None
        if use_playwright and self.use_playwright:
            import asyncio
            html = asyncio.run(self._fetch_with_playwright(self.PRODUCT_URL.format(asin=asin)))
        if not html:
            self._rotate_user_agent()
            html = fetch_page(self.PRODUCT_URL.format(asin=asin), self.session)

        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")
        result = self._parse_product_page(soup, asin, self.PRODUCT_URL.format(asin=asin))
        if result:
            self._save_cache(cache_key, result)
        self._rate_limit()
        return result

    def _parse_product_page(self, soup: BeautifulSoup, asin: str, url: str) -> dict:
        data = {
            "asin": asin,
            "url": url,
            "title": "",
            "brand": "",
            "price": None,
            "mrp": None,
            "rating": None,
            "review_count": 0,
            "description": "",
            "features": [],
            "images": [],
            "bestseller_rank": None,
            "reviews": [],
        }

        title_el = soup.select_one("#productTitle, [class*='product-title']")
        if title_el:
            data["title"] = title_el.get_text(strip=True)

        brand_el = soup.select_one("#bylineInfo, [class*='brand'], a[href*='brand_stores']")
        if brand_el:
            data["brand"] = brand_el.get_text(strip=True).replace("Visit the ", "").replace(" Store", "")

        price_el = soup.select_one(".a-price .a-offscreen, #priceblock_ourprice, .a-price-whole")
        if price_el:
            try:
                data["price"] = float(re.sub(r"[^\d.]", "", price_el.get_text(strip=True)))
            except ValueError:
                pass

        mrp_el = soup.select_one(".a-text-price .a-offscreen, .priceBlockStrikePriceString")
        if mrp_el:
            try:
                data["mrp"] = float(re.sub(r"[^\d.]", "", mrp_el.get_text(strip=True)))
            except ValueError:
                pass

        rating_el = soup.select_one("i.a-icon-star .a-icon-alt, [data-hook='rating-out-of-text']")
        if rating_el:
            match = re.search(r"([\d.]+)", rating_el.get_text(strip=True))
            if match:
                try:
                    data["rating"] = float(match.group(1))
                except ValueError:
                    pass

        count_el = soup.select_one("#acrCustomerReviewText, [data-hook='total-review-count']")
        if count_el:
            match = re.search(r"([\d,]+)", count_el.get_text(strip=True))
            if match:
                data["review_count"] = int(match.group(1).replace(",", ""))

        desc_el = soup.select_one("#productDescription, [data-feature-name='productDescription']")
        if desc_el:
            data["description"] = desc_el.get_text(strip=True)

        for feat in soup.select("#feature-bullets li, .a-unordered-list li"):
            text = feat.get_text(strip=True)
            if text and len(text) > 5:
                data["features"].append(text)

        for img in soup.select("#imgTagWrapperId img, .a-dynamic-image"):
            src = img.get("src", "") or img.get("data-old-hires", "")
            if src and src not in data["images"]:
                data["images"].append(src)

        rank_el = soup.select_one("#productDetails_detailBullets_sections1 tr:has(th:contains('Rank')) td")
        if rank_el:
            data["bestseller_rank"] = rank_el.get_text(strip=True)

        # Parse server-rendered reviews from product page
        for card in soup.select("#cm-cr-dp-review-list .review, [data-hook='review'], .a-section.review"):
            try:
                title_el = card.select_one("[data-hook='review-title'], .review-title")
                body_el = card.select_one("[data-hook='review-body'], .review-text")
                rating_el = card.select_one("[data-hook='review-star-rating'], i.a-icon-star")
                author_el = card.select_one("[data-hook='review-author'], .a-profile-name")
                date_el = card.select_one("[data-hook='review-date'], .review-date")
                verified_el = card.select_one("[data-hook='avp-badge'], .verified-purchase")
                rating = None
                if rating_el:
                    match = re.search(r"([\d.]+)", rating_el.get_text(strip=True))
                    if match:
                        try:
                            rating = float(match.group(1))
                        except ValueError:
                            pass
                data["reviews"].append({
                    "title": title_el.get_text(strip=True) if title_el else "",
                    "body": body_el.get_text(strip=True) if body_el else "",
                    "rating": rating,
                    "author": author_el.get_text(strip=True) if author_el else "",
                    "date": date_el.get_text(strip=True) if date_el else None,
                    "verified": verified_el is not None,
                })
            except Exception:
                continue

        if data.get("reviews"):
            data["review_count"] = max(data.get("review_count", 0), len(data["reviews"]))

        return data

    def get_reviews(self, asin: str, max_pages: int = 3) -> list[dict]:
        cache_key = f"reviews_{asin}"
        cached = self._load_cache(cache_key)
        if cached and len(cached.get("reviews", [])) > 0:
            return cached["reviews"]

        all_reviews = []

        # Strategy 1: Try reviews JSON endpoint
        try:
            json_url = f"https://www.amazon.in/gp/customer-reviews/widgets/average-customer-review/popover/?ie=UTF8&asin={asin}&context=detail"
            self._rotate_user_agent()
            resp = self.session.get(json_url, timeout=10)
            if resp.status_code == 200 and resp.text.strip():
                json_soup = BeautifulSoup(resp.text, "html.parser")
                review_links = json_soup.select("a[href*='/product-reviews/']")
                if review_links:
                    pass  # JSON HTML contains review link, actual reviews need Playwright
        except Exception:
            pass

        # Strategy 2: Try Playwright for JS-rendered reviews
        if self.use_playwright:
            import asyncio
            for page in range(1, max_pages + 1):
                pw_url = f"{self.REVIEWS_URL.format(asin=asin)}?pageNumber={page}"
                pw_html = asyncio.run(self._fetch_with_playwright(pw_url))
                if pw_html:
                    pw_reviews = self._parse_reviews_page(pw_html)
                    all_reviews.extend(pw_reviews)
                    if len(pw_reviews) < 10:
                        break
                else:
                    break
            if all_reviews:
                self._save_cache(cache_key, {"reviews": all_reviews, "asin": asin})
                return all_reviews

        # Strategy 3: Try non-JS versions (most Amazon review pages require JS now)
        for page in range(1, max_pages + 1):
            self._rotate_user_agent()
            page_url = f"{self.REVIEWS_URL.format(asin=asin)}?pageNumber={page}"
            html = fetch_page(page_url, self.session)
            if not html:
                break
            reviews = self._parse_reviews_page(html)
            all_reviews.extend(reviews)
            self._rate_limit()
            if len(reviews) < 10:
                break

        if all_reviews:
            self._save_cache(cache_key, {"reviews": all_reviews, "asin": asin})
        return all_reviews

    def _parse_reviews_page(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        reviews = []

        for card in soup.select("[data-hook='review'], .review, [class*='review-']"):
            try:
                title_el = card.select_one("[data-hook='review-title'], .review-title")
                body_el = card.select_one("[data-hook='review-body'], .review-text")
                rating_el = card.select_one("[data-hook='review-star-rating'], i.a-icon-star")
                author_el = card.select_one("[data-hook='review-author'], .a-profile-name")
                date_el = card.select_one("[data-hook='review-date'], .review-date")
                verified_el = card.select_one("[data-hook='avp-badge'], .verified-purchase")
                helpful_el = card.select_one("[data-hook='helpful-vote'], .cr-vote-text")

                rating = None
                if rating_el:
                    match = re.search(r"([\d.]+)", rating_el.get_text(strip=True))
                    if match:
                        try:
                            rating = float(match.group(1))
                        except ValueError:
                            pass

                helpful_count = 0
                if helpful_el:
                    match = re.search(r"(\d+)", helpful_el.get_text(strip=True))
                    if match:
                        helpful_count = int(match.group(1))

                reviews.append({
                    "title": title_el.get_text(strip=True) if title_el else "",
                    "body": body_el.get_text(strip=True) if body_el else "",
                    "rating": rating,
                    "author": author_el.get_text(strip=True) if author_el else "",
                    "date": date_el.get_text(strip=True) if date_el else None,
                    "verified": verified_el is not None,
                    "votes_helpful": helpful_count,
                })
            except Exception:
                continue

        return reviews

    def enrich_product(self, product: PerfumeProduct) -> PerfumeProduct:
        query = f"{product.brand} {product.name}".strip()
        if not query:
            return product

        results = self.search(query, max_results=3)
        if not results:
            return product

        best = results[0]
        asin = best.get("asin", "")
        if not asin:
            return product

        details = self.get_product_details(asin, use_playwright=self.use_playwright)
        if details:
            # Extract notes from Amazon product features/description
            from ..utils import extract_notes_from_features, extract_notes_from_text
            amazon_notes = extract_notes_from_features(details.get("features", []))
            if not amazon_notes.get("top"):
                amazon_notes = extract_notes_from_text(details.get("description", ""))
            existing = product.notes
            if amazon_notes.get("top") and not (existing.top_notes if hasattr(existing, 'top_notes') else []):
                if hasattr(existing, 'top_notes'):
                    existing.top_notes = [n for n in amazon_notes["top"] if n not in existing.top_notes]
            if amazon_notes.get("middle") and not (existing.middle_notes if hasattr(existing, 'middle_notes') else []):
                if hasattr(existing, 'middle_notes'):
                    existing.middle_notes = [n for n in amazon_notes["middle"] if n not in existing.middle_notes]
            if amazon_notes.get("base") and not (existing.base_notes if hasattr(existing, 'base_notes') else []):
                if hasattr(existing, 'base_notes'):
                    existing.base_notes = [n for n in amazon_notes["base"] if n not in existing.base_notes]
            if details.get("price") and not product.prices:
                from ..models import PriceEntry
                product.prices.append(PriceEntry(
                    mrp=details.get("mrp") or details["price"],
                    discount_price=details["price"] if details.get("mrp") else None,
                    currency="INR",
                    url=details["url"],
                    source="amazon",
                ))
            if details.get("rating") and not product.rating:
                product.rating = details["rating"]
            if details.get("images"):
                product.images = list(dict.fromkeys(product.images + details["images"]))
            # Reviews from product page (server-rendered)
            if details.get("reviews"):
                existing_bodies = {r.body[:100] for r in product.reviews}
                for rv in details["reviews"]:
                    if rv["body"] and rv["body"][:100] not in existing_bodies:
                        product.reviews.append(ReviewData(
                            source="amazon",
                            title=rv.get("title", ""),
                            body=rv["body"],
                            rating=rv.get("rating"),
                            author=rv.get("author", ""),
                            date=rv.get("date"),
                            verified=rv.get("verified", False),
                        ))
                        existing_bodies.add(rv["body"][:100])

        # More reviews from dedicated reviews page (JS-rendered, needs Playwright)
        reviews_data = self.get_reviews(asin, max_pages=2)
        if reviews_data:
            existing_bodies = {r.body[:100] for r in product.reviews}
            for rv in reviews_data:
                if rv["body"] and rv["body"][:100] not in existing_bodies:
                    product.reviews.append(ReviewData(
                        source="amazon",
                        title=rv.get("title", ""),
                        body=rv["body"],
                        rating=rv.get("rating"),
                        author=rv.get("author", ""),
                        date=rv.get("date"),
                        verified=rv.get("verified", False),
                        votes_helpful=rv.get("votes_helpful", 0),
                    ))
                    existing_bodies.add(rv["body"][:100])

        return product

    def _safe_print(self, msg: str):
        try:
            print(msg)
        except UnicodeEncodeError:
            print(msg.encode('ascii', errors='replace').decode('ascii'))

    def enrich_many(self, products: list[PerfumeProduct]) -> list[PerfumeProduct]:
        for i, product in enumerate(products):
            self._safe_print(f"  Amazon [{i+1}/{len(products)}] {product.brand} - {product.name}")
            try:
                self.enrich_product(product)
            except Exception as e:
                self._safe_print(f"    [WARN] Failed: {e}")
        return products
