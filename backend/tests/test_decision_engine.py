"""
Unit tests for the deterministic scoring/matching logic in decision_engine.py.
These lock in the behavior of several bugs found and fixed during review:
substring false positives in note/accord matching, score clustering from
always-active neutral weights, and the negation penalty.
"""
from app.services.decision_engine import (
    _adjust_performance_by_type,
    _age_fit,
    _bridge_fit,
    _dominant_accord,
    _gender_fit,
    _gender_leaning_modifier,
    _identity_boost,
    _match_accords,
    _match_notes,
    _negation_penalty,
    _note_family_fit,
    _price_fit,
    _scenario_fit,
    cap_by_scent_character,
    cap_per_brand,
    hybrid_score,
    rank_and_explain,
)


class TestMatchNotesAccords:
    def test_substring_false_positive_is_not_matched(self):
        # "men" must not match inside "pimento" (pi-men-to) - a raw substring
        # check would incorrectly match here.
        assert _match_notes(["men"], ["Pimento"]) == []

    def test_whole_word_at_boundary_still_matches(self):
        assert _match_notes(["men"], ["Musk for Men"]) == ["Musk for Men"]

    def test_generic_descriptor_is_filtered_as_stop_word(self):
        # "notes" is a generic descriptor, not a real query intent - it must
        # not false-positive match every "X Notes" accord entry.
        assert _match_notes(["notes"], ["Green Notes"]) == []
        assert _match_accords(["scent"], ["Woody Notes"]) == []

    def test_suffix_flexibility_is_preserved(self):
        # Plural/inflected forms should still match ("bergamot" is a prefix
        # of "bergamots") - only mid-word substrings should be rejected.
        assert _match_notes(["bergamot"], ["Bergamots"]) == ["Bergamots"]

    def test_accord_matching_mirrors_note_matching(self):
        assert _match_accords(["woody"], ["Woody"]) == ["Woody"]
        assert _match_accords(["men"], ["Ambery"]) == []


class TestFitFunctions:
    def test_price_fit_neutral_without_budget(self):
        assert _price_fit(5000, None) == 1.0

    def test_price_fit_zero_when_over_budget(self):
        assert _price_fit(1500, 1000) == 0.0

    def test_price_fit_rewards_closer_to_budget_by_default(self):
        assert _price_fit(900, 1000) == 0.9

    def test_price_fit_deal_breaker_rewards_cheaper(self):
        assert _price_fit(200, 1000, deal_breaker=True) == 0.8

    def test_gender_fit_neutral_without_request(self):
        assert _gender_fit("male", None) == 1.0

    def test_gender_fit_neutral_for_unisex_perfume(self):
        assert _gender_fit("unisex", "female") == 1.0

    def test_gender_fit_penalizes_mismatch(self):
        assert _gender_fit("male", "female") == 0.4

    def test_age_fit_neutral_without_age(self):
        assert _age_fit(["woody"], None) == 1.0


class TestScenarioFit:
    def test_neutral_without_scenario(self):
        assert _scenario_fit(["woody"], ["cedar"], []) == 1.0

    def test_blends_accords_and_notes(self):
        # "gym" scenario accords include citrus/fresh/green/aromatic/etc,
        # notes include bergamot/lemon/tea/etc (see scenario_map.py).
        accord_only = _scenario_fit(["citrus", "fresh"], [], ["gym"])
        note_only = _scenario_fit([], ["bergamot", "lemon", "tea"], ["gym"])
        both = _scenario_fit(["citrus", "fresh"], ["bergamot", "lemon", "tea"], ["gym"])
        assert accord_only == 0.7   # 2/2 accords -> full accord credit, weighted 0.7
        assert note_only == 0.3     # 3/3 notes -> full note credit, weighted 0.3
        assert both == 1.0          # both maxed -> full combined credit

    def test_note_overlap_uses_fuzzy_equivalence_not_exact_match(self):
        # Regression: a raw set intersection would never match "Sicilian
        # Lemon"/"Indonesian Patchouli Leaf" against SCENARIO_MAP's generic
        # "lemon"/"patchouli" note entries, silently losing scenario credit
        # for perfumes tagged with more specific, real-world note names.
        exact = _scenario_fit([], ["lemon", "bergamot", "tea"], ["gym"])
        specific = _scenario_fit([], ["Sicilian Lemon", "Bergamot", "Green Tea"], ["gym"])
        assert exact == specific == 0.3


