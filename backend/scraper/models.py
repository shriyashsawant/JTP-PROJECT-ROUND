from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


class NoteProfile(BaseModel):
    top_notes: list[str] = []
    middle_notes: list[str] = []
    base_notes: list[str] = []


class PerformanceMetrics(BaseModel):
    longevity: Optional[str] = None
    projection: Optional[str] = None
    sillage: Optional[str] = None


class ReviewSentiment(BaseModel):
    positive: int = 0
    negative: int = 0
    neutral: int = 0


class ReviewData(BaseModel):
    source: str = ""
    rating: Optional[float] = None
    title: str = ""
    body: str = ""
    author: str = ""
    date: Optional[str] = None
    verified: bool = False
    votes_helpful: int = 0


class PriceEntry(BaseModel):
    mrp: Optional[float] = None
    discount_price: Optional[float] = None
    currency: str = "INR"
    size_ml: Optional[int] = None
    url: Optional[str] = None
    source: str = ""


class PerfumeProduct(BaseModel):
    name: str = ""
    brand: str = ""
    gender: Optional[str] = None
    category: Optional[str] = None
    concentration: Optional[str] = None
    description: str = ""

    notes: NoteProfile = Field(default_factory=NoteProfile)
    accords: list[str] = []
    ingredients: list[str] = []
    opening: Optional[str] = None
    drydown: Optional[str] = None

    prices: list[PriceEntry] = []
    images: list[str] = []
    tags: list[str] = []
    collection: Optional[str] = None
    launch_year: Optional[str] = None

    longevity: Optional[str] = None
    projection: Optional[str] = None
    sillage: Optional[str] = None

    season: list[str] = []
    time_of_day: list[str] = []
    occasion: list[str] = []
    age_group: Optional[str] = None

    vibe: list[str] = []
    mood: list[str] = []

    celebrity_similarity: Optional[str] = None
    similar_perfumes: list[str] = []
    clone_of: Optional[str] = None

    review_summary: Optional[str] = None
    pros: list[str] = []
    cons: list[str] = []
    rating: Optional[float] = None
    price_segment: Optional[str] = None
    fragrantica_rating: Optional[float] = None
    review_sentiment: ReviewSentiment = Field(default_factory=ReviewSentiment)
    reviews: list[ReviewData] = []

    scent_family: Optional[str] = None
    opening_style: Optional[str] = None
    drydown_style: Optional[str] = None

    formality_score: Optional[float] = None
    sweetness: Optional[float] = None
    freshness: Optional[float] = None
    spiciness: Optional[float] = None
    masculinity: Optional[float] = None
    versatility: Optional[float] = None
    uniqueness: Optional[float] = None
    mass_appeal: Optional[float] = None
    compliment_factor: Optional[float] = None
    office_safety: Optional[float] = None
    date_night_suitability: Optional[float] = None
    luxury_feel: Optional[float] = None
    value_for_money: Optional[float] = None

    scraped_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    source_url: Optional[str] = None


ScoredAttribute = Literal[
    "formality_score", "sweetness", "freshness", "spiciness",
    "masculinity", "versatility", "uniqueness", "mass_appeal",
    "compliment_factor", "office_safety", "date_night_suitability",
    "luxury_feel", "value_for_money"
]

SCORE_RANGE = (1, 10)

SEASONS = ["Summer", "Monsoon", "Winter", "Spring", "Autumn", "Year-round"]
TIMES = ["Morning", "Afternoon", "Evening", "Night"]
OCCASIONS = [
    "Office", "College", "Daily Wear", "Date", "Night Out",
    "Wedding", "Clubbing", "Party", "Formal", "Interview",
    "Travel", "Festival", "Summer Vacation", "Business Meeting",
    "Dinner", "Family Event"
]
VIBES = [
    "Luxury", "Romantic", "Boss", "Confident", "Sexy",
    "Professional", "Clean", "Gym", "Beach", "Vacation",
    "Office", "Wedding", "Royal", "Dark", "Mystery",
    "Elegant", "Minimalist", "Playful", "Youthful", "Mature",
    "Masculine", "Feminine", "Unisex", "Comforting", "Cozy",
    "Sophisticated", "Bold", "Intimate", "Energetic", "Relaxing",
    "Powerful"
]
MOODS = [
    "Powerful", "Elegant", "Mysterious", "Romantic", "Confident",
    "Playful", "Calm", "Sensual", "Adventurous", "Nostalgic",
    "Bold", "Sophisticated", "Energetic", "Relaxed", "Happy"
]
