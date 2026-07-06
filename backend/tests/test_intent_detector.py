"""
Unit tests for the deterministic (non-ML) free-text intent parsers in
intent_detector.py. `detect_scenarios`'s semantic half is mocked out here so
these stay fast and don't require downloading/loading the SentenceTransformer
model - the keyword-matching path is still exercised for real.
"""
import app.services.intent_detector as intent_detector
from app.services.intent_detector import (
    detect_budget_from_text,
    detect_dupe_intent,
    detect_gender,
    detect_longevity_hours_required,
    detect_longevity_intent,
    detect_negated_terms,
    detect_projection_preference,
    detect_scenarios,
)


class TestDetectGender:
    def test_male_hint(self):
        assert detect_gender("a scent for my husband") == "male"

    def test_female_hint(self):
        assert detect_gender("something for her") == "female"

    def test_unisex_hint(self):
        assert detect_gender("a unisex fragrance") == "unisex"

    def test_unisex_takes_priority_over_conflicting_binary_hints(self):
        # Without the unisex check, "men and women" matches both MALE_HINTS
        # and FEMALE_HINTS and would fall through to the ambiguous None case.
        assert detect_gender("perfume for men and women") == "unisex"

    def test_ambiguous_both_hints_without_unisex_phrase_is_none(self):
        assert detect_gender("something for him or her") is None

    def test_no_hint_is_none(self):
        assert detect_gender("fresh citrus scent") is None

    def test_empty_query_is_none(self):
        assert detect_gender("") is None


class TestDetectLongevityHours:
    def test_plus_notation(self):
        assert detect_longevity_hours_required("needs 8+ hours") == 8

    def test_hyphen_range_captures_lower_bound(self):
        assert detect_longevity_hours_required("lasts 6-8 hours") == 6

    def test_to_word_range(self):
        assert detect_longevity_hours_required("lasts 6 to 8 hours") == 6

    def test_or_word_range(self):
        assert detect_longevity_hours_required("8 or 10 hrs") == 8

    def test_no_number_returns_none(self):
        assert detect_longevity_hours_required("long lasting please") is None

    def test_out_of_range_hours_rejected(self):
        assert detect_longevity_hours_required("lasts 30 hours") is None

    def test_soft_longevity_phrase_detected_separately(self):
        assert detect_longevity_intent("I want something long lasting") is True
        assert detect_longevity_intent("fresh citrus scent") is False


class TestDetectBudgetFromText:
    def test_currency_symbol(self):
        assert detect_budget_from_text("under ₹500") == 500.0

    def test_rs_prefix(self):
        assert detect_budget_from_text("within Rs 1000") == 1000.0

    def test_no_currency_fallback(self):
        assert detect_budget_from_text("perfume under 2000") == 2000.0

    def test_no_currency_fallback_ignores_hour_counts(self):
        # Regression: this must NOT match "8" as a budget - hour counts are
        # always 1-2 digits, the no-currency fallback requires 3-5 digits.
        assert detect_budget_from_text("lasts under 8 hours") is None

    def test_no_currency_fallback_ignores_small_distances(self):
        assert detect_budget_from_text("commute under 20km") is None

    def test_budget_keyword(self):
        assert detect_budget_from_text("my budget is 1500") == 1500.0

    def test_no_budget_mentioned(self):
        assert detect_budget_from_text("fresh citrus scent") is None


class TestDetectDupeIntent:
    def test_bare_dupe_word(self):
        assert detect_dupe_intent("looking for a cheap dupe") is True

    def test_dupe_for_phrase(self):
        assert detect_dupe_intent("dupe for Bleu de Chanel") is True

    def test_cheaper_alternative_phrase(self):
        assert detect_dupe_intent("cheaper alternative to Dior Sauvage") is True

    def test_no_dupe_intent(self):
        assert detect_dupe_intent("a fresh summer fragrance") is False


class TestDetectProjectionPreference:
    def test_light_hint(self):
        assert detect_projection_preference("something subtle, close to skin") == "light"

    def test_strong_hint(self):
        assert detect_projection_preference("I want beast mode projection") == "strong"

    def test_bike_travel_hint(self):
        assert detect_projection_preference("travel 20km by bike daily") == "strong"

    def test_no_hint(self):
        assert detect_projection_preference("fresh citrus scent") is None


class TestDetectNegatedTerms:
    def test_no_phrase(self):
        assert detect_negated_terms("fresh summer scent but no vanilla") == ["vanilla"]

    def test_not_and_avoid_phrases(self):
        assert detect_negated_terms("not sweet or heavy, avoid oud") == ["sweet", "oud"]

    def test_without_phrase(self):
        assert detect_negated_terms("without rose") == ["rose"]

    def test_no_negation_present(self):
        assert detect_negated_terms("fresh citrus scent") == []

    def test_stray_word_after_no_is_harmless_but_still_captured(self):
        # Best-effort extraction: this is captured even though "idea what"
        # isn't a fragrance term - decision_engine's penalty only fires on an
        # actual note/accord match, so a stray capture like this is a no-op.
        assert detect_negated_terms("I have no idea what I want") == ["idea what"]

    def test_stops_at_clause_boundary_not_just_stop_words(self):
        # Regression: without a punctuation-boundary split, "no vanilla, I
        # want musk" captured the next clause's pronoun too ("vanilla i"),
        # which matches no real note/accord - silently defeating both the
        # SQL exclusion filter and the Python penalty for the one term
        # (vanilla) that genuinely should have been excluded.
        assert detect_negated_terms("fresh summer scent but no vanilla, I want musk") == ["vanilla"]

    def test_pronoun_after_negated_term_is_not_captured_even_without_punctuation(self):
        assert detect_negated_terms("no vanilla I want musk") == ["vanilla"]

    def test_stops_at_period_and_question_mark(self):
        assert detect_negated_terms("no vanilla. also want something fresh") == ["vanilla"]
        assert detect_negated_terms("no vanilla? just curious") == ["vanilla"]

    def test_does_not_false_positive_on_word_containing_no(self):
        # "no" must be matched as a whole word, not as a substring of "piano".
        assert detect_negated_terms("I love piano music") == []


async def test_detect_scenarios_keyword_path(monkeypatch):
    # Isolate the deterministic keyword-matching half from the semantic
    # (embedding-based) half, which needs the real ML model loaded.
    async def _no_semantic_matches(*args, **kwargs):
        return []

    monkeypatch.setattr(intent_detector, "detect_scenarios_semantic", _no_semantic_matches)
    scenarios = await detect_scenarios("heading to the gym for a workout")
    assert "gym" in scenarios


async def test_detect_scenarios_empty_query(monkeypatch):
    async def _no_semantic_matches(*args, **kwargs):
        return []

    monkeypatch.setattr(intent_detector, "detect_scenarios_semantic", _no_semantic_matches)
    assert await detect_scenarios("") == []