class TestNoteFamilyFit:
    def test_neutral_without_note_families(self):
        assert _note_family_fit(["bergamot"], ["citrus"], None) == 1.0
        assert _note_family_fit(["bergamot"], ["citrus"], []) == 1.0

    def test_full_credit_when_all_requested_families_matched(self):
        assert _note_family_fit(["bergamot"], [], ["citrus"]) == 1.0

    def test_partial_credit_when_only_some_families_matched(self):
        # "citrus" matches via bergamot, "woody" has nothing on this perfume.
        assert _note_family_fit(["bergamot"], [], ["citrus", "woody"]) == 0.5

    def test_zero_credit_when_no_families_matched(self):
        assert _note_family_fit(["bergamot"], [], ["woody"]) == 0.0

    def test_fuzzy_match_against_specific_note_name(self):
        # "Sicilian Lemon" should still satisfy the generic "citrus" family
        # (which lists "lemon"), same fuzzy-equivalence reasoning as _scenario_fit.
        assert _note_family_fit(["Sicilian Lemon"], [], ["citrus"]) == 1.0

    def test_unknown_family_name_is_ignored(self):
        assert _note_family_fit(["bergamot"], [], ["not-a-real-family"]) == 1.0


class TestBridgeFit:
    def test_neutral_without_both_fresh_and_longevity_intent(self):
        assert _bridge_fit(["bergamot"], ["musk"], [], wants_fresh=True, wants_longevity=False) == 1.0
        assert _bridge_fit(["bergamot"], ["musk"], [], wants_fresh=False, wants_longevity=True) == 1.0

    def test_full_credit_for_fresh_top_and_dense_base(self):
        assert _bridge_fit(["bergamot"], ["musk"], [], wants_fresh=True, wants_longevity=True) == 1.0

    def test_partial_credit_for_only_one_tier_matching(self):
        assert _bridge_fit(["bergamot"], ["rose"], [], wants_fresh=True, wants_longevity=True) == 0.5
        assert _bridge_fit(["rose"], ["musk"], [], wants_fresh=True, wants_longevity=True) == 0.5

    def test_low_score_when_neither_tier_matches(self):
        assert _bridge_fit(["rose"], ["rose"], [], wants_fresh=True, wants_longevity=True) == 0.2

    def test_accords_fill_the_gap_when_notes_are_completely_missing(self):
        # Regression: 21% of the catalog (8,721 rows) has no notes at all,
        # but 96% of those still have main_accords - without this fallback,
        # a perfume would score the worst possible bridge fit (0.2) purely
        # because notes data happens to be missing, not because it's
        # actually a poor fresh-top/dense-base match.
        fit = _bridge_fit([], [], ["citrus", "woody"], wants_fresh=True, wants_longevity=True)
        assert fit == 1.0

    def test_accords_only_fill_the_missing_side_not_override_a_real_one(self):
        # Real note data says the top is fresh; accords supply the (missing)
        # dense-base signal that base_notes alone couldn't answer.
        fit = _bridge_fit(["bergamot"], [], ["woody"], wants_fresh=True, wants_longevity=True)
        assert fit == 1.0

    def test_accords_that_dont_indicate_either_tier_still_score_low(self):
        assert _bridge_fit([], [], ["floral"], wants_fresh=True, wants_longevity=True) == 0.2


