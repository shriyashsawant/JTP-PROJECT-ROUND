import re
import json
import time
import hashlib
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .config import SCRAPING_CONFIG


def get_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": SCRAPING_CONFIG["user_agent"],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    })
    return session


def fetch_page(url: str, session: Optional[requests.Session] = None) -> Optional[str]:
    if session is None:
        session = get_session()
    for attempt in range(SCRAPING_CONFIG["max_retries"]):
        try:
            resp = session.get(
                url,
                timeout=SCRAPING_CONFIG["timeout"],
                allow_redirects=True,
            )
            if resp.status_code == 200:
                return resp.text
            elif resp.status_code == 429:
                wait = 2 ** (attempt + 2)
                time.sleep(wait)
                continue
            elif resp.status_code in (403, 404):
                return None
        except requests.RequestException:
            if attempt < SCRAPING_CONFIG["max_retries"] - 1:
                time.sleep(2 ** attempt)
                continue
    return None


def extract_price(text: str) -> Optional[float]:
    if not text:
        return None
    cleaned = re.sub(r"[^\d.]", "", text)
    try:
        return float(cleaned)
    except ValueError:
        return None


def extract_ml(text: str) -> Optional[int]:
    if not text:
        return None
    match = re.search(r"(\d+)\s*ml", text, re.IGNORECASE)
    return int(match.group(1)) if match else None


def extract_concentration(text: str) -> Optional[str]:
    if not text:
        return None
    text_lower = text.lower()
    if "extrait" in text_lower or "pure parfum" in text_lower:
        return "Extrait"
    if "parfum" in text_lower and "eau de" not in text_lower:
        return "Parfum"
    if "edp" in text_lower or "eau de parfum" in text_lower or "eaudeparfum" in text_lower:
        return "EDP"
    if "edt" in text_lower or "eau de toilette" in text_lower or "eaudetoilette" in text_lower:
        return "EDT"
    if "edc" in text_lower or "eau de cologne" in text_lower or "eaudecologne" in text_lower:
        return "Cologne"
    return None


def extract_notes(text: str) -> list[str]:
    if not text:
        return []
    known_notes = [
        "bergamot", "lemon", "orange", "mandarin", "grapefruit", "yuzu", "lime",
        "sandalwood", "cedar", "vetiver", "patchouli", "oud", "agarwood",
        "amber", "vanilla", "tonka", "tobacco", "coffee", "leather",
        "rose", "jasmine", "lavender", "iris", "violet",
        "cardamom", "cinnamon", "pepper", "nutmeg", "clove", "ginger",
        "musk", "incense", "frankincense", "myrrh",
        "marine", "aquatic", "sea", "ozonic",
        "apple", "pear", "pineapple", "peach", "blackcurrant", "fig", "coconut",
        "chocolate", "honey", "almond", "pink pepper",
        "geranium", "ylang-ylang", "neroli", "orange blossom",
        "oakmoss", "patchouli", "amberwood", "cashmeran",
        "coriander", "saffron", "sage", "rosemary", "thyme", "basil",
        "styrax", "benzoin", "labdanum", "cistus",
    ]
    text_lower = text.lower()
    found = []
    for note in known_notes:
        if note in text_lower:
            found.append(note.capitalize())
    return found


