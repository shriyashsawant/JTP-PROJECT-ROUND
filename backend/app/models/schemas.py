from typing import Literal

from pydantic import BaseModel, Field


class MatchCriterion(BaseModel):
    label: str
    status: Literal["met", "partial", "unmet"]

class ContextSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="Natural language query or scenario keyword")
    budget: float | None = Field(None, ge=0, description="Max price in INR")
    limit: int = Field(5, ge=1, le=60, description="Raised from an earlier 20 to support incremental \"Show More\" pagination in the chat UI")
    scenario: list[str] | None = Field(None, description="Optional scenario filters (multi-select)")
    skin_type: str | None = Field(None, description="Skin type: dry/oily/normal")
    gender: Literal["male", "female", "unisex"] | None = Field(None, description="Optional gender preference")
    age: int | None = Field(None, ge=13, le=100, description="Age - used as a soft accord-affinity nudge, not a hard filter")
    note_families: list[str] | None = Field(None, description="Preferred scent families")
    hours_required: int | None = Field(None, ge=1, le=24, description="Minimum longevity in hours (20% of the score) - same signal as typing '8+ hours' in the query, but explicit")
    projection_preference: Literal["light", "moderate", "strong"] | None = Field(None, description="Preferred sillage/projection strength (10% of the score)")
    deal_breaker: bool = Field(False, description="If true and a budget is set, results are sorted cheapest-first instead of nearest-to-budget-first")

class BudgetSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="Perfume name or description")
    budget: float | None = Field(None, ge=100, description="Max price in INR - if omitted, results aren't price-filtered or price-sorted, just ranked by match quality")
    limit: int = Field(6, ge=1, le=60, description="Raised from an earlier 20 to support incremental \"Show More\" pagination in the chat UI")
    scenario: list[str] | None = Field(None, description="Optional scenario filters (multi-select)")
    skin_type: str | None = Field(None, description="Skin type: dry/oily/normal")
    gender: Literal["male", "female", "unisex"] | None = Field(None, description="Optional gender preference")
    age: int | None = Field(None, ge=13, le=100, description="Age - used as a soft accord-affinity nudge, not a hard filter")
    note_families: list[str] | None = Field(None, description="Preferred scent families")
    hours_required: int | None = Field(None, ge=1, le=24, description="Minimum longevity in hours (20% of the score) - same signal as typing '8+ hours' in the query, but explicit")
    projection_preference: Literal["light", "moderate", "strong"] | None = Field(None, description="Preferred sillage/projection strength (10% of the score)")
    deal_breaker: bool = Field(False, description="If true and a budget is set, results are sorted cheapest-first instead of nearest-to-budget-first")

class PerfumeResponse(BaseModel):
    id: int
    brand: str
    perfume: str
    price_inr: float | None = None
    currency: str = "INR"
    match_score: float | None = None
    notes: list[str] = []
    main_accords: list[str] = []
    type: str | None = None
    gender: str | None = None
    longevity_score: float | None = None
    sillage_score: float | None = None
    launch_year: str | None = None
    image_url: str | None = None
    url: str | None = None
    country: str | None = None
    perfumer: str | None = None
    savings: float | None = None
    explanation: str | None = None
    estimated_wear_hours: str | None = None
    projection_label: str | None = None
    best_for: list[str] = []
    match_breakdown: list[MatchCriterion] = []

class PerfumeDetailResponse(BaseModel):
    id: int
    brand: str
    perfume: str
    launch_year: str | None = None
    price_inr: float | None = None
    currency: str = "INR"
    type: str | None = None
    gender: str | None = None
    main_accords: list[str] = []
    notes: list[str] = []
    top_notes: list[str] = []
    heart_notes: list[str] = []
    base_notes: list[str] = []
    longevity_score: float | None = None
    sillage_score: float | None = None
    image_url: str | None = None
    url: str | None = None
    country: str | None = None
    perfumer: str | None = None

class HealthResponse(BaseModel):
    status: str
    db_connected: bool