class TestNegationPenalty:
    def test_no_op_without_negated_terms(self):
        assert _negation_penalty(["citrus"], ["bergamot"], None) == (1.0, None)
        assert _negation_penalty(["citrus"], ["bergamot"], []) == (1.0, None)

    def test_no_op_when_negated_term_absent(self):
        assert _negation_penalty(["citrus"], ["bergamot"], ["vanilla"]) == (1.0, None)

    def test_penalizes_when_negated_accord_present(self):
        fit, hit = _negation_penalty(["vanilla", "amber"], [], ["vanilla"])
        assert fit == 0.25
        assert hit == "vanilla"

    def test_penalizes_when_negated_note_present(self):
        fit, hit = _negation_penalty([], ["tonka bean"], ["tonka"])
        assert fit == 0.25
        assert hit == "tonka"


class TestHybridScoreDynamicWeighting:
    def test_bare_query_no_match_scores_zero_not_seventy_three(self):
        # Regression test: previously, six always-active neutral 1.0 defaults
        # (scenario/longevity/projection/price/gender/age) contributed a flat
        # 73% floor to every score regardless of actual match quality.
        assert hybrid_score(0.0, note_match=0.0) == 0.0

    def test_bare_query_perfect_match_scores_hundred(self):
        assert hybrid_score(1.0, note_match=1.0) == 100.0

    def test_full_signal_perfect_match_scores_hundred(self):
        score = hybrid_score(
            1.0, price_fit=1.0, note_match=1.0, gender_fit=1.0, longevity_fit=1.0,
            scenario_fit=1.0, projection_fit=1.0, age_fit=1.0,
            has_budget=True, has_gender=True, has_longevity=True,
            has_scenario=True, has_projection=True, has_age=True,
        )
        assert score == 100.0

    def test_only_active_signal_counts_toward_denominator(self):
        # With only scenario active and a perfect scenario_fit but zero
        # sim/note_match, the score should reflect the weighted average of
        # ONLY sim+note (baseline, always active) and scenario (active) -
        # not be diluted by the five inactive neutral defaults.
        score = hybrid_score(0.0, note_match=0.0, scenario_fit=1.0, has_scenario=True)
        assert score == 50.9  # 0.28 / (0.07+0.20+0.28) rounded


class TestIdentityBoost:
    def test_exact_match_gets_highest_tier(self):
        bonus, label = _identity_boost("Dior Sauvage Elixir", "Dior", "Sauvage Elixir")
        assert bonus == 35.0
        assert label == "Dior — Sauvage Elixir"

    def test_no_match_gives_zero_bonus(self):
        bonus, label = _identity_boost("fresh summer scent", "Dior", "Sauvage Elixir")
        assert bonus == 0.0
        assert label is None

    def test_short_query_guarded_against_generic_boost(self):
        bonus, _ = _identity_boost("ab", "Dior", "Sauvage")
        assert bonus == 0.0


