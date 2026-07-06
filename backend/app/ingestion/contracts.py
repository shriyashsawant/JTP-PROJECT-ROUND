"""
AuraMatch AI - Ingestion Contract
The one canonical shape any data source (today: 5 batch CSV/Kaggle loaders
in seed_data.py; later: a scraper run, a partner API feed, or a user
submission - "all of the above eventually") must normalize into before it
touches storage. This is the only place in the app where adapter-style
decoupling from a specific data source is actually justified right now -
not a full hexagonal rewrite of the whole app, just this one real boundary
where multiple genuine sources already exist or are explicitly planned.
"""
import re

from pydantic import BaseModel, Field


def normalize_name(s: str | None) -> str:
    """Lowercased, punctuation-stripped, whitespace-collapsed form used for
    dedup matching (both the in-memory batch dedup in seed_data.py and the
    persisted `normalized_key` column - see app/ingestion/upsert.py and
    migration 0003_normalized_key). Single source of truth: seed_data.py
    imports this rather than keeping its own copy, so the two dedup paths
    (batch merge, live upsert) can't silently drift out of sync."""
    if not s:
        return ""
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9\s]", "", s)
    return re.sub(r"\s+", " ", s).strip()


class PerfumeRecord(BaseModel):
    """Canonical shape of one perfume, post-normalization, pre-storage.
    Deliberately mirrors the per-row dict shape seed_data.py's loaders
    already produce - this formalizes that existing shape into a typed,
    validated contract rather than introducing a new one."""

    brand: str = Field(..., min_length=1)
    perfume: str = Field(..., min_length=1)
    name: str = ""
    launch_year: str | None = None
    gender: str | None = None
    accords: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    notes_top: list[str] = Field(default_factory=list)
    notes_middle: list[str] = Field(default_factory=list)
    notes_base: list[str] = Field(default_factory=list)
    description: str = ""
    image_url: str | None = None
    rating: float | None = None
    rating_count: int | None = None
    real_price_inr: int | None = None
    url: str | None = None
    country: str | None = None
    perfumer: str | None = None
    source: str = "unknown"
    source_priority: int = 0

    @property
    def normalized_key(self) -> str:
        """`normalize_name(brand)|normalize_name(perfume)` - matches the
        persisted `normalized_key` DB column exactly (both computed by this
        same `normalize_name`), so a lookup by this value reliably finds
        the same logical perfume regardless of case/punctuation variance
        between sources."""
        return f"{normalize_name(self.brand)}|{normalize_name(self.perfume)}"
