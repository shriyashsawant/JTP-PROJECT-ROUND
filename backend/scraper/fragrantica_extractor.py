import sys, re, json, csv, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# ──────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────
BASE = "https://www.fragrantica.com"
CACHE = Path("backend/scraper/data/fragrantica_cache")
CACHE.mkdir(parents=True, exist_ok=True)
FETCHED = Path("backend/scraper/data/fragrantica_fetched")
FETCHED.mkdir(parents=True, exist_ok=True)

# ──────────────────────────────────────────────────
# STEP 1: Generate ALL entry URLs
# ──────────────────────────────────────────────────
COUNTRIES = [
    "Argentina", "Australia", "Austria", "Bahrain", "Bangladesh", "Belgium",
    "Brazil", "Bulgaria", "Canada", "Chile", "China", "Colombia", "Croatia",
    "Czech-Republic", "Denmark", "Egypt", "Estonia", "Finland", "France",
    "Germany", "Greece", "Hungary", "Iceland", "India", "Indonesia", "Iran",
    "Iraq", "Ireland", "Israel", "Italy", "Japan", "Jordan", "Kuwait",
    "Latvia", "Lebanon", "Lithuania", "Luxembourg", "Malaysia", "Mexico",
    "Monaco", "Morocco", "Myanmar", "Nepal", "Netherlands", "New-Zealand",
    "Nigeria", "Norway", "Oman", "Pakistan", "Peru", "Philippines",
    "Poland", "Portugal", "Qatar", "Romania", "Russia", "Saudi-Arabia",
    "Serbia", "Singapore", "Slovakia", "Slovenia", "South-Africa",
    "South-Korea", "Spain", "Sri-Lanka", "Sweden", "Switzerland", "Taiwan",
    "Thailand", "Tunisia", "Turkey", "Ukraine", "United-Arab-Emirates",
    "United-Kingdom", "United-States", "Vietnam", "Yemen",
]

# Known designer IDs for AJAX popularity endpoint
DESIGNER_IDS = {
    "Lattafa-Perfumes": 1979, "Maison-Alhambra": 12155, "Armaf": 3888,
    "Rasasi": 1302, "Ajmal-Perfumes": 3153, "Afnan": 4120,
    "Paris-Corner": 12976, "Fragrance-World": 13130,
    "Swiss-Arabian": 553, "Al-Haramain-Perfumes": 1367,
    "Ahmed-Al-Maghribi": 7783, "Bombay-Perfumery": 14241,
    "Fogg": 13526, "Al-Rehab": 1154, "Fueguia-1833": 3299,
}


def generate_urls():
    urls = []
    urls.append({"url": f"{BASE}/countries/", "type": "country-index", "stage": 0})
    for c in COUNTRIES:
        urls.append({"url": f"{BASE}/country/{c}.html", "type": "country", "slug": c, "stage": 0})
    return urls


def save_urls(urls, path=None):
    if path is None:
        path = Path(__file__).parent / "fragrantica_urls.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["url", "type", "slug", "stage"])
        w.writerows([[u["url"], u["type"], u.get("slug", ""), u["stage"]] for u in urls])
    print(f"Saved {len(urls)} URLs to {path}")


# ──────────────────────────────────────────────────
# STEP 2: PARSING functions (work on HTML)
# ──────────────────────────────────────────────────
def parse_country_brands(html: str) -> list[dict]:
    """Extract brand links from a country page."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    brands = []
    seen = set()
    for a in soup.select("a[href*='/designers/']"):
        href = a.get("href", "")
        name = a.get_text(strip=True)
        if not name or name in ("Designers",) or name in seen:
            continue
        seen.add(name)
        full_url = href if href.startswith("http") else f"{BASE}{href}"
        brands.append({"name": name, "url": full_url, "slug": href.split("/")[-1].replace(".html", "")})
    return brands


def parse_brand_perfumes(html: str) -> list[dict]:
    """Extract perfume links from a designer/brand page."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    perfumes = []
    seen = set()
    for a in soup.select("a[href*='/perfume/']"):
        href = a.get("href", "")
        key = href.lower().rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        full_url = href if href.startswith("http") else f"{BASE}{href}"
        name = a.get_text(strip=True) or a.get("title", "") or href.split("/")[-1].replace(".html", "").replace("-", " ")
        perfumes.append({"name": name.strip(), "url": full_url})
    return perfumes