class TestRankAndExplainIntegration:
    def _perfume(self, **overrides):
        base = {
            "id": 1, "brand": "TestBrand", "perfume": "Vanilla Dream",
            "price_inr": 1000, "notes": ["vanilla", "tonka bean"],
            "main_accords": ["vanilla", "sweet"], "gender": "unisex",
            "longevity_score": 60, "sillage_score": 50, "similarity": 0.8,
        }
        base.update(overrides)
        return base

    def test_negation_demotes_matching_perfume_below_alternative(self):
        results = [
            self._perfume(id=1, perfume="Vanilla Dream"),
            self._perfume(
                id=2, perfume="Citrus Burst", notes=["bergamot", "lemon"],
                main_accords=["citrus", "fresh"], longevity_score=40, sillage_score=30,
                similarity=0.6,
            ),
        ]
        ranked = rank_and_explain(results, query="fresh but no vanilla", negated_terms=["vanilla"])
        assert ranked[0]["perfume"] == "Citrus Burst"
        assert ranked[1]["perfume"] == "Vanilla Dream"
        assert any("Excludes" in item["label"] or "excluded" in item["label"] for item in ranked[1]["match_breakdown"])

    def test_nearest_to_budget_ceiling_ranks_first(self):
        # rank_and_explain assumes the SQL layer already filtered to
        # price_inr <= budget; within that pool, the default (non-deal-
        # breaker) ordering is nearest-to-the-ceiling-first, not cheapest.
        results = [
            self._perfume(id=1, perfume="Near Budget", price_inr=950),
            self._perfume(id=2, perfume="Well Under Budget", price_inr=400),
        ]
        ranked = rank_and_explain(results, query="vanilla", budget=1000)
        assert ranked[0]["perfume"] == "Near Budget"

    def test_deal_breaker_flips_to_cheapest_first(self):
        results = [
            self._perfume(id=1, perfume="Near Budget", price_inr=950),
            self._perfume(id=2, perfume="Well Under Budget", price_inr=400),
        ]
        ranked = rank_and_explain(results, query="vanilla", budget=1000, deal_breaker=True)
        assert ranked[0]["perfume"] == "Well Under Budget"

    def test_over_budget_candidate_gets_zero_price_fit_penalty(self):
        results = [self._perfume(id=1, price_inr=1200)]
        ranked = rank_and_explain(results, query="vanilla dream", budget=1000)
        # price_fit=0.0 for an over-budget item pulls the score down relative
        # to the same perfume scored with no budget constraint at all.
        unconstrained = rank_and_explain(
            [self._perfume(id=1, price_inr=1200)], query="vanilla dream", budget=None,
        )
        assert ranked[0]["match_score"] < unconstrained[0]["match_score"]

    def test_age_appears_in_match_breakdown_when_requested(self):
        # AGE_WEIGHT is an active, weighted scoring dimension whenever `age`
        # is given, but _build_breakdown previously had no age entry at all -
        # every other active dimension (gender/budget/longevity/projection/
        # scenario) was visible in the checklist except this one.
        results = [self._perfume(id=1, main_accords=["woody", "amber"])]
        ranked = rank_and_explain(results, query="vanilla dream", age=30)
        labels = [item["label"] for item in ranked[0]["match_breakdown"]]
        assert any("Age-appropriate profile (30)" in label for label in labels)

    def test_age_absent_from_match_breakdown_when_not_requested(self):
        results = [self._perfume(id=1)]
        ranked = rank_and_explain(results, query="vanilla dream")
        labels = [item["label"] for item in ranked[0]["match_breakdown"]]
        assert not any("Age-appropriate" in label for label in labels)

    def test_bridge_scoring_rewards_fresh_top_dense_base_combo(self):
        # The exact "chemical contradiction" case: a fresh gym scent that
        # must last 12 hours. A single-tier match (pure citrus fades fast,
        # pure heavy oud isn't fresh) can't satisfy both - a "bridge" perfume
        # (fresh top + dense base) should score higher than an otherwise-
        # identical perfume missing the dense base tier.
        bridge_perfume = self._perfume(
            id=1, perfume="Bridge Scent", notes=["bergamot", "musk"],
            main_accords=["citrus", "musky"], top_notes=["bergamot"], base_notes=["musk"],
            longevity_score=70, sillage_score=55, similarity=0.7,
        )
        # Genuinely fresh-only: no base_notes AND no base-tier accord either
        # ("citrus" is the only accord, no "musky"/"woody"/etc), so _bridge_fit's
        # accords fallback correctly has nothing to find on the dense-base side.
        fresh_only_perfume = self._perfume(
            id=2, perfume="Fresh Only", notes=["bergamot"],
            main_accords=["citrus"], top_notes=["bergamot"], base_notes=[],
            longevity_score=70, sillage_score=55, similarity=0.7,
        )
        ranked = rank_and_explain(
            [bridge_perfume, fresh_only_perfume], query="fresh gym scent that lasts 12 hours",
            scenarios=["gym"], hours_required=12,
        )
        scores = {r["perfume"]: r["match_score"] for r in ranked}
        breakdowns = {r["perfume"]: r["match_breakdown"] for r in ranked}
        assert scores["Bridge Scent"] > scores["Fresh Only"]
        assert any("long-lasting base" in item["label"] for item in breakdowns["Bridge Scent"])

    def test_bridge_accords_fallback_credits_notes_less_perfume_with_real_base_accord(self):
        # A perfume with NO notes at all (the 21% of the catalog this affects)
        # but a real "musky" accord should score the same full bridge credit
        # as one with explicit base_notes - the accords fallback in
        # _bridge_fit should recognize its dense-base character either way.
        no_notes_perfume = self._perfume(
            id=1, perfume="No Notes Bridge", notes=[],
            main_accords=["citrus", "musky"], top_notes=[], base_notes=[],
            longevity_score=70, sillage_score=55, similarity=0.7,
        )
        explicit_notes_perfume = self._perfume(
            id=2, perfume="Explicit Notes Bridge", notes=["bergamot", "musk"],
            main_accords=["citrus", "musky"], top_notes=["bergamot"], base_notes=["musk"],
            longevity_score=70, sillage_score=55, similarity=0.7,
        )
        ranked = rank_and_explain(
            [no_notes_perfume, explicit_notes_perfume], query="fresh gym scent that lasts 12 hours",
            scenarios=["gym"], hours_required=12,
        )
        breakdowns = {r["perfume"]: r["match_breakdown"] for r in ranked}
        bridge_item = next(item for item in breakdowns["No Notes Bridge"] if "long-lasting base" in item["label"])
        assert bridge_item["status"] == "met"


