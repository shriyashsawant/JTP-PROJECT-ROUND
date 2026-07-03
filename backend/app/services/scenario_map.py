"""
AuraMatch AI - Scenario to Notes/Accords Mapping
"""

SCENARIO_MAP = {
    "gym": {
        "label": "Gym & Sports",
        "vibe": "dynamic and energizing",
        "description": "Light, fresh, high-energy scents that won't overpower",
        "accords": [
            "aquatic",
            "citrus",
            "fresh",
            "green",
            "ozonic",
            "aromatic",
            "marine"
        ],
        "notes": [
            "citruses",
            "bergamot",
            "lemon",
            "grapefruit",
            "green notes",
            "lavender",
            "mint",
            "tea"
        ]
    },
    "summer": {
        "label": "Summer",
        "vibe": "light and refreshing",
        "description": "Light, airy, refreshing scents for hot weather",
        "accords": [
            "aquatic",
            "citrus",
            "fresh",
            "tropical",
            "marine",
            "ozonic",
            "green"
        ],
        "notes": [
            "citruses",
            "bergamot",
            "lemon",
            "grapefruit",
            "coconut",
            "neroli",
            "orange blossom",
            "mandarin orange",
            "sea notes"
        ]
    },
    "winter": {
        "label": "Winter",
        "vibe": "warm and comforting",
        "description": "Warm, rich, cozy scents that last in cold weather",
        "accords": [
            "warm spicy",
            "woody",
            "balsamic",
            "vanilla",
            "amber",
            "smoky",
            "leather"
        ],
        "notes": [
            "vanilla",
            "amber",
            "sandalwood",
            "cedar",
            "tonka bean",
            "incense",
            "leather",
            "cinnamon",
            "cardamom",
            "patchouli",
            "labdanum"
        ]
    },
    "monsoon": {
        "label": "Monsoon & Rainy",
        "vibe": "fresh and earthy",
        "description": "Fresh, green, petrichor-inspired scents for humid weather",
        "accords": [
            "green",
            "aquatic",
            "fresh",
            "ozonic",
            "earthy",
            "aromatic",
            "herbal"
        ],
        "notes": [
            "vetiver",
            "green notes",
            "grassy",
            "tea",
            "lavender",
            "watery notes",
            "petrichor",
            "moss"
        ]
    },
    "office": {
        "label": "Office & Work",
        "vibe": "refined and non-intrusive",
        "description": "Professional, subtle, clean scents that won't distract",
        "accords": [
            "fresh",
            "aromatic",
            "citrus",
            "green",
            "powdery",
            "soft spicy",
            "musky"
        ],
        "notes": [
            "lavender",
            "bergamot",
            "citruses",
            "violet",
            "iris",
            "tea",
            "musk",
            "cedar",
            "oakmoss",
            "neroli"
        ]
    },
    "party": {
        "label": "Party & Night Out",
        "vibe": "bold and vibrant",
        "description": "Bold, loud, attention-grabbing scents",
        "accords": [
            "sweet",
            "warm spicy",
            "amber",
            "leather",
            "animalic",
            "vanilla",
            "smoky",
            "tropical"
        ],
        "notes": [
            "vanilla",
            "amber",
            "leather",
            "incense",
            "cinnamon",
            "tonka bean",
            "coconut",
            "tuberose",
            "ylang-ylang",
            "patchouli"
        ]
    },
    "date": {
        "label": "Date Night",
        "vibe": "alluring and captivating",
        "description": "Romantic, alluring, intimate scents",
        "accords": [
            "sweet",
            "floral",
            "vanilla",
            "warm spicy",
            "musky",
            "white floral",
            "rose"
        ],
        "notes": [
            "rose",
            "jasmine",
            "vanilla",
            "musk",
            "sandalwood",
            "ylang-ylang",
            "tuberose",
            "iris",
            "tonka bean",
            "orange blossom"
        ]
    },
    "wedding": {
        "label": "Wedding & Festival",
        "vibe": "elegant and celebratory",
        "description": "Elegant, sophisticated, celebratory scents",
        "accords": [
            "floral",
            "white floral",
            "rose",
            "powdery",
            "aldehydic",
            "sweet",
            "vanilla"
        ],
        "notes": [
            "rose",
            "jasmine",
            "musk",
            "sandalwood",
            "vanilla",
            "orange blossom",
            "neroli",
            "amber",
            "iris",
            "lily-of-the-valley"
        ]
    },
    "daily": {
        "label": "Daily Wear",
        "vibe": "versatile and easygoing",
        "description": "Versatile, easy-going scents for everyday use",
        "accords": [
            "citrus",
            "fresh",
            "aromatic",
            "musky",
            "woody",
            "soft spicy",
            "green",
            "powdery"
        ],
        "notes": [
            "bergamot",
            "citruses",
            "lavender",
            "musk",
            "cedar",
            "amber",
            "violet",
            "iris",
            "tea",
            "oakmoss"
        ]
    },
    "evening": {
        "label": "Evening",
        "vibe": "sophisticated and elegant",
        "description": "Warm, sensual scents that transition from day to night",
        "accords": [
            "amber",
            "woody",
            "warm spicy",
            "balsamic",
            "leather",
            "smoky",
            "vanilla",
            "animalic"
        ],
        "notes": [
            "amber",
            "leather",
            "incense",
            "sandalwood",
            "patchouli",
            "tonka bean",
            "labdanum",
            "agarwood (oud)",
            "cinnamon",
            "cardamom"
        ]
    },
    "spring": {
        "label": "Spring",
        "vibe": "vibrant and uplifting",
        "description": "Uplifting, floral, and vibrant scents for blooming weather",
        "accords": ["floral", "green", "fresh", "fruity", "aromatic"],
        "notes": ["neroli", "lily-of-the-valley", "jasmine", "green tea", "apple", "peach", "vetiver"]
    },
    "autumn": {
        "label": "Autumn / Fall",
        "vibe": "warm and grounded",
        "description": "Crisp, woody, and gently spiced scents",
        "accords": ["woody", "warm spicy", "earthy", "amber", "leather"],
        "notes": ["cedar", "sandalwood", "cardamom", "nutmeg", "patchouli", "vetiver", "plum"]
    }
}

