"""
AuraMatch AI - Ingestion Quality Gate
Deliberately separate from PerfumeRecord's Pydantic-level validation:
Pydantic enforces the hard structural contract (types, required fields).
This module enforces softer *business* rules (price positivity, rating
range, blank-but-technically-valid-string entries) and reports them as a
list of human-readable issues rather than raising - today's curated
CSV/Kaggle sources are trustworthy enough that this never fires, but
once live sources (scraping, a partner API, user submissions) start
landing with much less pre-validated data, these same functions become
the actual gate, and the (record, errors) shape is what a future admin
review UI (Phase 5 of the architecture roadmap) would surface to a human
before/instead of auto-rejecting.
"""
from app.ingestion.contracts import PerfumeRecord


def validate_record(record: PerfumeRecord) -> list[str]:
    """Returns a list of quality issues (empty = clean). Never raises -
    callers decide what to do with the issues (reject, flag for review,
    log and proceed anyway)."""
    errors = []

    if not record.brand.strip():
        errors.append("brand is empty")
    if not record.perfume.strip():
        errors.append("perfume name is empty")

    if record.real_price_inr is not None and record.real_price_inr <= 0:
        errors.append(f"non-positive price: {record.real_price_inr}")

    if record.rating is not None and not (0 <= record.rating <= 5):
        errors.append(f"rating out of expected 0-5 range: {record.rating}")

    if record.rating_count is not None and record.rating_count < 0:
        errors.append(f"negative rating_count: {record.rating_count}")

    for label, values in (("accord", record.accords), ("note", record.notes)):
        if any(not v.strip() for v in values):
            errors.append(f"blank {label} entry present")

    return errors


def is_valid(record: PerfumeRecord) -> bool:
    return not validate_record(record)