class TestGenderLeaningScorer:
    def test_unisex_leaning_feminine_penalized_for_male(self):
        # Unisex but heavy floral/fruity (jasmine, rose, sweet) leans opposite to 'male' request.
        fit = _gender_leaning_modifier(
            perfume_gender="unisex",
            requested_gender="male",
            notes=["jasmine", "rose", "pear"],
            accords=["floral", "fruity", "sweet"]
        )
        assert fit == 0.85

    def test_unisex_leaning_masculine_not_penalized_for_male(self):
        # Unisex with heavy woody/spicy elements fits 'male' request well.
        fit = _gender_leaning_modifier(
            perfume_gender="unisex",
            requested_gender="male",
            notes=["cedar", "vetiver", "pepper"],
            accords=["woody", "spicy", "leather"]
        )
        assert fit == 1.0

    def test_unisex_leaning_masculine_penalized_for_female(self):
        # Unisex but woody/leathery leans opposite to 'female' request.
        fit = _gender_leaning_modifier(
            perfume_gender="unisex",
            requested_gender="female",
            notes=["cedar", "vetiver", "pepper"],
            accords=["woody", "spicy", "leather"]
        )
        assert fit == 0.85

    def test_unisex_leaning_feminine_not_penalized_for_female(self):
        # Unisex with heavy floral/fruity fits 'female' request well.
        fit = _gender_leaning_modifier(
            perfume_gender="unisex",
            requested_gender="female",
            notes=["jasmine", "rose", "pear"],
            accords=["floral", "fruity", "sweet"]
        )
        assert fit == 1.0

    def test_non_unisex_skipped(self):
        # strictly male or female perfume is skipped by the leaning modifier
        assert _gender_leaning_modifier("male", "female", ["rose"], ["floral"]) == 1.0
        assert _gender_leaning_modifier("female", "male", ["cedar"], ["woody"]) == 1.0