NOTE_FAMILIES = {
    "citrus": [
        "bergamot",
        "lemon",
        "grapefruit",
        "mandarin orange",
        "orange",
        "neroli",
        "citruses",
        "lime",
        "petitgrain"
    ],
    "floral": [
        "rose",
        "jasmine",
        "violet",
        "ylang-ylang",
        "iris",
        "tuberose",
        "orange blossom",
        "lily-of-the-valley",
        "floral notes",
        "lavender",
        "heliotrope"
    ],
    "woody": [
        "sandalwood",
        "cedar",
        "woody notes",
        "woodsy notes",
        "oakmoss",
        "pine",
        "cypress"
    ],
    "oriental": [
        "amber",
        "vanilla",
        "tonka bean",
        "incense",
        "labdanum",
        "benzoin",
        "myrrh",
        "cinnamon",
        "clove"
    ],
    "fresh_aquatic": [
        "aquatic notes",
        "sea notes",
        "ozonic",
        "marine notes",
        "watery notes",
        "calone"
    ],
    "green": [
        "green notes",
        "vetiver",
        "tea",
        "grassy",
        "herbal",
        "mint",
        "basil",
        "thyme",
        "rosemary"
    ],
    "gourmand": [
        "vanilla",
        "coconut",
        "caramel",
        "chocolate",
        "honey",
        "almond",
        "coffee",
        "sugar"
    ],
    "spicy": [
        "cinnamon",
        "cardamom",
        "black pepper",
        "clove",
        "nutmeg",
        "ginger",
        "saffron",
        "spices",
        "spicy notes"
    ],
    "animalic": [
        "musk",
        "leather",
        "castoreum",
        "civet",
        "ambergris"
    ],
    "earthy": [
        "patchouli",
        "agarwood (oud)",
        "moss",
        "mushroom",
        "rooty notes",
        "earth"
    ],
    "fruity": ["pineapple", "apple", "peach", "plum", "cherry", "pear", "melon", "blackcurrant", "berries", "red fruits"]
}


SKIN_TYPE_MODIFIERS = {
    "dry": {
        "description": "Fragrance fades quickly. Boosts heavy base notes.",
        "boost_families": ["woody", "oriental", "gourmand", "animalic"]
    },
    "oily": {
        "description": "Fragrance projects heavily. Favors lighter top notes.",
        "boost_families": ["citrus", "fresh_aquatic", "green", "fruity"]
    },
    "normal": {
        "description": "Standard projection and longevity.",
        "boost_families": []
    }
}


# ---------------------------------------------------------------------------
# Free-text intent detection keyword banks (deterministic, no LLM)
# ---------------------------------------------------------------------------

