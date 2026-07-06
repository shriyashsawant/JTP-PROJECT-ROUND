import re
import json
import time
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .models import PerfumeProduct, PriceEntry, NoteProfile
from .utils import (
    fetch_page, get_session, extract_price, extract_ml,
    extract_concentration, extract_notes, clean_html,
    save_json, generate_id,
)
from .config import RAW_DIR, SCRAPING_CONFIG
from .brands import BRAND_CONFIGS


class BrandScraper:
    def __init__(self, brand_key: str):
        self.brand_key = brand_key
        self.config = BRAND_CONFIGS[brand_key]
        self.session = get_session()
        self.products: list[PerfumeProduct] = []

    def scrape(self, deep: bool = False) -> list[PerfumeProduct]:
        print(f"[{self.config['name']}] Starting scrape...")
        method = self.config.get("scrape_method", "html")

        if method == "products_json":
            self._scrape_via_products_json()
        elif method == "html":
            self._scrape_via_html()
        else:
            print(f"  Unknown method '{method}', falling back to HTML")
            self._scrape_via_html()

        if deep and self.products:
            self._deep_scrape_products()

        if self.products:
            output_path = RAW_DIR / f"{self.brand_key}.json"
            data = [p.model_dump() for p in self.products]
            save_json(data, output_path)
            print(f"  Saved {len(self.products)} products to {output_path}")

        return self.products

    # ── Deep scrape: visit each product page for richer data ──

    def _deep_scrape_products(self):
        print(f"  Deep-scraping {len(self.products)} product pages for rich data...")
        for i, product in enumerate(self.products):
            url = product.source_url
            if not url:
                continue
            if i % 10 == 0 and i > 0:
                print(f"    Deep-scraped {i}/{len(self.products)}")
            time.sleep(SCRAPING_CONFIG["request_delay"] / 2)
            try:
                self._deep_scrape_product_page(product, url)
            except Exception as e:
                pass

    def _deep_scrape_product_page(self, product: PerfumeProduct, url: str):
        if "lipstick" in url.lower() or "eyebrow" in url.lower() or "soap" in url.lower():
            return

        html = fetch_page(url, self.session)
        if not html:
            return
        soup = BeautifulSoup(html, "html.parser")

        # Extract description from the dedicated description section only
        desc = ""
        for sel in [".product__description", ".product-single__description",
                     ".product-description", ".description", ".rte",
                     "[data-product-description]", ".product-info__description",
                     ".tab-content", ".accordion-content"]:
            el = soup.select_one(sel)
            if el:
                text = el.get_text(strip=True)
                if len(text) > 30:
                    desc = text
                    break

        # Fallback: JSON-LD description
        if not desc:
            jsonld = re.findall(
                r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
                html, re.DOTALL | re.IGNORECASE
            )
            for block in jsonld:
                try:
                    data = json.loads(block)
                    if isinstance(data, dict) and data.get("@type") == "Product":
                        desc = data.get("description", "")
                        if desc:
                            break
                except json.JSONDecodeError:
                    pass

        if not desc or len(desc) < 20:
            return

        if len(desc) > len(product.description):
            product.description = clean_html(desc)

        # Extract notes only from description text (not full page)
        desc_lower = desc.lower()
        all_notes = extract_notes(desc)

        # Try structured note pyramid
        top = self._extract_section(desc,
            r"(?:top|head|opening)\s*notes?\s*:?\s*(.*?)(?:middle|heart|base|drydown|\n)")
        middle = self._extract_section(desc,
            r"(?:middle|heart)\s*notes?\s*:?\s*(.*?)(?:base|drydown|bottom|\n)")
        base = self._extract_section(desc,
            r"(?:base|bottom|drydown|dry\s*down)\s*notes?\s*:?\s*(.*?)(?:\n|$)")

        # Story pattern: "starts with X, moves into Y, settles into Z"
        if not any([top, middle, base]):
            story = re.search(
                r"(?:starts?|opens?|begins?)\s*(?:with|as)\s*(.*?)(?:,|\s+then\s+|\s+moves?\s+|\s+transitions?\s+)"
                r"(.*?)(?:,|\s+before\s+|\s+and\s+|\s+settles?\s+|\s+dries?\s+)"
                r"(.*?)(?:\.|$)",
                desc, re.IGNORECASE | re.DOTALL
            )
            if story:
                top = story.group(1).strip()
                middle = story.group(2).strip()
                base = story.group(3).strip()

        if top:
            product.notes.top_notes = extract_notes(top)
        if middle:
            product.notes.middle_notes = extract_notes(middle)
        if base:
            product.notes.base_notes = extract_notes(base)

        # Fallback note split
        if not any([product.notes.top_notes, product.notes.middle_notes, product.notes.base_notes]) and all_notes:
            mid = len(all_notes) // 3
            product.notes.top_notes = all_notes[:mid]
            product.notes.middle_notes = all_notes[mid:2*mid] if 2*mid < len(all_notes) else all_notes[mid:]
            product.notes.base_notes = all_notes[2*mid:] if 2*mid < len(all_notes) else []

        # Accords from description
        re_extracted = self._extract_accords_from_text(desc)
        if re_extracted:
            product.accords = list(dict.fromkeys(product.accords + re_extracted))

        # Opening / drydown
        om = re.search(r"(?:opening|first\s*impression)\s*[:\-]?\s*(.*?)(?:\.|heart|middle|\Z)", desc, re.IGNORECASE | re.DOTALL)
        if om and not product.opening:
            product.opening = om.group(1).strip()[:100]

        dm = re.search(r"(?:dry\s*down|drydown)\s*[:\-]?\s*(.*?)(?:\.|\Z)", desc, re.IGNORECASE | re.DOTALL)
        if dm and not product.drydown:
            product.drydown = dm.group(1).strip()[:100]

        # Gender from description
        g = self._detect_gender(desc_lower)
        if g and not product.gender:
            product.gender = g

        # Concentration
        c = extract_concentration(desc_lower)
        if c and not product.concentration:
            product.concentration = c

    FRAGRANCE_KEYWORDS = [
        "perfume", "eau de", "edp", "edt", "cologne", "fragrance",
        "attar", "ittar", "body mist", "deodorant", "spray",
        "oud", "musk", "scent",
    ]
    NON_FRAGRANCE_KEYWORDS = [
        "lipstick", "lip gloss", "eyebrow", "eyelash", "soap",
        "shower gel", "sunscreen", "moisturizer", "serum",
        "shampoo", "conditioner", "face wash", "cream", "lotion",
        "makeup", "foundation", "concealer", "powder", "blush",
        "nail", "comb", "brush", "towel", "gift card",
    ]

    def _is_fragrance_product(self, item: dict) -> bool:
        title = (item.get("title", "") or "").lower()
        ptype = (item.get("product_type", "") or "").lower()
        body = (item.get("body_html", "") or "").lower()
        raw_tags = item.get("tags", [])
        if isinstance(raw_tags, str):
            tags_text = raw_tags.lower()
        elif isinstance(raw_tags, list):
            tags_text = " ".join(t.lower() for t in raw_tags)
        else:
            tags_text = ""

        combined = f"{title} {ptype} {tags_text} {body[:200]}"

        # Quick reject: explicit non-fragrance product type or title
        if any(kw in title or kw in ptype for kw in self.NON_FRAGRANCE_KEYWORDS):
            return False

        # Accept: explicit fragrance keyword match
        if any(kw in combined for kw in self.FRAGRANCE_KEYWORDS):
            return True

        # Accept: product type clearly indicates fragrance
        fragrance_types = ["perfume", "eau de parfum", "eau de toilette", "cologne",
                           "attar", "body mist", "deodorant", "edp", "edt"]
        if any(ft in ptype.lower() for ft in fragrance_types):
            return True

        return False

    # ── Shopify /products.json scraper (stable, no CSS selectors) ──

    def _scrape_via_products_json(self):
        base_url = self.config["website"].rstrip("/")
        products_path = self.config.get("products_json", "/products.json?limit=250")
        json_url = base_url + products_path

        print(f"  Fetching Shopify JSON: {json_url}")
        html = fetch_page(json_url, self.session)
        if not html:
            print(f"  Failed to fetch {json_url}, falling back to HTML...")
            self.config["scrape_method"] = "html"
            self._scrape_via_html()
            return

        try:
            data = json.loads(html)
        except json.JSONDecodeError:
            print(f"  Invalid JSON from {json_url} (got HTML instead), falling back to HTML...")
            self.config["scrape_method"] = "html"
            self._scrape_via_html()
            return

        products_list = data.get("products", [])
        print(f"  Found {len(products_list)} products in JSON feed")

        filtered = [p for p in products_list if self._is_fragrance_product(p)]
        skipped = len(products_list) - len(filtered)
        if skipped:
            print(f"  Filtered out {skipped} non-fragrance products")

        for item in filtered:
            try:
                product = self._parse_shopify_product(item)
                if product:
                    self.products.append(product)
            except Exception as e:
                print(f"  Error parsing product: {e}")

    def _parse_shopify_product(self, item: dict) -> Optional[PerfumeProduct]:
        title = item.get("title", "")
        handle = item.get("handle", "")
        product_url = f"{self.config['website'].rstrip('/')}/products/{handle}"

        product = PerfumeProduct(
            brand=self.config["name"],
            name=title,
            source_url=product_url,
        )

        body_html = item.get("body_html", "") or ""
        product.description = clean_html(body_html)

        product_type = item.get("product_type", "") or ""
        if product_type:
            product.category = product_type

        vendor = item.get("vendor", "")
        raw_tags = item.get("tags", "")
        if isinstance(raw_tags, list):
            product.tags = [t.strip() for t in raw_tags if t and t.strip()]
        elif isinstance(raw_tags, str):
            product.tags = [t.strip() for t in raw_tags.split(",") if t.strip()]

        desc_text = body_html + " " + product_type + " " + " ".join(product.tags)
        all_notes = extract_notes(desc_text)
        product.notes = self._classify_notes_from_text(desc_text, all_notes)
        product.accords = self._extract_accords_from_text(desc_text)

        # Concentration: check title, product_type, body_html
        conc = extract_concentration(title + " " + product_type + " " + body_html)
        if conc:
            product.concentration = conc

        # Parse images
        images = item.get("images", [])
        for img in images:
            src = img.get("src", "")
            if src:
                product.images.append(src)

        # Parse variants (prices, sizes, etc.)
        variants = item.get("variants", [])
        for v in variants:
            price = v.get("price")
            compare_price = v.get("compare_at_price")
            ml = None

            v_title = v.get("title", "").lower()
            if "ml" in v_title:
                ml = extract_ml(v_title)

            if not ml:
                gram_match = re.search(r"(\d+)\s*(ml|g)", v_title, re.IGNORECASE)
                if gram_match:
                    ml = int(gram_match.group(1))

            price_entry = PriceEntry(
                mrp=extract_price(str(compare_price)) if compare_price else None,
                discount_price=extract_price(str(price)) if price else None,
                size_ml=ml,
                url=product_url,
                source=self.config["name"],
            )
            if price_entry.mrp or price_entry.discount_price:
                product.prices.append(price_entry)

        # Gender from title, product_type, body_html, tags
        all_text = (title + " " + product_type + " " + body_html + " " + vendor + " " + " ".join(product.tags)).lower()
        all_text_lax = " " + all_text.replace("(", " ").replace(")", " ").replace("-", " ") + " "
        male_kw = ["for men", "men's", "for him", " him ", "male", "homme", "man", "gentleman", "(him)", "(men)", "for him"]
        female_kw = ["for women", "women's", "for her", " her ", "female", "femme", "woman", "lady", "(her)", "(women)", "for ladies", "(she)"]
        if any(kw in all_text or kw in all_text_lax for kw in male_kw):
            product.gender = "male"
        elif any(kw in all_text or kw in all_text_lax for kw in female_kw):
            product.gender = "female"
        elif any(kw in all_text or kw in all_text_lax for kw in ["unisex", "universal"]):
            product.gender = "unisex"

        # Opening / drydown from description
        opening_m = re.search(r"(?:opening|top|head)\s*notes?\s*:?\s*(.*?)(?:\.|,|heart|middle|base)", desc_text, re.IGNORECASE | re.DOTALL)
        if not opening_m:
            opening_m = re.search(
                r"(?:(?:starts?|opens?|begins?|bursts?\s+open)\s*(?:with|as)|first\s+(?:spritz|blast|impression))\s*(.*?)(?:,|\s+then\s+|\s+moves?\s+|\s+and\s+|\s+transitions?\s+|\s+reveals?\s+)",
                desc_text, re.IGNORECASE | re.DOTALL
            )
        if not opening_m:
            opening_m = re.search(r"(?:opens?\s+up\s+to|unveils?)\s*(.*?)(?:\.|,)", desc_text, re.IGNORECASE | re.DOTALL)
        if opening_m:
            product.opening = opening_m.group(1).strip()[:100]

        drydown_m = re.search(r"(?:base|drydown|dry down|bottom)\s*notes?\s*:?\s*(.*?)(?:\.|$)", desc_text, re.IGNORECASE | re.DOTALL)
        if not drydown_m:
            drydown_m = re.search(r"(?:settles?\s+(?:into|down)|dries?\s+down\s+to)\s*(.*?)(?:\.|$)", desc_text, re.IGNORECASE | re.DOTALL)
        if not drydown_m:
            drydown_m = re.search(r"(?:leaves?\s+(?:behind|a\s+trail\s+of|you\s+with))\s*(.*?)(?:\.|$)", desc_text, re.IGNORECASE | re.DOTALL)
        if drydown_m:
            product.drydown = drydown_m.group(1).strip()[:100]

        # Launch year
        yr_m = re.search(r"\b(19|20)\d{2}\b", all_text)
        if yr_m:
            yr = int(yr_m.group(0))
            if 1950 <= yr <= 2026:
                product.launch_year = str(yr)

        # Rating from JSON if available
        rating = item.get("rating")
        if rating:
            try:
                product.rating = float(rating)
            except (ValueError, TypeError):
                pass

        return product

    # ── HTML scraper (for non-Shopify sites) ──

    def _scrape_via_html(self):
        base_url = self.config["website"].rstrip("/")
        urls = []

        collections = self.config.get("collections", [])
        if collections:
            for col in collections:
                url = f"{base_url}/collections/{col}"
                urls.append(url)
        else:
            fallback_urls = self.config.get("collection_urls", [f"{base_url}/collections/all"])
            urls.extend(fallback_urls)

        discovered = set()
        for url in urls:
            print(f"  Fetching collection: {url}")
            html = fetch_page(url, self.session)
            if not html:
                continue

            soup = BeautifulSoup(html, "html.parser")
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if "/products/" in href:
                    full = urljoin(base_url, href)
                    discovered.add(full)

        print(f"  Found {len(discovered)} product URLs")
        for pu in discovered:
            time.sleep(SCRAPING_CONFIG["request_delay"])
            try:
                product = self._scrape_product_html(pu)
                if product:
                    self.products.append(product)
            except Exception as e:
                print(f"  Error scraping {pu}: {e}")

    def _scrape_product_html(self, url: str) -> Optional[PerfumeProduct]:
        html = fetch_page(url, self.session)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")
        product = PerfumeProduct(brand=self.config["name"], source_url=url)

        product.name = self._text(soup, "h1, .product-title, .product__title, [data-product-title]")
        product.description = clean_html(
            str(soup.select_one(".product-description, .product__description, .product-single__description, .description")) or ""
        )
        product.category = self._text(soup, ".product-type, .product__type")
        product.collection = self._text(soup, ".product-collection, .collection, .product__collection")

        all_text = soup.get_text()
        product.tags = self._collect_tags(soup)
        desc_text = product.description + " " + " ".join(product.tags)
        all_notes = extract_notes(desc_text)
        product.notes = self._classify_notes_from_text(desc_text, all_notes)
        product.accords = self._extract_accords_from_text(desc_text)
        product.concentration = extract_concentration(desc_text)

        product.gender = self._detect_gender(all_text)
        product.launch_year = self._detect_year(all_text)

        product.opening = self._extract_section(desc_text, r"(?:opening|top|head)\s*notes?\s*:?\s*(.*?)(?:\.|,|heart|middle|base)")
        product.drydown = self._extract_section(desc_text, r"(?:base|drydown|dry down|bottom)\s*notes?\s*:?\s*(.*?)(?:\.|$)")

        # Prices
        for sel in [".price .price--sale .price-item--sale", ".price .price-item--sale",
                     ".price .price--compare", ".product__price .price", ".price"]:
            el = soup.select_one(sel)
            if el:
                val = extract_price(el.get_text(strip=True))
                if val:
                    ml = extract_ml(all_text)
                    product.prices.append(PriceEntry(discount_price=val, size_ml=ml, url=url, source=self.config["name"]))
                    break

        compare = soup.select_one(".price--compare, .price__compare, .compare-price, meta[property='product:price:amount']")
        if compare:
            raw = compare.get("content", compare.get_text(strip=True))
            val = extract_price(raw)
            if val:
                if not product.prices:
                    product.prices.append(PriceEntry(mrp=val, url=url, source=self.config["name"]))
                elif not product.prices[0].mrp:
                    product.prices[0].mrp = val

        product.images = self._collect_images(soup, url)
        rating = self._extract_rating(soup)
        if rating:
            product.rating = rating

        return product

    # ── Shared helpers ──

    def _text(self, soup: BeautifulSoup, selector: str) -> str:
        el = soup.select_one(selector)
        return el.get_text(strip=True) if el else ""

    def _collect_tags(self, soup: BeautifulSoup) -> list[str]:
        tags = []
        for sel in [".product-tags span, .product-tags a", ".tags span, .tags a", ".product__tags span"]:
            for el in soup.select(sel):
                t = el.get_text(strip=True)
                if t:
                    tags.append(t)
        meta = soup.select_one("meta[name='keywords']")
        if meta and meta.get("content"):
            tags.extend(k.strip() for k in meta["content"].split(","))
        return tags

    def _collect_images(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        images = []
        for sel in [
            "img[data-product-featured-image]", ".product-single__photo img",
            ".product__photo img", ".product-gallery__image img", "img[src*='products']",
        ]:
            for img in soup.select(sel):
                src = img.get("src") or img.get("data-src") or ""
                if src and "placeholder" not in src.lower():
                    full = urljoin(base_url, src)
                    if full not in images:
                        images.append(full)
        return images[:5]

    def _detect_gender(self, text: str) -> Optional[str]:
        t = text.lower()
        if "for men" in t or "men's" in t or "male" in t or "homme" in t:
            return "male"
        if "for women" in t or "women's" in t or "female" in t or "femme" in t:
            return "female"
        if "unisex" in t:
            return "unisex"
        return None

    def _detect_year(self, text: str) -> Optional[str]:
        matches = re.findall(r"\b(19|20)\d{2}\b", text)
        for m in matches:
            yr = int(m)
            if 1950 <= yr <= 2026:
                return str(yr)
        return None

    def _extract_rating(self, soup: BeautifulSoup) -> Optional[float]:
        for sel in [".rating .average", ".rating span", "[itemprop='ratingValue']",
                     ".product-rating", ".ruk_rating_snippet"]:
            el = soup.select_one(sel)
            if el:
                raw = el.get("content", el.get_text(strip=True))
                try:
                    val = float(re.sub(r"[^\d.]", "", raw))
                    return val / 10 if val > 10 else val
                except (ValueError, TypeError):
                    continue
        return None

    def _extract_section(self, text: str, pattern: str) -> Optional[str]:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        return match.group(1).strip() if match else None

    def _classify_notes_from_text(self, text: str, all_notes: list[str]) -> NoteProfile:
        top = extract_notes(
            self._extract_section(text, r"(?:top|head|opening)\s*notes?\s*:?\s*(.*?)(?:middle|heart|base|drydown)") or ""
        )
        middle = extract_notes(
            self._extract_section(text, r"(?:middle|heart)\s*notes?\s*:?\s*(.*?)(?:base|drydown|bottom)") or ""
        )
        base = extract_notes(
            self._extract_section(text, r"(?:base|bottom|drydown)\s*notes?\s*:?\s*(.*?)(?:\n\n|$)") or ""
        )

        if not any([top, middle, base]) and all_notes:
            mid = len(all_notes) // 3
            top = all_notes[:mid]
            middle = all_notes[mid:2*mid] if 2*mid < len(all_notes) else all_notes[mid:]
            base = all_notes[2*mid:] if 2*mid < len(all_notes) else []

        return NoteProfile(top_notes=top, middle_notes=middle, base_notes=base)

    def _extract_accords_from_text(self, text: str) -> list[str]:
        text_lower = text.lower()
        accord_map = {
            "woody": ["woody", "woodsy", "sandalwood", "cedarwood"],
            "citrus": ["citrus", "bergamot", "lemon", "orange", "grapefruit"],
            "floral": ["floral", "rose", "jasmine", "lavender", "ylang"],
            "fresh": ["fresh", "aquatic", "marine", "ozonic", "clean"],
            "spicy": ["spicy", "cardamom", "cinnamon", "pepper", "clove", "nutmeg"],
            "sweet": ["sweet", "vanilla", "gourmand", "caramel", "honey"],
            "earthy": ["earthy", "patchouli", "vetiver", "oakmoss", "moss"],
            "leather": ["leather", "leathery"],
            "oriental": ["oriental", "amber", "incense", "resin"],
            "powdery": ["powdery", "iris", "violet", "musk"],
            "fruity": ["fruity", "apple", "berry", "peach", "pineapple"],
            "green": ["green", "grass", "galbanum", "violet leaf"],
            "aromatic": ["aromatic", "herbal", "sage", "rosemary"],
            "gourmand": ["gourmand", "edible", "chocolate", "coffee"],
            "aldehydic": ["aldehyde", "aldehydic", "soapy"],
            "tobacco": ["tobacco", "smoky"],
        }
        accords = []
        for accord, keywords in accord_map.items():
            if any(kw in text_lower for kw in keywords):
                accords.append(accord)
        return accords


def scrape_brand(brand_key: str, deep: bool = False) -> list[PerfumeProduct]:
    scraper = BrandScraper(brand_key)
    return scraper.scrape(deep=deep)


def scrape_all_brands(brand_keys: Optional[list[str]] = None, deep: bool = False):
    from .brands import BRAND_CONFIGS
    if brand_keys is None:
        brand_keys = list(BRAND_CONFIGS.keys())

    all_products = []
    for key in brand_keys:
        try:
            products = scrape_brand(key, deep=deep)
            all_products.extend(products)
        except Exception as e:
            print(f"[ERROR] Failed to scrape {key}: {e}")

    if all_products:
        combined = RAW_DIR / "_all_brands_combined.json"
        data = [p.model_dump() for p in all_products]
        save_json(data, combined)
        print(f"\nTotal: {len(all_products)} products saved to {combined}")

    return all_products