class TestConcentrationPerformanceAdjustments:
    def test_parfum_boosts_longevity_decreases_sillage(self):
        longevity, sillage = _adjust_performance_by_type(70.0, 70.0, "Extrait de Parfum")
        assert longevity > 70.0
        assert sillage < 70.0
        assert longevity == 80.5
        assert sillage == 59.5

    def test_eau_de_parfum_gets_its_own_distinct_moderate_boost(self):
        # Regression, in two stages. Originally an exact-match check
        # (`"parfum" == t`) only ever matched the bare word "parfum",
        # silently skipping "Eau de Parfum" - the single most common
        # concentration type in the dataset (828 of the ~2,800 rows with any
        # identifiable type) - leaving it completely unadjusted. A first fix
        # (`"parfum" in t`) caught it, but then conflated it with Extrait/
        # pure Parfum's +15%/-15% - EDP (15-20% oil) is a real step down in
        # concentration from Extrait/Parfum (20-40%), so it should land
        # between Extrait and Eau de Toilette, not equal Extrait outright.
        longevity, sillage = _adjust_performance_by_type(70.0, 70.0, "Eau de Parfum")
        extrait_longevity, extrait_sillage = _adjust_performance_by_type(70.0, 70.0, "Extrait de Parfum")
        assert longevity == 75.6
        assert sillage == 65.1
        assert 70.0 < longevity < extrait_longevity
        assert extrait_sillage < sillage < 70.0

    def test_unrecognized_type_string_returns_as_is(self):
        # Exact-match lookup: an input outside the fixed vocabulary
        # `_parse_concentration_type` can ever produce is a no-op, not a
        # best-effort substring guess.
        assert _adjust_performance_by_type(70.0, 70.0, "Unknown Type") == (70.0, 70.0)

    def test_edt_decreases_longevity_boosts_sillage(self):
        longevity, sillage = _adjust_performance_by_type(70.0, 70.0, "Eau de Toilette")
        assert longevity < 70.0
        assert sillage > 70.0
        assert longevity == 63.0
        assert sillage == 77.0

    def test_cologne_decreases_longevity_boosts_sillage(self):
        longevity, sillage = _adjust_performance_by_type(70.0, 70.0, "Eau de Cologne")
        assert longevity < 70.0
        assert sillage > 70.0
        assert longevity == 52.5
        assert sillage == 80.5

    def test_body_spray_penalized_on_both(self):
        longevity, sillage = _adjust_performance_by_type(70.0, 70.0, "Body Spray")
        assert longevity == 35.0
        assert sillage == 49.0

    def test_no_type_returns_as_is(self):
        assert _adjust_performance_by_type(70.0, 70.0, None) == (70.0, 70.0)
        assert _adjust_performance_by_type(None, 70.0, "EDT") == (None, 70.0)




