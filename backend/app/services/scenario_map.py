"""
AuraMatch AI - Scenario to Notes/Accords Mapping
"""

SCENARIO_MAP = {
    "gym": {
        "label": "Gym & Sports",
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
        "description": "Uplifting, floral, and vibrant scents for blooming weather",
        "accords": ["floral", "green", "fresh", "fruity", "aromatic"],
        "notes": ["neroli", "lily-of-the-valley", "jasmine", "green tea", "apple", "peach", "vetiver"]
    },
    "autumn": {
        "label": "Autumn / Fall",
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


def get_scenario_keys(scenario: str):
    """Get notes and accords for a given scenario."""
    return SCENARIO_MAP.get(scenario, SCENARIO_MAP["daily"])


def get_note_family(note: str):
    """Find which family a note belongs to."""
    for family, notes in NOTE_FAMILIES.items():
        if note.lower() in notes:
            return family
    return None
