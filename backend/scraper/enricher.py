import re
import json
from typing import Optional

from .models import PerfumeProduct


class AIEnricher:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = None
        self._load_model()

    def _load_model(self):
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.model_name)
            print(f"[Enricher] Loaded embedding model: {self.model_name}")
        except Exception as e:
            print(f"[Enricher] Embedding model not available: {e}")
            print("[Enricher] Running in rule-based enrichment mode only")

    def enrich(self, product: PerfumeProduct) -> PerfumeProduct:
        self._set_scent_family(product)
        self._set_opening_style(product)
        self._set_drydown_style(product)
        self._set_price_segment(product)
        self._set_scored_attributes(product)
        self._set_vibe_mood(product)
        self._set_occasion_season(product)
        return product

    def _get_text(self, product: PerfumeProduct) -> str:
        return (
            (product.description or "")
            + " " + (product.opening or "")
            + " " + (product.drydown or "")
            + " " + " ".join(product.tags)
        ).lower()

    def _get_accords(self, product: PerfumeProduct) -> list[str]:
        return [a.lower() for a in product.accords]

    def _get_all_notes(self, product: PerfumeProduct) -> list[str]:
        return [n.lower() for n in (
            product.notes.top_notes
            + product.notes.middle_notes
            + product.notes.base_notes
        )]

    def _set_scent_family(self, product: PerfumeProduct):
        accords = self._get_accords(product)
        notes = self._get_all_notes(product)
        desc = self._get_text(product)

        families = {
            "Citrus Aromatic":  (["citrus", "bergamot", "lemon", "grapefruit", "aromatic", "herbal"], 1),
            "Citrus Fresh":     (["citrus", "bergamot", "orange", "lime", "mandarin", "fresh"], 1),
            "Aquatic Fresh":    (["aquatic", "marine", "sea", "ozonic", "water", "ocean"], 1),
            "Green Fresh":      (["green", "grass", "galbanum", "violet leaf", "cucumber"], 1),
            "Floral":           (["floral", "rose", "jasmine", "peony", "gardenia"], 1),
            "Soft Floral":      (["powdery", "iris", "lily", "freesia", "soft floral"], 1),
            "Oriental Floral":  (["oriental floral", "spicy floral", "amber floral"], 1),
            "Woody":            (["woody", "sandalwood", "cedar", "oak", "pine"], 1),
            "Spicy Woody":      (["spicy", "pepper", "cardamom", "woody spicy"], 1),
            "Amber Woody":      (["amber", "amberwood", "woody amber"], 1),
            "Musk Woody":       (["musk", "woody musk", "musky"], 1),
            "Oriental":         (["oriental", "amber", "incense", "labdanum", "resin"], 1),
            "Spicy Oriental":   (["cinnamon", "clove oriental", "spicy oriental"], 1),
            "Soft Oriental":    (["vanilla amber", "soft oriental"], 1),
            "Gourmand":         (["gourmand", "vanilla", "chocolate", "caramel", "honey"], 1),
            "Fruity Gourmand":  (["fruity", "berry", "fruity sweet"], 1),
            "Leather":          (["leather", "leathery", "smoky"], 1),
            "Oud":              (["oud", "agarwood", "oudh"], 1),
            "Chypre":           (["chypre", "oakmoss", "labdanum", "bergamot patchouli"], 1),
            "Fougère":          (["fougere", "fern", "lavender", "coumarin"], 1),
        }

        best = ("Others", 0)
        for family, (keywords, _) in families.items():
            score = sum(2 for kw in keywords if kw in accords)
            score += sum(1 for kw in keywords if kw in notes)
            score += sum(1 for kw in keywords if kw in desc)
            if score > best[1]:
                best = (family, score)

        product.scent_family = best[0]

    def _set_opening_style(self, product: PerfumeProduct):
        notes = [n.lower() for n in product.notes.top_notes]
        if not notes:
            product.opening_style = "Not specified"
            return
        if any(n in notes for n in ["bergamot", "lemon", "orange", "grapefruit", "lime", "mandarin", "yuzu"]):
            product.opening_style = "Fresh Citrus Burst"
        elif any(n in notes for n in ["apple", "pear", "pineapple", "peach", "berry", "blackcurrant"]):
            product.opening_style = "Fruity Opening"
        elif any(n in notes for n in ["pink pepper", "pepper", "cardamom", "cinnamon", "nutmeg"]):
            product.opening_style = "Spicy Opening"
        elif any(n in notes for n in ["lavender", "rosemary", "sage", "basil", "thyme"]):
            product.opening_style = "Aromatic Opening"
        elif any(n in notes for n in ["aldehyde", "aldehydes"]):
            product.opening_style = "Aldehydic Sparkle"
        elif any(n in notes for n in ["green", "galbanum", "violet leaf"]):
            product.opening_style = "Green Opening"
        elif any(n in notes for n in ["aquatic", "marine", "sea"]):
            product.opening_style = "Fresh Aquatic Opening"
        else:
            product.opening_style = f"{notes[0].title()} Opening"

    def _set_drydown_style(self, product: PerfumeProduct):
        base = [n.lower() for n in product.notes.base_notes]
        if not base:
            product.drydown_style = "Not specified"
            return
        if any(n in base for n in ["vanilla", "tonka", "benzoin"]):
            product.drydown_style = "Sweet Creamy Base"
        elif any(n in base for n in ["oud", "agarwood"]):
            product.drydown_style = "Rich Oud Base"
        elif any(n in base for n in ["sandalwood", "cedar", "vetiver", "patchouli"]):
            product.drydown_style = "Woody Base"
        elif any(n in base for n in ["musk", "white musk"]):
            product.drydown_style = "Musky Clean Base"
        elif any(n in base for n in ["amber", "labdanum"]):
            product.drydown_style = "Warm Amber Base"
        elif any(n in base for n in ["leather", "tobacco"]):
            product.drydown_style = "Leathery Base"
        elif any(n in base for n in ["incense", "frankincense", "myrrh"]):
            product.drydown_style = "Resinous Incense Base"
        elif any(n in base for n in ["coconut", "milk", "cream"]):
            product.drydown_style = "Creamy Gourmand Base"
        else:
            product.drydown_style = f"{base[0].title()} Base"

    def _set_price_segment(self, product: PerfumeProduct):
        prices = [p.mrp or p.discount_price for p in product.prices if p.mrp or p.discount_price]
        if not prices:
            product.price_segment = "Unknown"
            return
        avg = sum(prices) / len(prices)
        if avg <= 500:
            product.price_segment = "Budget"
        elif avg <= 1500:
            product.price_segment = "Affordable"
        elif avg <= 3500:
            product.price_segment = "Mid-Range"
        elif avg <= 8000:
            product.price_segment = "Premium"
        else:
            product.price_segment = "Luxury"

    def _set_scored_attributes(self, product: PerfumeProduct):
        accords = self._get_accords(product)
        notes = self._get_all_notes(product)
        desc = self._get_text(product)

        def match_score(exact: list[list[str]], high: float, low: float, default: float) -> float:
            if any(all(kw in accords or kw in notes or kw in desc for kw in group) for group in exact):
                return high
            if any(any(kw in accords or kw in notes or kw in desc for kw in group) for group in exact):
                return high - 1.5
            return low

        def keyword_score(high_kw: list[str], low_kw: list[str], default: float) -> float:
            if any(kw in accords or kw in notes or kw in desc for kw in high_kw):
                return 8.0
            if any(kw in accords or kw in notes or kw in desc for kw in low_kw):
                return 3.0
            return default

        product.sweetness = keyword_score(
            ["sweet", "vanilla", "gourmand", "honey", "caramel", "chocolate", "tonka"],
            ["citrus", "green", "herbal", "earthy", "woody"],
            5.0
        )
        product.freshness = keyword_score(
            ["fresh", "citrus", "aquatic", "marine", "ozonic", "green"],
            ["gourmand", "leather", "tobacco", "oud"],
            5.0
        )
        product.spiciness = keyword_score(
            ["spicy", "pepper", "cardamom", "cinnamon", "clove", "nutmeg", "saffron"],
            ["fresh", "aquatic", "floral", "clean"],
            4.0
        )
        product.formality_score = keyword_score(
            ["formal", "luxury", "elegant", "sophisticated", "premium", "classy"],
            ["casual", "playful", "fun", "beach", "gym"],
            5.0
        )

        has_rose = "rose" in notes
        has_jasmine = "jasmine" in notes
        has_lavender = "lavender" in notes
        has_floral = "floral" in accords or has_rose or has_jasmine or has_lavender
        has_woody = "woody" in accords or "sandalwood" in notes
        has_oud = "oud" in accords or "agarwood" in notes

        if product.gender == "male":
            product.masculinity = 8.0
        elif product.gender == "female":
            product.masculinity = 2.0
        else:
            product.masculinity = 6.0 if (has_woody or has_oud) else (4.0 if has_floral else 5.0)

        product.versatility = 7.0 if len(product.accords) >= 4 else 5.0
        product.uniqueness = 6.0 if len(product.accords) >= 3 else (4.0 if len(product.accords) <= 1 else 5.0)
        product.mass_appeal = 7.0 if ("citrus" in accords or "fresh" in accords) else 5.0
        product.compliment_factor = 7.5 if ("sweet" in accords or "vanilla" in accords) else 5.5
        product.office_safety = 8.0 if ("fresh" in accords or "citrus" in accords or "aromatic" in accords) else 4.0
        product.date_night_suitability = 8.0 if ("vanilla" in accords or "sweet" in accords or "oriental" in accords) else 5.0

        product.luxury_feel = keyword_score(
            ["oud", "leather", "tobacco", "incense", "premium"],
            ["fresh", "citrus", "aquatic"],
            5.0
        )
        product.value_for_money = 8.0 if product.price_segment in ("Budget", "Affordable") else (
            6.0 if product.price_segment == "Mid-Range" else 4.0
        )

    def _set_vibe_mood(self, product: PerfumeProduct):
        accords = self._get_accords(product)
        notes = self._get_all_notes(product)

        vibe_rules = {
            "Luxury":       ["oud", "leather", "incense", "premium"],
            "Confident":    ["woody", "leather", "spicy", "bold"],
            "Sexy":         ["vanilla", "musk", "amber", "oriental"],
            "Elegant":      ["floral", "powdery", "aldehydic", "rose"],
            "Playful":      ["fruity", "sweet", "gourmand", "berry"],
            "Mysterious":   ["oud", "incense", "dark", "tobacco"],
            "Romantic":     ["rose", "vanilla", "floral"],
            "Professional": ["clean", "aromatic", "fresh", "soapy"],
            "Youthful":     ["fruity", "citrus", "fresh"],
            "Bold":         ["spicy", "leather", "tobacco", "oud"],
            "Calm":         ["lavender", "musk", "powdery"],
            "Energetic":    ["citrus", "fresh", "aquatic"],
            "Cozy":         ["vanilla", "tonka", "amber", "gourmand"],
            "Sophisticated": ["woody", "chypre", "aldehydic", "iris"],
        }

        product.vibe = []
        for vibe, kws in vibe_rules.items():
            if any(kw in accords or kw in notes for kw in kws):
                product.vibe.append(vibe)
        if not product.vibe:
            product.vibe = ["Versatile"]

        if "floral" in accords or "rose" in notes or "jasmine" in notes:
            product.mood = ["Elegant", "Romantic"]
            if "sweet" in accords or "gourmand" in accords:
                product.mood.append("Playful")
        elif "oud" in accords:
            product.mood = ["Powerful", "Mysterious", "Bold"]
        elif "citrus" in accords or "fresh" in accords or "aquatic" in accords:
            product.mood = ["Energetic", "Happy", "Fresh"]
        elif "vanilla" in accords or "sweet" in accords or "gourmand" in accords:
            product.mood = ["Romantic", "Comforting", "Cozy"]
        elif "woody" in accords:
            product.mood = ["Confident", "Sophisticated"]
        elif "oriental" in accords or "amber" in accords:
            product.mood = ["Sensual", "Warm", "Mysterious"]
        else:
            product.mood = ["Sophisticated"]

    def _set_occasion_season(self, product: PerfumeProduct):
        accords = self._get_accords(product)
        is_fresh = any(a in accords for a in ["citrus", "aquatic", "green", "fresh", "aromatic"])
        is_warm = any(a in accords for a in ["oriental", "amber", "vanilla", "sweet", "gourmand"])
        is_woody = any(a in accords for a in ["woody", "leather", "oud", "tobacco"])
        is_floral = "floral" in accords

        if not product.season:
            if is_fresh and not is_warm:
                product.season = ["Summer", "Spring"]
            elif is_warm and not is_fresh:
                product.season = ["Winter", "Autumn"]
            elif is_woody:
                product.season = ["Autumn", "Winter"]
            elif is_floral:
                product.season = ["Spring", "Summer"]
            else:
                product.season = ["Year-round"]
            if any(a in ["aquatic", "marine"] for a in accords):
                if "Summer" not in product.season:
                    product.season.append("Summer")

        if not product.occasion:
            occ = []
            if is_fresh or is_woody:
                occ.append("Daily Wear")
            if is_fresh and not is_warm:
                occ.append("Office")
            if is_warm or is_woody or is_floral:
                occ.extend(["Date", "Evening"])
            if is_floral:
                occ.append("Wedding")
            if is_warm:
                occ.append("Party")
            if "Summer" in (product.season or []):
                occ.append("Summer Vacation")
            if not occ:
                occ = ["Daily Wear", "Casual"]
            product.occasion = list(dict.fromkeys(occ))

    def compute_embedding(self, text: str) -> Optional[list[float]]:
        if self.model is None:
            return None
        try:
            emb = self.model.encode(text, normalize_embeddings=True)
            return emb.tolist()
        except Exception:
            return None

    def generate_description_embedding(self, product: PerfumeProduct) -> Optional[list[float]]:
        text = (
            f"{product.name} by {product.brand}. "
            f"{' '.join(product.accords)}. "
            f"Top: {' '.join(product.notes.top_notes)}. "
            f"Middle: {' '.join(product.notes.middle_notes)}. "
            f"Base: {' '.join(product.notes.base_notes)}. "
            f"{product.description}"
        )
        return self.compute_embedding(text)

    def llm_enrich(self, product: PerfumeProduct) -> PerfumeProduct:
        """
        Optional LLM-based enrichment (requires an LLM API).
        Overrides rule-based values with LLM-generated ones.
        Implement via your preferred LLM client.
        """
        return product
