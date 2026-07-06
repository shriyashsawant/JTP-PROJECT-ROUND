"""Unit tests for the small heuristic conversion helpers in scenario_map.py."""
from app.services.scenario_map import (
    age_to_bracket,
    classify_note_tiers,
    estimate_hours_numeric,
    estimate_wear_hours,
    get_note_family,
    sillage_label,
)


class TestGetNoteFamily:
    def test_exact_match(self):
        assert get_note_family("bergamot") == "citrus"

    def test_fuzzy_match_against_more_specific_note_name(self):
        # Regression: an exact-match-only lookup would return None for real
        # DB note names more specific than this generic vocabulary.
        assert get_note_family("Sicilian Lemon") == "citrus"
        assert get_note_family("Indonesian Patchouli Leaf") == "earthy"

    def test_bare_oud_and_agarwood_variants_resolve_to_earthy(self):
        assert get_note_family("Oud") == "earthy"
        assert get_note_family("Agarwood") == "earthy"

    def test_vetiver_resolves_to_woody(self):
        assert get_note_family("Vetiver") == "woody"

    def test_new_expanded_mappings_resolve_correctly(self):
        assert get_note_family("Vanille") == "oriental"
        assert get_note_family("Tangerine") == "citrus"
        assert get_note_family("Pink Pepper") == "spicy"

    def test_unknown_note_returns_none(self):
        assert get_note_family("Some Unrecognized Note") is None

    def test_empty_note_returns_none(self):
        assert get_note_family("") is None


class TestClassifyNoteTiers:
    def test_splits_notes_into_top_heart_base(self):
        top, heart, base = classify_note_tiers(["bergamot", "rose", "musk"])
        assert top == ["bergamot"]
        assert heart == ["rose"]
        assert base == ["musk"]

    def test_unknown_note_falls_back_to_heart(self):
        top, heart, base = classify_note_tiers(["Some Unrecognized Note"])
        assert top == []
        assert heart == ["Some Unrecognized Note"]
        assert base == []

    def test_empty_input(self):
        assert classify_note_tiers([]) == ([], [], [])
        assert classify_note_tiers(None) == ([], [], [])


class TestAgeToBracket:
    def test_none_age_returns_none(self):
        assert age_to_bracket(None) is None

    def test_under_25(self):
        assert age_to_bracket(20) == "under_25"

    def test_25_to_40_inclusive(self):
        assert age_to_bracket(25) == "25_40"
        assert age_to_bracket(40) == "25_40"

    def test_over_40(self):
        assert age_to_bracket(41) == "40_plus"


class TestEstimateWearHours:
    def test_none_score_is_unknown(self):
        assert estimate_wear_hours(None) == "Unknown"

    def test_low_score_bucket(self):
        assert estimate_wear_hours(10) == "2-4 hours"

    def test_high_score_bucket(self):
        assert estimate_wear_hours(95) == "10+ hours"

    def test_boundary_score(self):
        assert estimate_wear_hours(69) == "6-8 hours"
        assert estimate_wear_hours(70) == "8-10 hours"


class TestEstimateHoursNumeric:
    def test_none_score_defaults_to_four(self):
        assert estimate_hours_numeric(None) == 4.0

    def test_returns_a_positive_number_for_known_score(self):
        assert estimate_hours_numeric(80) > 0


class TestSillageLabel:
    def test_none_score_is_unknown(self):
        assert sillage_label(None) == "unknown"

    def test_light(self):
        assert sillage_label(10) == "light"

    def test_moderate(self):
        assert sillage_label(50) == "moderate"

    def test_strong(self):
        assert sillage_label(90) == "strong"
