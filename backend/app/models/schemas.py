from pydantic import BaseModel, Field
from typing import Optional, Literal

class ContextSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language query or scenario keyword")
    budget: Optional[float] = Field(None, ge=0, description="Max price in INR")
    limit: int = Field(5, ge=1, le=20)
    scenario: Optional[list[str]] = Field(None, description="Optional scenario filters (multi-select)")
    skin_type: Optional[str] = Field(None, description="Skin type: dry/oily/normal")
    gender: Optional[Literal["male", "female", "unisex"]] = Field(None, description="Optional gender preference")
    age: Optional[int] = Field(None, ge=13, le=100, description="Age (not used in scoring, UX only)")
    note_families: Optional[list[str]] = Field(None, description="Preferred scent families")

class BudgetSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Perfume name or description")
    budget: float = Field(..., ge=100, description="Max price in INR (required)")
    limit: int = Field(6, ge=1, le=20)
    scenario: Optional[list[str]] = Field(None, description="Optional scenario filters (multi-select)")
    skin_type: Optional[str] = Field(None, description="Skin type: dry/oily/normal")
    gender: Optional[Literal["male", "female", "unisex"]] = Field(None, description="Optional gender preference")
    age: Optional[int] = Field(None, ge=13, le=100, description="Age (not used in scoring, UX only)")
    note_families: Optional[list[str]] = Field(None, description="Preferred scent families")

class PerfumeResponse(BaseModel):
    id: int
    brand: str
    perfume: str
    price_inr: Optional[float] = None
    currency: str = "INR"
    match_score: Optional[float] = None
    notes: list[str] = []
    main_accords: list[str] = []
    type: Optional[str] = None
    gender: Optional[str] = None
    longevity_score: Optional[float] = None
    sillage_score: Optional[float] = None
    launch_year: Optional[str] = None
    image_url: Optional[str] = None
    savings: Optional[float] = None
    explanation: Optional[str] = None

class PerfumeDetailResponse(BaseModel):
    id: int
    brand: str
    perfume: str
    launch_year: Optional[str] = None
    price_inr: Optional[float] = None
    currency: str = "INR"
    type: Optional[str] = None
    gender: Optional[str] = None
    main_accords: list[str] = []
    notes: list[str] = []
    longevity_score: Optional[float] = None
    sillage_score: Optional[float] = None
    image_url: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    db_connected: bool