def parse_perfume_detail(html: str, url: str = "") -> dict:
    """Extract full perfume detail from a perfume page."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    data = {
        "url": url,
        "name": "",
        "brand": "",
        "gender": None,
        "concentration": None,
        "description": "",
        "notes": {"top": [], "middle": [], "base": []},
        "accords": [],
        "longevity": None,
        "sillage": None,
        "projection": None,
        "ratings": {},
        "launch_year": None,
        "perfumers": [],
        "similar_perfumes": [],
    }

    # Name from title or h1
    title_el = soup.select_one("h1[itemprop='name'], h1")
    if title_el:
        data["name"] = title_el.get_text(strip=True)

    # Brand from breadcrumb or header
    brand_el = soup.select_one("a[href*='/designers/']")
    if brand_el:
        data["brand"] = brand_el.get_text(strip=True)

    # Notes pyramid — server rendered
    for level, cls in [("top", "pyramid-top"), ("middle", "pyramid-middle"), ("base", "pyramid-base")]:
        container = soup.select_one(f".{cls}")
        if container:
            notes = []
            for a in container.select("a.pyramid-note-link"):
                notes.append(a.get_text(strip=True))
            data["notes"][level] = notes

    # Fallback: Parse notes from meta description
    if not any(data["notes"].values()):
        meta = soup.select_one("meta[name='description']")
        if meta:
            desc = meta.get("content", "")
            m = re.search(r"Top notes are ([^;]+);?\s*middle notes are ([^;]+);?\s*base notes are ([^;.]+)", desc)
            if m:
                data["notes"]["top"] = [n.strip() for n in m.group(1).split(",")]
                data["notes"]["middle"] = [n.strip() for n in m.group(2).split(",")]
                data["notes"]["base"] = [n.strip() for n in m.group(3).split(",")]

    # Gender from meta or heading
    meta = soup.select_one("meta[name='description']")
    if meta:
        desc = meta.get("content", "").lower()
        if "for women" in desc:
            data["gender"] = "female"
        elif "for men" in desc:
            data["gender"] = "male"
        elif "for women and men" in desc or "unisex" in desc:
            data["gender"] = "unisex"

    # Concentration from description
    if meta:
        desc = meta.get("content", "")
        for c in ["Extrait de Parfum", "Parfum", "Eau de Parfum", "EDP", "Eau de Toilette", "EDT", "Eau de Cologne", "EDC"]:
            if c.lower() in desc.lower():
                data["concentration"] = c
                break

    # Launch year from text (e.g., "launched in 2020")
    text = soup.get_text()
    m = re.search(r"launched\sin\s(\d{4})", text, re.IGNORECASE)
    if m:
        data["launch_year"] = int(m.group(1))

    # Perfumers from h3 section
    for el in soup.find_all(["h3", "h4"]):
        t = el.get_text(strip=True).lower()
        if "perfumer" in t:
            next_p = el.find_next_sibling(["p", "div"])
            if next_p:
                data["perfumers"] = [p.strip() for p in next_p.get_text(strip=True).split(",") if p.strip()]

    # Accords from accord boxes
    for box in soup.select("[class*='accord-box'], .note-box, [class*='note-']"):
        label = box.get_text(strip=True)
        if label:
            data["accords"].append(label.lower())

    # Longevity/Sillage/Projection rating bars
    for attr, sel in [
        ("longevity", "[class*='longevity'] .value, .longevity-value"),
        ("sillage", "[class*='sillage'] .value, .sillage-value"),
        ("projection", "[class*='projection'] .value, .projection-value"),
    ]:
        el = soup.select_one(sel)
        if el:
            val = el.get_text(strip=True)
            m = re.search(r"[\d.]+", val)
            if m:
                data[attr] = float(m.group(1))

    # Similar perfumes
    similar = soup.select_one("#similar, .similar-perfumes, [class*='similar']")
    if similar:
        data["similar_perfumes"] = [a.get_text(strip=True) for a in similar.select("a") if a.get_text(strip=True)]

    # Description
    desc_el = soup.select_one("[itemprop='description'], .description, [class*='desc']")
    if desc_el:
        data["description"] = desc_el.get_text(strip=True)

    return data


# ──────────────────────────────────────────────────
# STEP 3: EXTRACTION PIPELINE
# ──────────────────────────────────────────────────
def extract_all():
    """Full extraction: Countries → Brands → Perfumes."""
    results = {
        "countries": {},
        "brands": {},
        "perfumes": [],
    }
    seen_brands = set()
    seen_perfumes = set()

    # Phase A: Process each country page
    for c in COUNTRIES:
        html_path = FETCHED / f"country_{c}.html"
        if not html_path.exists():
            print(f"[SKIP] Country '{c}' — no fetched HTML at {html_path}")
            continue
        html = html_path.read_text(encoding="utf-8")
        brands = parse_country_brands(html)
        results["countries"][c] = brands
        print(f"[COUNTRY] {c}: {len(brands)} brands")

        for brand in brands:
            brand_slug = brand["slug"]
            if brand_slug in seen_brands:
                continue
            seen_brands.add(brand_slug)

            # Read brand page HTML
            brand_html_path = FETCHED / f"designer_{brand_slug}.html"
            if not brand_html_path.exists():
                continue
            brand_html = brand_html_path.read_text(encoding="utf-8")
            perfumes = parse_brand_perfumes(brand_html)
            results["brands"][brand_slug] = {"name": brand["name"], "perfumes": len(perfumes)}
            print(f"  [BRAND] {brand['name']}: {len(perfumes)} perfumes")

            for p in perfumes:
                p_key = p["url"].lower().rstrip("/")
                if p_key in seen_perfumes:
                    continue
                seen_perfumes.add(p_key)

                perfume_html_path = FETCHED / f"perfume_{brand_slug}_{Path(p['url']).stem}.html"
                if not perfume_html_path.exists():
                    continue
                perfume_html = perfume_html_path.read_text(encoding="utf-8")
                detail = parse_perfume_detail(perfume_html, p["url"])
                detail["name"] = p["name"]
                detail["brand"] = brand["name"]
                results["perfumes"].append(detail)

    return results


# ──────────────────────────────────────────────────
# STEP 4: FETCHING with Playwright (bypass Cloudflare)
# ──────────────────────────────────────────────────
# ──────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────
if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "urls"

    if mode == "urls":
        urls = generate_urls()
        save_urls(urls)
        print("Use these URLs with your external data scraper.")
        print("Then save fetched HTML to:", FETCHED)
        print("  country pages  -> country_{Name}.html")
        print("  designer pages -> designer_{Brand-Slug}.html")
        print("  perfume pages  -> perfume_{slug}.html")
        print()
        print("After fetching, run: python fragrantica_extractor.py parse")

    elif mode == "parse":
        result = extract_all()
        out_path = Path("backend/scraper/data/fragrantica_catalog.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"Saved catalog to {out_path}")
        print(f"  Countries: {len(result['countries'])}")
        print(f"  Brands: {len(result['brands'])}")
        print(f"  Perfumes: {len(result['perfumes'])}")
        for c, brands in result["countries"].items():
            print(f"    {c}: {len(brands)} brands")