class TestCapPerBrand:
    def _perfume(self, id, brand):
        return {"id": id, "brand": brand, "perfume": f"p{id}", "match_score": 100 - id}

    def test_no_cap_needed_when_already_diverse(self):
        results = [self._perfume(i, f"brand{i}") for i in range(6)]
        capped = cap_per_brand(results, limit=6, max_per_brand=2)
        assert [r["id"] for r in capped] == [0, 1, 2, 3, 4, 5]

    def test_caps_an_over_represented_brand_and_backfills(self):
        # 4 from "A" (the exact failure mode found live: an LLM given this
        # pool would previously have been free to return all 4), should
        # only keep 2 and backfill the remaining 4 slots from other brands.
        results = (
            [self._perfume(i, "A") for i in range(4)]
            + [self._perfume(i, f"other{i}") for i in range(10, 14)]
        )
        capped = cap_per_brand(results, limit=6, max_per_brand=2)
        assert len(capped) == 6
        brand_counts = {}
        for r in capped:
            brand_counts[r["brand"]] = brand_counts.get(r["brand"], 0) + 1
        assert brand_counts["A"] == 2
        assert all(count <= 2 for count in brand_counts.values())

    def test_preserves_rank_order_for_kept_results(self):
        # Rank order (as given) must survive the cap - it must not silently
        # re-sort by anything else.
        results = [self._perfume(0, "A"), self._perfume(1, "B"), self._perfume(2, "A"), self._perfume(3, "A")]
        capped = cap_per_brand(results, limit=4, max_per_brand=1)
        # Only 1 "A" and 1 "B" fit the cap from the first pass; the extra
        # "A"s backfill afterward once the cap is already applied elsewhere.
        assert [r["id"] for r in capped[:2]] == [0, 1]

    def test_insufficient_pool_returns_fewer_than_limit_rather_than_erroring(self):
        results = [self._perfume(0, "A"), self._perfume(1, "A")]
        capped = cap_per_brand(results, limit=6, max_per_brand=2)
        assert len(capped) == 2

    def test_empty_input(self):
        assert cap_per_brand([], limit=6) == []

    def test_brand_matching_is_case_insensitive(self):
        # Real data-casing inconsistency confirmed live: "Le Labo" and
        # "le labo" both exist as literal distinct brand strings on real
        # rows - a case-sensitive key would count them as two different
        # brands and never cap them against each other at all.
        results = (
            [self._perfume(0, "Le Labo"), self._perfume(1, "le labo"), self._perfume(2, "LE LABO")]
            + [self._perfume(i, f"other{i}") for i in range(10, 14)]
        )
        capped = cap_per_brand(results, limit=6, max_per_brand=2)
        le_labo_count = sum(1 for r in capped if r["brand"].lower() == "le labo")
        assert le_labo_count == 2  # capped, not 3 - enough real alternatives exist that backfill isn't forced

    def test_relaxes_fairly_across_all_over_represented_brands_not_just_one(self):
        # Regression: an earlier version's backfill pulled unconditionally
        # from the raw overflow list, which could readmit 3+ copies of the
        # same over-represented brand it had just capped - only caught by
        # live testing (3 "All Good Scents" in one of 8 runs), not by the
        # simpler unit tests above. Pool: 5 "A", 1 each of "B"/"C"/"D" - only
        # 3 non-"A" alternatives exist, so reaching limit=6 genuinely
        # requires a 3rd "A" (2 + 3 others = 5 < 6) - correct, forced
        # behavior - but it must not go to 4 or 5 just because the raw
        # overflow list still had more "A"s sitting in it.
        results = (
            [self._perfume(i, "A") for i in range(5)]
            + [self._perfume(10, "B"), self._perfume(11, "C"), self._perfume(12, "D")]
        )
        capped = cap_per_brand(results, limit=6, max_per_brand=2)
        assert len(capped) == 6
        brand_counts: dict[str, int] = {}
        for r in capped:
            brand_counts[r["brand"]] = brand_counts.get(r["brand"], 0) + 1
        assert brand_counts["A"] == 3  # forced minimum, not 4 or 5
        assert brand_counts["B"] == brand_counts["C"] == brand_counts["D"] == 1

    def test_limit_smaller_than_max_per_brand_still_returns_results(self):
        # Real bug, confirmed live: POST /search/dupe with limit=1 returned
        # [] over real HTTP (limit=2 through 5 worked fine). Root cause: with
        # backfill=True and limit(1) < max_per_brand(2), max_cap was set to
        # limit itself (1) - below the starting cap (2) - so the while loop's
        # own entry condition failed before a single pass ran.
        results = [self._perfume(i, f"brand{i}") for i in range(3)]
        capped = cap_per_brand(results, limit=1, max_per_brand=2)
        assert len(capped) == 1
        assert capped[0]["id"] == 0

    def test_limit_one_with_a_single_over_represented_brand(self):
        results = [self._perfume(i, "A") for i in range(3)]
        capped = cap_per_brand(results, limit=1, max_per_brand=2)
        assert len(capped) == 1
        assert capped[0]["id"] == 0

    def test_strict_mode_never_relaxes_even_if_short_of_limit(self):
        # backfill=False is for the wide pre-LLM pool: relaxing the cap to
        # hit a large fetch_limit (e.g. 25) would let an over-represented
        # brand climb back up before the LLM ever sees it, defeating the
        # point of capping at all. Returning fewer than `limit` here is the
        # correct, intended behavior, not a bug.
        results = [self._perfume(i, "A") for i in range(5)] + [self._perfume(10, "B")]
        capped = cap_per_brand(results, limit=25, max_per_brand=2, backfill=False)
        assert len(capped) == 3  # 2 "A" + 1 "B", nothing more
        assert sum(1 for r in capped if r["brand"] == "A") == 2