SCENARIO_KEYWORDS = {
    "gym": ["gym", "workout", "work out", "exercise", "sweat", "training", "sports", "fitness", "run", "jog"],
    "summer": ["summer", "hot weather", "heatwave", "hot day", "hot climate"],
    "winter": ["winter", "cold weather", "snow", "chilly", "cold day"],
    "monsoon": ["monsoon", "rainy", "rain", "humid weather"],
    "office": ["office", "work", "commute", "desk job", "workplace", "meeting", "professional", "9 to 5", "9-to-5"],
    "party": ["party", "night out", "club", "clubbing", "rave"],
    "date": ["date night", "romantic date", "dinner date", " date "],
    "wedding": ["wedding", "festival", "celebration", "reception"],
    "daily": ["daily", "everyday", "every day", "regular wear", "casual wear"],
    "evening": ["evening", "dinner", "after work"],
    "spring": ["spring season", "springtime", "blooming"],
    "autumn": ["autumn", "fall season", "fall weather"],
}

LONGEVITY_PHRASES = [
    "long lasting", "long-lasting", "lasts long", "lasts all day", "all day",
    "all-day", "stays long", "longevity", "full day", "long wear", "long lasting scent",
]

MALE_HINTS = [r"\bmale\b", r"\bman\b", r"\bmen\b", r"\bboy\b", r"\bguy\b", r"\bhim\b", r"\bhis\b", r"\bhusband\b", r"\bboyfriend\b"]
FEMALE_HINTS = [r"\bfemale\b", r"\bwoman\b", r"\bwomen\b", r"\bgirl\b", r"\bher\b", r"\bhers\b", r"\bwife\b", r"\bgirlfriend\b"]

# Accord -> longevity/sillage weight (0-1). Heavier/denser accords linger and project more.
LONGEVITY_ACCORD_WEIGHTS = {
    "woody": 0.9, "amber": 0.9, "balsamic": 0.9, "leather": 0.9, "musky": 0.85,
    "animalic": 0.9, "smoky": 0.85, "warm spicy": 0.8, "vanilla": 0.8, "oud": 0.95,
    "patchouli": 0.85, "incense": 0.8, "earthy": 0.75,
    "floral": 0.55, "white floral": 0.55, "powdery": 0.5, "soft spicy": 0.55,
    "sweet": 0.6, "rose": 0.55, "aromatic": 0.5, "herbal": 0.5, "spicy": 0.6, "aldehydic": 0.5,
    "citrus": 0.25, "fresh": 0.25, "aquatic": 0.2, "green": 0.3, "ozonic": 0.2,
    "marine": 0.2, "fruity": 0.35, "tropical": 0.35,
}

SILLAGE_ACCORD_WEIGHTS = {
    "oud": 0.95, "leather": 0.9, "smoky": 0.9, "animalic": 0.9, "incense": 0.85,
    "amber": 0.8, "warm spicy": 0.8, "woody": 0.7, "musky": 0.75, "balsamic": 0.7,
    "vanilla": 0.65, "patchouli": 0.75, "sweet": 0.6, "spicy": 0.65, "earthy": 0.6,
    "floral": 0.5, "white floral": 0.55, "rose": 0.5, "powdery": 0.4, "soft spicy": 0.5,
    "aromatic": 0.45, "herbal": 0.4, "aldehydic": 0.45,
    "citrus": 0.3, "fresh": 0.25, "aquatic": 0.2, "green": 0.3, "ozonic": 0.2,
    "marine": 0.2, "fruity": 0.35, "tropical": 0.4,
}

# "Power notes" - individual notes known for outsized longevity/projection regardless of accord family.
POWER_NOTES = ["agarwood (oud)", "oud", "musk", "amber", "sandalwood", "patchouli", "vanilla", "tonka bean", "labdanum"]

# longevity_score (0-100 heuristic) -> human-readable estimated wear time, for display
# and for enforcing explicit hour requirements ("8+ hours") rather than an abstract score.
LONGEVITY_HOUR_BUCKETS = [
    (30, "2-4 hours"),
    (50, "4-6 hours"),
    (70, "6-8 hours"),
    (85, "8-10 hours"),
    (101, "10+ hours"),
]

# sillage_score (0-100 heuristic) -> projection label, for display and for matching
# an explicitly requested projection preference ("moderate projection", "beast mode"...).
SILLAGE_LABEL_BUCKETS = [
    (35, "light"),
    (65, "moderate"),
    (101, "strong"),
]

PROJECTION_HINTS = {
    "light": ["light projection", "subtle", "skin scent", "close to skin", "soft projection", "not too strong"],
    "moderate": ["moderate projection", "medium projection", "balanced projection"],
    "strong": ["strong projection", "heavy sillage", "beast mode", "loud", "projects a lot", "room-filling"],
}