def clean_html(html_content: str) -> str:
    soup = BeautifulSoup(html_content, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(separator=" ", strip=True)


def generate_id(name: str, brand: str) -> str:
    raw = f"{brand}_{name}".lower()
    raw = re.sub(r"[^a-z0-9]", "_", raw)
    raw = re.sub(r"_+", "_", raw).strip("_")
    return raw[:64]


def save_json(data, filepath: Path):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_json(filepath: Path):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def chunk_list(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


KNOWN_NOTES = [
    "Bergamot", "Lemon", "Mandarin", "Orange", "Grapefruit", "Lime", "Tangerine", "Yuzu",
    "Jasmine", "Rose", "Lavender", "Lily", "Violet", "Iris", "Peony", "Lily-of-the-Valley",
    "Freesia", "Magnolia", "Gardenia", "Tuberose", "Ylang-Ylang", "Neroli", "Orange Blossom",
    "Vanilla", "Musk", "Amber", "Sandalwood", "Cedar", "Patchouli", "Vetiver", "Oud",
    "Leather", "Tobacco", "Incense", "Frankincense", "Myrrh", "Labdanum", "Benzoin",
    "Cinnamon", "Clove", "Nutmeg", "Cardamom", "Ginger", "Pepper", "Saffron",
    "Coconut", "Almond", "Peach", "Apple", "Pear", "Strawberry", "Cherry", "Raspberry",
    "Blackcurrant", "Pineapple", "Mango", "Melon", "Green Apple", "Red Apple",
    "Honey", "Caramel", "Chocolate", "Coffee", "Tea", "Matcha", "Mint", "Basil",
    "Rosemary", "Thyme", "Sage", "Coriander", "Cumin", "Anise", "Fennel",
    "Oakmoss", "Tree Moss", "Seaweed", "Salt", "Ambergris", "Civet", "Castoreum",
    "Aldehydes", "Bergamot", "Black Pepper", "Blond Woods", "Bourbon Vanilla",
    "Bulgarian Rose", "Cacao", "Cashmeran", "Cedarwood", "Champaca", "Cistus",
    "Citron", "Clary Sage", "Coconut Water", "Coriander Seed", "Cyclamen",
    "Cypress", "Davana", "Elemi", "Fig", "Fir", "Florentine Iris", "French Lavender",
    "Galbanum", "Garlic", "Geranium", "Ginger Lily", "Grapefruit Blossom",
    "Green Grass", "Green Mandarin", "Guaic Wood", "Hay", "Hawthorn", "Hedione",
    "Heliotrope", "Honey Blossom", "Hyacinth", "Jasmine Sambac", "Juniper",
    "Lotus", "Lychee", "Magnolia", "Maple", "Marzipan", "Mimosa", "Muguet",
    "Myrtle", "Narcissus", "Neroli", "Nutmeg", "Oak Wood", "Olive", "Opopanax",
    "Orris", "Oud", "Papyrus", "Passionfruit", "Patchouli Leaf", "Pepper",
    "Petitgrain", "Pimento", "Pink Grapefruit", "Pink Pepper", "Plum", "Plumeria",
    "Poplar Bud", "Prune", "Pumpkin", "Raspberry", "Red Berries", "Red Mandarin",
    "Rhubarb", "Rice", "Rose Absolute", "Rose Centifolia", "Rose de Mai",
    "Rose Oxide", "Rose Petal", "Rose Water", "Rosemary", "Saffron", "Sage",
    "Sandalwood Oil", "Sea Salt", "Seaweed Absolute", "Siam Wood", "Silver Fir",
    "Skunk", "Smoke", "Snowdrop", "Soap", "Sodium Chloride", "Soft Spices",
    "Solar Note", "Souffle", "Spearmint", "Spices", "Star Anise", "Strawberry",
    "Styrax", "Sugar", "Suede", "Sunflower", "Sweet Orange", "Tagetes", "Tamarind",
    "Tar", "Tarragon", "Tea", "Teak Wood", "Thyme", "Tiaré", "Tobacco Blossom",
    "Tolu Balsam", "Tomato Leaf", "Tonka", "Tonka Bean", "Toffee", "Treemoss",
    "Tuberose", "Turkish Rose", "Ultramarine", "Vanilla Absolute", "Vanilla Bean",
    "Vanilla Orchid", "Verbena", "Vetiver Bourbon", "Vetiver Haiti", "Violet Leaf",
    "Violet", "Virginia Cedar", "Vodka", "Walnut", "Water", "Water Jasmine",
    "Water Lily", "Watercress", "Watermelon", "Wax", "Wenge", "Wet Stone",
    "Wheat", "White Amber", "White Chocolate", "White Florals", "White Honey",
    "White Musk", "White Pepper", "White Truffle", "Wild Berries", "Wild Mint",
    "Wintergreen", "Wisteria", "Wood Sage", "Wood Smoke", "Wormwood", "Xylish",
    "Ylang-Ylang", "Yogurt", "Yuzu", "Zest", "Zests",
]


def extract_notes_from_text(text: str) -> dict:
    """Extract notes pyramid from product description / features text."""
    notes = {"top": [], "middle": [], "base": []}
    if not text:
        return notes
    text_lower = text.lower()

    # Pattern 1: structured "Top notes: X; Middle notes: Y; Base notes: Z"
    structured = re.search(
        r"(?:top|head|opening)\s*(?:notes?)?\s*[:;]\s*(.+?)(?:\s*[;.]|\s*(?:middle|heart|mid)\s*(?:notes?)?\s*[:;])"
        r"(?:middle|heart|mid)\s*(?:notes?)?\s*[:;]\s*(.+?)(?:\s*[;.]|\s*(?:base|bottom|dry)\s*(?:notes?)?\s*[:;])"
        r"(?:base|bottom|dry\s*down)\s*(?:notes?)?\s*[:;]\s*(.+?)(?:\.|$)",
        text_lower,
        re.IGNORECASE,
    )
    if structured:
        for i, level in enumerate(["top", "middle", "base"]):
            notes[level] = [n.strip().title() for n in re.split(r"[,/&]+", structured.group(i + 1)) if n.strip()]
        return notes

    # Pattern 2: individual level lines (may not have all 3)
    level_patterns = [
        (["top", "head", "opening"], "top"),
        (["middle", "heart", "mid"], "middle"),
        (["base", "bottom", "dry down"], "base"),
    ]
    for aliases, level in level_patterns:
        for alias in aliases:
            m = re.search(rf"{re.escape(alias)}\s*(?:notes?)?\s*[:;]\s*(.+?)(?:\.|;|$)", text_lower, re.IGNORECASE)
            if m:
                extracted = [n.strip().title() for n in re.split(r"[,/&]+", m.group(1)) if n.strip()]
                # Filter to known notes or reasonable length words
                for n in extracted:
                    if len(n) > 1:
                        notes[level].append(n)
                break

    # Pattern 3: "Fragrance Note: Comes with X top notes that blend with Y" style
    if not any(notes.values()):
        m = re.search(r"(?:fragrance|scent)\s*(?:notes?)?\s*[:;]\s*(.+?)(?:\.|$)", text_lower, re.IGNORECASE)
        if m:
            text_to_scan = m.group(1)
        else:
            text_to_scan = text_lower
        # Look for known notes in the text
        found = []
        for note in KNOWN_NOTES:
            if note.lower() in text_to_scan and note not in found:
                found.append(note)
        if found:
            # Distribute: first ~1/3 as top, middle as middle, last as base
            third = max(len(found) // 3, 1)
            notes["top"] = found[:third]
            notes["middle"] = found[third : 2 * third]
            notes["base"] = found[2 * third:]

    return notes


def extract_notes_from_features(features: list[str]) -> dict:
    """Notes extraction from Amazon feature bullet points."""
    combined = " ".join(features)
    return extract_notes_from_text(combined)


def extract_notes_from_product(product: dict) -> dict:
    """Extract notes from a product dict (works with both scraped and Amazon data)."""
    text_parts = []
    if product.get("description"):
        text_parts.append(product["description"])
    if product.get("features"):
        text_parts.extend(product["features"])
    combined = " ".join(text_parts)
    return extract_notes_from_text(combined)