class TestDominantAccord:
    def test_returns_lowercased_first_accord(self):
        assert _dominant_accord({"main_accords": ["Woody", "Amber"]}) == "woody"

    def test_empty_accords_returns_empty_string(self):
        assert _dominant_accord({"main_accords": []}) == ""

    def test_missing_accords_key_returns_empty_string(self):
        assert _dominant_accord({}) == ""


class TestCapByScentCharacter:
    def _perfume(self, id, brand, accords):
        return {"id": id, "brand": brand, "perfume": f"p{id}", "main_accords": accords, "match_score": 100 - id}

    def test_caps_an_over_represented_accord_across_different_brands(self):
        # The gap cap_per_brand alone can't catch: 6 different brands, but 4
        # of them are all dominantly "citrus aromatic" - real label
        # diversity, much less real scent-character diversity. Mirrors
        # TestCapPerBrand's own over-represented-brand test structure.
        results = (
            [self._perfume(i, f"brand{i}", ["citrus aromatic", "fresh"]) for i in range(4)]
            + [self._perfume(i, f"other{i}", [f"accord{i}"]) for i in range(10, 12)]
        )
        capped = cap_by_scent_character(results, limit=6, max_per_accord=2)
        assert len(capped) == 6
        accord_counts: dict[str, int] = {}
        for r in capped:
            key = _dominant_accord(r)
            accord_counts[key] = accord_counts.get(key, 0) + 1
        assert accord_counts["citrus aromatic"] == 4  # forced minimum via backfill (only 2 alternatives exist)
        assert accord_counts["accord10"] == 1
        assert accord_counts["accord11"] == 1

    def test_no_cap_needed_when_already_diverse(self):
        results = [self._perfume(i, f"brand{i}", [f"accord{i}"]) for i in range(5)]
        capped = cap_by_scent_character(results, limit=5, max_per_accord=3)
        assert [r["id"] for r in capped] == [0, 1, 2, 3, 4]

    def test_preserves_rank_order_for_kept_results(self):
        results = [
            self._perfume(0, "A", ["woody"]), self._perfume(1, "B", ["citrus"]),
            self._perfume(2, "C", ["woody"]), self._perfume(3, "D", ["woody"]),
        ]
        capped = cap_by_scent_character(results, limit=4, max_per_accord=1)
        assert [r["id"] for r in capped[:2]] == [0, 1]

    def test_limit_smaller_than_max_per_accord_still_returns_results(self):
        # Same class of bug cap_per_brand shipped with (see its own tests) -
        # shared via _cap_by_key, so covered here for this wrapper too.
        results = [self._perfume(i, f"brand{i}", ["woody"]) for i in range(3)]
        capped = cap_by_scent_character(results, limit=1, max_per_accord=3)
        assert len(capped) == 1
        assert capped[0]["id"] == 0

    def test_perfumes_with_no_accords_are_not_falsely_grouped_as_diverse(self):
        # Empty main_accords all map to the same "" key - they should still
        # be capped against each other (and forced through backfill relaxation
        # to reach the limit), not treated as N naturally distinct clusters.
        results = [self._perfume(i, f"brand{i}", []) for i in range(5)]
        capped = cap_by_scent_character(results, limit=5, max_per_accord=2)
        assert len(capped) == 5  # backfill still reaches the limit
        assert [r["id"] for r in capped] == [0, 1, 2, 3, 4]  # rank order preserved throughout