# Explicit hour requirements in free text ("8+ hours", "lasts 6-8 hours") - parsed via regex
# in intent_detector.py, not a simple keyword list.
LONGEVITY_HOUR_PATTERN = r"(\d{1,2})\s*\+?\s*(?:-\s*\d{1,2}\s*)?(?:hour|hr)s?"

# Signals the user wants a cheaper/similar alternative to a named perfume (the
# "dupe engine" intent), whether typed into the free-text search or the
# dedicated dupe form. The bare word "dupe" is checked separately via
# word-boundary regex (see detect_dupe_intent) so "cheap dupe", "a dupe",
# "find a dupe" etc. are all caught without enumerating every adjective.
DUPE_INTENT_PHRASES = [
    "cheaper alternative", "cheaper version", "affordable alternative",
    "budget alternative", "budget version", "clone of", "similar to",
    "alternative to", "instead of", "smells like",
]

# An explicit price ceiling stated in free text ("under Rs 500", "within a
# 1000 budget", "for under 800 rupees", "Rs. 500 budget") - this is EXPLICIT
# user input and must always win over any auto-defaulted budget (e.g. a named
# reference perfume's own price) or a slider default. A currency marker (or
# the word "budget" itself) is REQUIRED before treating a number as a price -
# without it, "under/within/less than" alone would false-positive on
# unrelated numbers like "lasts under 8 hours" or "commute under 20km".
BUDGET_TEXT_PATTERNS = [
    r"(?:under|within|below|less than)\s*(?:rs\.?|inr|₹|rupees)\s*(\d[\d,]*)",
    r"(?:under|within|below|less than)\s*(\d[\d,]*)\s*(?:rupees|rs\.?|inr)\b",
    r"budget\s*(?:of|is|:)?\s*(?:rs\.?|inr|₹|rupees)?\s*(\d[\d,]*)",
    r"(?:rs\.?|inr|₹)\s*(\d[\d,]*)\s*budget",
]

# Age -> accord-tier affinity, sourced from industry/consumer research (fragrance retailer
# and market-segmentation write-ups consistently report this directional pattern across
# independent sources): younger buyers skew fresh/citrus/fruity/light-gourmand, 25-40 skews
# toward woody/spicy/oriental/gourmand, 40+ skews toward classic florals/amber/woody/powdery.
# This is a population-level marketing trend, NOT a hard rule or peer-reviewed finding -
# used as a small, capped nudge (see decision_engine.age_fit), never a hard filter, and the
# explanation text says so explicitly when it's a deciding factor.
AGE_BRACKET_ACCORDS = {
    "under_25": ["citrus", "fresh", "aquatic", "green", "ozonic", "marine", "fruity", "tropical", "sweet"],
    "25_40": ["woody", "warm spicy", "amber", "vanilla", "spicy", "aromatic"],
    "40_plus": ["woody", "amber", "balsamic", "leather", "floral", "white floral", "powdery", "aldehydic", "oud"],
}


def age_to_bracket(age):
    """Map an age (int) to an AGE_BRACKET_ACCORDS key, or None if age is unknown."""
    if age is None:
        return None
    if age < 25:
        return "under_25"
    if age <= 40:
        return "25_40"
    return "40_plus"


def estimate_wear_hours(longevity_score) -> str:
    """Convert a 0-100 longevity_score into a human-readable estimated wear range."""
    if longevity_score is None:
        return "Unknown"
    for threshold, label in LONGEVITY_HOUR_BUCKETS:
        if longevity_score < threshold:
            return label
    return LONGEVITY_HOUR_BUCKETS[-1][1]


def estimate_hours_numeric(longevity_score) -> float:
    """Rough numeric midpoint (hours) for a longevity_score, used to compare against an
    explicit hour requirement like '8+ hours'."""
    if longevity_score is None:
        return 4.0
    label = estimate_wear_hours(longevity_score)
    lo, hi = label.replace(" hours", "").replace("+", "-99").split("-")
    return (float(lo) + min(float(hi), float(lo) + 4)) / 2


def sillage_label(sillage_score) -> str:
    """Convert a 0-100 sillage_score into a light/moderate/strong projection label."""
    if sillage_score is None:
        return "unknown"
    for threshold, label in SILLAGE_LABEL_BUCKETS:
        if sillage_score < threshold:
            return label
    return SILLAGE_LABEL_BUCKETS[-1][1]


def get_scenario_keys(scenario: str):
    """Get notes and accords for a given scenario."""
    return SCENARIO_MAP.get(scenario, SCENARIO_MAP["daily"])


def get_note_family(note: str):
    """Find which family a note belongs to."""
    for family, notes in NOTE_FAMILIES.items():
        if note.lower() in notes:
            return family
    return None
