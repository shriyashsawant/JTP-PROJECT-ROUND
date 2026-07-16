"""
AuraMatch AI - User Profile Tower
Builds a lightweight user profile from session click history stored in
feedback_events. The profile is used to inject personalization context into
the LLM enrichment prompt, so repeat users get recommendations tuned to their
revealed preferences (brand affinity, note family preference, price
sensitivity) without requiring authentication or explicit preference forms.

The profile is entirely session-scoped: no PII, no user identity, no
cross-session tracking. A single session_id with 3+ clicks is enough for
meaningful signal — fewer than that, the profile returns empty signals and
the LLM prompt is unchanged.
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Minimum events before profile signals are considered meaningful
MIN_EVENTS_FOR_PROFILE = 3

# How many recent events to analyze
PROFILE_WINDOW = 50


@dataclass
class UserProfile:
    brand_counts: dict[str, int] = field(default_factory=dict)
    note_family_counts: dict[str, int] = field(default_factory=dict)
    avg_match_score: float = 0.0
    event_count: int = 0
    preferred_gender: str | None = None
    price_sensitivity: str | None = None  # "budget" (<1000), "mid" (1000-3000), "premium" (>3000)

    def has_signal(self) -> bool:
        return self.event_count >= MIN_EVENTS_FOR_PROFILE

    def top_brands(self, n: int = 3) -> list[str]:
        return [b for b, _ in sorted(self.brand_counts.items(), key=lambda x: -x[1])[:n]]

    def top_note_families(self, n: int = 3) -> list[str]:
        return [f for f, _ in sorted(self.note_family_counts.items(), key=lambda x: -x[1])[:n]]


async def build_profile(conn, session_id: str | None) -> UserProfile:
    """Build a UserProfile from recent click events for this session_id.

    Returns an empty-profile (has_signal() == False) if session_id is None,
    has fewer than MIN_EVENTS_FOR_PROFILE events, or any DB error occurs.
    """
    profile = UserProfile()

    if not session_id:
        return profile

    try:
        rows = await conn.fetch(
            """
            SELECT fe.perfume_id, fe.match_score,
                   p.brand, p.main_accords, p.gender, p.price_inr
            FROM feedback_events fe
            JOIN perfumes p ON p.id = fe.perfume_id
            WHERE fe.session_id = $1
              AND fe.event_type = 'click'
            ORDER BY fe.created_at DESC
            LIMIT $2
            """,
            session_id,
            PROFILE_WINDOW,
        )
    except Exception:
        logger.warning("profile_build_db_error", exc_info=True)
        return profile

    if len(rows) < MIN_EVENTS_FOR_PROFILE:
        return profile

    profile.event_count = len(rows)
    total_score = 0.0
    price_total = 0
    price_count = 0
    gender_counts: dict[str, int] = {}

    for row in rows:
        brand = row.get("brand")
        if brand:
            profile.brand_counts[brand] = profile.brand_counts.get(brand, 0) + 1

        accords = row.get("main_accords") or []
        for accord in accords:
            profile.note_family_counts[accord] = profile.note_family_counts.get(accord, 0) + 1

        score = row.get("match_score")
        if score is not None:
            total_score += score

        gender_val = row.get("gender")
        if gender_val and gender_val in ("male", "female", "unisex"):
            gender_counts[gender_val] = gender_counts.get(gender_val, 0) + 1

        price = row.get("price_inr")
        if price is not None:
            price_total += price
            price_count += 1

    if profile.event_count > 0:
        profile.avg_match_score = round(total_score / profile.event_count, 1)

    if gender_counts:
        profile.preferred_gender = max(gender_counts, key=gender_counts.get)

    if price_count > 0:
        avg_price = price_total / price_count
        if avg_price < 1000:
            profile.price_sensitivity = "budget"
        elif avg_price <= 3000:
            profile.price_sensitivity = "mid"
        else:
            profile.price_sensitivity = "premium"

    return profile


def build_personalization_context(profile: UserProfile) -> str:
    """Build a natural-language personalization paragraph for the LLM prompt.

    Returns an empty string if the profile has no meaningful signal, so
    callers can simply append it to the prompt unconditionally.
    """
    if not profile.has_signal():
        return ""

    parts = []
    if top_brands := profile.top_brands():
        parts.append(f"preferred brands: {', '.join(top_brands)}")
    if top_notes := profile.top_note_families():
        parts.append(f"preferred scent families: {', '.join(top_notes)}")
    if profile.preferred_gender:
        parts.append(f"usually wears {profile.preferred_gender} fragrances")
    if profile.price_sensitivity:
        parts.append(f"price sensitivity: {profile.price_sensitivity}")

    if not parts:
        return ""

    ctx = "; ".join(parts)
    return (
        f"\n\nThis user has a session history with these preferences: {ctx}. "
        "Factor these into your ranking — favor brands and scent families "
        "the user has clicked on before, but still prioritize overall match quality."
    )
