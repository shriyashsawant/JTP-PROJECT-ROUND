"""
AuraMatch AI - A/B Testing Framework
Assigns experiment variants to requests deterministically based on a hash
of the request_id, so the same request always sees the same variant (no
flip-flopping on retries) and distribution is balanced across variants.

Usage:
    @router.post("/search")
    async def search(req: Request, ab: AbTest = Depends(get_ab_test)):
        if ab.is_enabled("new_scoring_v2"):
            # use variant-specific weights
            pass
        response.headers["X-AuraMatch-Variant"] = ab.active_variant
"""

import hashlib
from dataclasses import dataclass, field

from app.core.config import settings


@dataclass
class AbTest:
    """Per-request A/B test assignment. `request_id` is hashed to determine
    which variants this request falls into for each experiment."""

    request_id: str
    _assignments: dict[str, str] = field(default_factory=dict)

    def is_enabled(self, flag_name: str, rollout_pct: int = 50) -> bool:
        """Check if this request is in the treatment group for `flag_name`.

        Uses the existing feature_flags system as a global killswitch:
        if `flag_name` is NOT in settings.feature_flags_set, the feature
        is treated as disabled for ALL requests (canary off).

        When enabled, assigns based on hash(flag_name + request_id) %
        100 < rollout_pct, giving an even split without needing sticky
        sessions or a targeting service."""
        if flag_name not in settings.feature_flags_set:
            self._assignments[flag_name] = "off"
            return False

        key = f"{flag_name}:{self.request_id}"
        h = int(hashlib.md5(key.encode()).hexdigest()[:8], 16)
        assigned = h % 100 < rollout_pct
        self._assignments[flag_name] = "treatment" if assigned else "control"
        return assigned

    @property
    def active_variant(self) -> str:
        """The first active treatment variant, for the response header.
        Returns 'control' if no experiment assigned this request to treatment."""
        for flag, assignment in self._assignments.items():
            if assignment == "treatment":
                return f"{flag}_treatment"
        return "control"
