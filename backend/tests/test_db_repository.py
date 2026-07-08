"""Unit tests for db_repository.py's pure helper functions (no DB needed)."""
from app.services.db_repository import (
    _build_exclusion_patterns,
    _candidate_pool_size,
    _clean_notes,
    _clean_query_for_lookup,
    _format_perfume_row,
    _is_same_brand_group,
    _parse_concentration_type,
    _resolve_pyramid,
    find_reference_perfume,
)


class TestParseConcentrationType:
    def test_edt(self):
        assert _parse_concentration_type("Sauvage EDT") == "Eau de Toilette"

    def test_edp(self):
        assert _parse_concentration_type("Bleu de Chanel EDP") == "Eau de Parfum"

    def test_full_name_eau_de_parfum(self):
        assert _parse_concentration_type("Black Opium Eau de Parfum") == "Eau de Parfum"

    def test_extrait(self):
        assert _parse_concentration_type("Layton Extrait de Parfum") == "Extrait de Parfum"

    def test_cologne(self):
        assert _parse_concentration_type("Acqua di Gio Cologne") == "Eau de Cologne"

    def test_elixir(self):
        assert _parse_concentration_type("Sauvage Elixir") == "Elixir"

    def test_body_spray(self):
        assert _parse_concentration_type("Axe Body Spray") == "Body Spray"

    def test_no_match_returns_none(self):
        assert _parse_concentration_type("Some Random Name") is None

    def test_empty_name_returns_none(self):
        assert _parse_concentration_type("") is None
        assert _parse_concentration_type(None) is None


class TestResolvePyramid:
    def test_uses_real_columns_when_present(self):
        row = {"top_notes": ["bergamot"], "heart_notes": ["rose"], "base_notes": ["musk"]}
        assert _resolve_pyramid(row, ["bergamot", "rose", "musk"]) == (["bergamot"], ["rose"], ["musk"])

    def test_classifies_on_the_fly_when_columns_are_null(self):
        # Rows seeded before the pyramid columns existed (or restored from
        # the pre-baked dump that predates them) have NULL here - this is
        # the fallback that makes the feature work without a full reseed.
        row = {"top_notes": None, "heart_notes": None, "base_notes": None}
        top, heart, base = _resolve_pyramid(row, ["bergamot", "rose", "musk"])
        assert top == ["bergamot"]
        assert heart == ["rose"]
        assert base == ["musk"]

    def test_no_fallback_needed_when_no_notes_at_all(self):
        row = {"top_notes": None, "heart_notes": None, "base_notes": None}
        assert _resolve_pyramid(row, []) == ([], [], [])

    def test_classifies_accords_when_notes_are_empty(self):
        row = {"top_notes": None, "heart_notes": None, "base_notes": None, "main_accords": ["woody", "marine", "floral"]}
        top, heart, base = _resolve_pyramid(row, [])
        assert top == ["marine"]
        assert heart == ["floral"]
        assert base == ["woody"]


class TestCleanNotes:
    def test_strips_serialized_dict_element(self):
        # Real corruption found live: 514 legacy_seed rows have this exact
        # shape as a spurious extra notes element, alongside the correctly
        # flattened individual note strings.
        notes = [
            "{'middle': ['Guatemalan Cardamom', 'Israeli Basil'], 'base': ['Musk'], 'top': ['Bergamot']}",
            "pepper", "bergamot", "musk",
        ]
        assert _clean_notes(notes) == ["pepper", "bergamot", "musk"]

    def test_leaves_clean_notes_untouched(self):
        assert _clean_notes(["bergamot", "rose", "musk"]) == ["bergamot", "rose", "musk"]

    def test_empty_list_is_a_no_op(self):
        assert _clean_notes([]) == []

    def test_real_note_names_are_never_removed(self):
        # No legitimate note name in this catalog is wrapped in braces - the
        # filter is a whole-element shape check, not a general parser, so it
        # should never touch a normal note string.
        notes = ["oud", "vanilla", "sandalwood", "green notes", "aquatic notes"]
        assert _clean_notes(notes) == notes


def _db_row(**overrides) -> dict:
    row = {
        "id": 1, "brand": "Creed", "perfume": "Aventus", "price_inr": 9000,
        "notes": ["pineapple", "birch"], "main_accords": ["fruity", "woody"],
        "type": None, "gender": "male", "longevity_score": 70, "sillage_score": 60,
        "similarity": 0.8,
    }
    row.update(overrides)
    return row


class TestFormatPerfumeRowLimitedData:
    """has_limited_data flags the ~21% of the catalog with no real note data
    at all (see DECISION_ENGINE.md §3.4) - invisible to the user otherwise,
    since the accord-tier fallback scoring degrades gracefully but silently."""

    def test_flagged_when_no_notes_at_all(self):
        result = _format_perfume_row(_db_row(notes=[]))
        assert result["has_limited_data"] is True

    def test_not_flagged_when_real_notes_present(self):
        result = _format_perfume_row(_db_row(notes=["pineapple", "birch"]))
        assert result["has_limited_data"] is False

    def test_flagged_when_only_note_was_corrupted_garbage(self):
        # If _clean_notes strips the ONLY element (the dict-repr corruption
        # bug), the row correctly ends up flagged as limited-data too - it
        # genuinely has no usable note data left after cleaning.
        row = _db_row(notes=["{'middle': ['a'], 'base': ['b'], 'top': ['c']}"])
        result = _format_perfume_row(row)
        assert result["notes"] == []
        assert result["has_limited_data"] is True


class TestCandidatePoolSize:
    def test_small_limit_has_a_floor(self):
        # A floor well above what a tiny `limit` alone would suggest - see
        # the function's docstring: this is what actually gives the 10
        # highest-weighted scoring dimensions (occasion/notes/longevity/etc.)
        # genuine variety across the catalog to choose from, not just
        # whatever a narrow embedding-similarity neighborhood turns up.
        assert _candidate_pool_size(1) == 500
        assert _candidate_pool_size(5) == 500

    def test_scales_with_limit_above_the_floor(self):
        assert _candidate_pool_size(40) == 600  # 40 * 15

    def test_capped_at_the_hnsw_ef_search_hard_limit(self):
        # pgvector rejects hnsw.ef_search above 1000 outright - confirmed
        # live (`SET hnsw.ef_search = 2000` warns and the value doesn't
        # apply) - so this ceiling isn't an arbitrary tuning choice.
        assert _candidate_pool_size(60) == 900  # 60 * 15, still under the cap
        assert _candidate_pool_size(100) == 1000  # 100 * 15 = 1500, capped


class TestBuildExclusionPatterns:
    """`_build_exclusion_patterns` produces Postgres-flavored regex (`\\m`/`\\M`
    word-boundary anchors), which Python's `re` module doesn't understand
    (`\\m` is a syntax error there) - so these check pattern *construction*
    only, not execution. The actual matching semantics run inside Postgres
    via the `~*` operator, not in Python."""

    def test_none_without_negated_terms(self):
        assert _build_exclusion_patterns(None) is None
        assert _build_exclusion_patterns([]) is None

    def test_word_bounded_pattern_built_for_each_term(self):
        assert _build_exclusion_patterns(["vanilla"]) == [r"\mvanilla\M"]

    def test_multiple_terms_produce_multiple_patterns(self):
        patterns = _build_exclusion_patterns(["vanilla", "oud"])
        assert patterns == [r"\mvanilla\M", r"\moud\M"]

    def test_special_characters_are_escaped(self):
        # A negated term shouldn't be able to break out of the regex pattern.
        assert _build_exclusion_patterns(["a.b"]) == [r"\ma\.b\M"]


class TestCleanQueryForLookup:
    def test_cheaper_alternative_to_aventus(self):
        assert _clean_query_for_lookup("cheaper alternative to Aventus") == "aventus"

    def test_dupe_for_bleu_de_chanel(self):
        assert _clean_query_for_lookup("dupe for Bleu de Chanel") == "bleu de chanel"

    def test_alternative_to_sauvage_under_2000(self):
        assert _clean_query_for_lookup("Alternative to Sauvage under 2000") == "sauvage under 2000"

    def test_punctuation_removed(self):
        assert _clean_query_for_lookup("Creed Aventus!") == "creed aventus"


class FakeReferenceConn:
    """Simulates find_reference_perfume's four SQL tiers in Python over an
    in-memory row list, dispatching on distinguishing substrings of the
    (fixed, literal) SQL text - same pattern as test_ingestion.py's FakeConn,
    since a real Postgres/pg_trgm connection isn't available in unit tests.
    The fuzzy tiers approximate pg_trgm's word_similarity with a trigram
    intersection-over-shorter-string ratio (see `_sim`) - not bit-for-bit
    identical to Postgres' real algorithm, but good enough to exercise
    find_reference_perfume's own branching (which tier fired, whether
    ambiguity was detected), which is what these tests actually verify. A
    plain difflib.SequenceMatcher ratio was tried first and discarded: it
    systematically over-scored coincidental character overlap between short,
    unrelated strings (e.g. "black" vs "mont blanc" scored 0.53 - well above
    the 0.3 threshold - purely from shared letters, not real similarity),
    which doesn't happen with real Postgres word_similarity and made these
    tests fail in ways production doesn't.

    The two name-only tiers mirror _AMBIGUITY_GUARD_CTE exactly (verified
    against the real ~40,649-row table, not just reasoned about): the BEST
    notes-availability tier present is computed, its distinct brand strings
    are collected, and find_reference_perfume itself runs those through
    _is_same_brand_group - a same-name collision at a *worse* tier (e.g. a
    real "Aventus" from Creed with real note data, vs a distinct, data-sparse
    "Aventus" from another catalog brand with none) doesn't block the match,
    since the existing tiebreak already resolves it; a same-name collision
    at the SAME best tier is only blocked if the brand strings themselves
    aren't recognizably the same house (e.g. "Dior" vs "Christian Dior" IS;
    19 unrelated brands both named "Black" is NOT)."""

    def __init__(self, rows):
        self.rows = rows

    async def fetchrow(self, sql, *params):
        if "word_similarity(brand" in sql:
            query, threshold = params
            return self._fuzzy_both(query, threshold)
        if "word_similarity(perfume" in sql:
            query, threshold = params
            return self._best_tier_pick(
                [r for r in self.rows if len(r["perfume"]) >= 4 and self._sim(query, r["perfume"]) > threshold],
                sort_key=lambda r: (not bool(r.get("notes")), -self._sim(query, r["perfume"]), len(r["perfume"])),
            )
        if "|| brand || '%'" in sql:
            (query,) = params
            return self._exact_both(query)
        if "|| perfume || '%'" in sql:
            (query,) = params
            return self._best_tier_pick(
                [r for r in self.rows if len(r["perfume"]) >= 4 and self._contains(query, r["perfume"])],
                sort_key=lambda r: (not bool(r.get("notes")), len(r["perfume"])),
            )
        return None

    @staticmethod
    def _contains(query: str, value: str) -> bool:
        return value.lower() in query.lower()

    @staticmethod
    def _trigrams(s: str) -> set[str]:
        padded = f"  {s}  "
        return {padded[i:i + 3] for i in range(len(padded) - 2)}

    @classmethod
    def _sim(cls, a: str, b: str) -> float:
        """Intersection over the SHORTER string's trigram count, not a full
        Jaccard over the union - approximates word_similarity's actual
        intent (find the best-matching extent of the longer string, don't
        penalize for its surrounding context), which matters for typo
        tolerance against a short brand name embedded in a longer phrase."""
        ta, tb = cls._trigrams(a.lower()), cls._trigrams(b.lower())
        if not ta or not tb:
            return 0.0
        shorter, longer = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
        return len(shorter & longer) / len(shorter)

    def _exact_both(self, query):
        matches = [
            r for r in self.rows
            if len(r["brand"]) >= 3 and len(r["perfume"]) >= 3
            and self._contains(query, r["brand"]) and self._contains(query, r["perfume"])
        ]
        matches.sort(key=lambda r: (not bool(r.get("notes")), len(r["perfume"])))
        return matches[0] if matches else None

    def _fuzzy_both(self, query, threshold):
        matches = [
            r for r in self.rows
            if len(r["brand"]) >= 3 and len(r["perfume"]) >= 3
            and self._sim(query, r["brand"]) > threshold and self._sim(query, r["perfume"]) > threshold
        ]
        matches.sort(key=lambda r: (not bool(r.get("notes")), -(self._sim(query, r["brand"]) + self._sim(query, r["perfume"])), len(r["perfume"])))
        return matches[0] if matches else None

    @staticmethod
    def _best_tier_pick(matches, sort_key):
        """Mirrors _AMBIGUITY_GUARD_CTE: best_tier_brands is collected only
        from rows tied at the best (has-notes-first) tier, not the full
        match set - see this class's own docstring for why."""
        if not matches:
            return None
        best_tier = min(not bool(r.get("notes")) for r in matches)
        best_tier_brands = sorted({r["brand"].lower() for r in matches if (not bool(r.get("notes"))) == best_tier})
        ordered = sorted(matches, key=sort_key)
        top = dict(ordered[0])
        top["best_tier_brands"] = best_tier_brands
        return top


def _row(id_, brand, perfume, notes=None, main_accords=None, price_inr=None, gender=None):
    return {
        "id": id_, "brand": brand, "perfume": perfume,
        "notes": notes or [], "main_accords": main_accords or [],
        "price_inr": price_inr, "gender": gender,
    }


class TestIsSameBrandGroup:
    def test_single_brand_is_trivially_grouped(self):
        assert _is_same_brand_group(["creed"]) is True

    def test_suffix_naming_variant_is_grouped(self):
        # The real, systematic "<brand>for" pattern found across ~30 houses
        # in the live catalog (creedfor, diorfor, avonfor, ...) - no space,
        # so this must be a raw substring check, not word-bounded.
        assert _is_same_brand_group(["creed", "creedfor"]) is True

    def test_full_legal_name_variant_is_grouped(self):
        # "Dior" vs "Christian Dior" - the real regression case: both real,
        # both with note data, same house under different name granularity.
        assert _is_same_brand_group(["dior", "christian dior"]) is True

    def test_three_way_variant_is_grouped(self):
        assert _is_same_brand_group(["dior", "christian dior", "diorfor"]) is True

    def test_unrelated_brands_are_not_grouped(self):
        # 3 real, unrelated houses that happen to share a generic perfume
        # name ("Homme") - nothing about the BRAND strings themselves is
        # related, so this must fail safe toward "ambiguous".
        assert _is_same_brand_group(["ysl", "nicole farhi", "prada"]) is False

    def test_many_unrelated_brands_are_not_grouped(self):
        assert _is_same_brand_group(["jack black", "chanel", "tom ford", "versace"]) is False

    def test_short_core_below_minimum_length_is_not_grouped(self):
        # A 3-char core is deliberately below _BRAND_GROUP_MIN_CORE_LEN (4) -
        # too short and generic to trust as a real brand-family signal.
        assert _is_same_brand_group(["ysl", "ysla"]) is False


class TestFindReferencePerfume:
    async def test_exact_brand_and_perfume_match(self):
        conn = FakeReferenceConn([_row(1, "Creed", "Aventus", notes=["pineapple", "birch"])])
        result = await find_reference_perfume(conn, "cheaper alternative to Creed Aventus")
        assert result is not None
        assert result["id"] == 1
        assert result["brand"] == "Creed"

    async def test_corrupted_dict_string_notes_are_cleaned(self):
        # Real gap found in a broader sweep: _format_perfume_row and
        # get_perfume_by_id both apply _clean_notes(), but this function's
        # own return statement didn't - so a reference perfume resolved to
        # one of the real corrupted legacy_seed rows would leak the garbled
        # "{'middle': [...], ...}" string straight into the embedding query
        # text and _reference_fit's composition-overlap scoring.
        conn = FakeReferenceConn([_row(
            1, "Creed", "Aventus",
            notes=["{'middle': ['a'], 'base': ['b'], 'top': ['c']}", "pineapple", "birch"],
        )])
        result = await find_reference_perfume(conn, "cheaper alternative to Creed Aventus")
        assert result is not None
        assert result["notes"] == ["pineapple", "birch"]

    async def test_name_only_fallback_when_brand_is_omitted(self):
        # The user never typed "Creed" at all - only the exact brand+perfume
        # tier would miss, but the perfume name uniquely identifies one row.
        conn = FakeReferenceConn([_row(1, "Creed", "Aventus", notes=["pineapple", "birch"])])
        result = await find_reference_perfume(conn, "cheaper alternative to Aventus")
        assert result is not None
        assert result["brand"] == "Creed"

    async def test_ambiguous_name_only_match_returns_none(self):
        # Two unrelated brands both happen to sell a perfume literally named
        # "Legend" - the bug this guards against: silently grounding the
        # dupe search in whichever one happened to sort first. Both have real
        # note data, so there's no tiebreak signal to prefer one - genuinely
        # ambiguous (confirmed live: "legend" collides across 5 real distinct
        # brands in the actual catalog).
        conn = FakeReferenceConn([
            _row(1, "Mont Blanc", "Legend", notes=["oakmoss", "lavender"]),
            _row(2, "Generic House", "Legend", notes=["vanilla"]),
        ])
        result = await find_reference_perfume(conn, "cheaper alternative to Legend")
        assert result is None

    async def test_same_name_collision_at_a_worse_data_tier_is_not_ambiguous(self):
        # Real case, confirmed live against the actual ~40,649-row catalog:
        # "Aventus" collides between "Creed" (real note data) and "Creedfor"
        # (a distinct, lower-quality catalog entry with no note data at all -
        # not a duplicate of Creed, a genuinely different brand row).
        # Rejecting this as "ambiguous" would break the single most common
        # real "cheaper alternative to X" query in the whole category, even
        # though the existing notes-completeness tiebreak already resolves
        # it correctly and unambiguously to Creed.
        conn = FakeReferenceConn([
            _row(1, "Creed", "Aventus", notes=["pineapple", "birch", "ambroxan"]),
            _row(2, "Creedfor", "Aventus", notes=[]),
        ])
        result = await find_reference_perfume(conn, "cheaper alternative to Aventus")
        assert result is not None
        assert result["brand"] == "Creed"

    async def test_same_house_under_two_names_at_the_same_tier_is_not_ambiguous(self):
        # Real regression, confirmed live: "Sauvage" collides between "Dior"
        # and "Christian Dior" - BOTH with real note data, tied at the same
        # best tier (unlike the Creed/Creedfor case above, so the notes
        # tiebreak alone can't resolve it). A naive distinct-brand-string
        # count treats these as 2 brands and rejects the match - this
        # actually shipped and broke "cheaper alternative to Sauvage" in
        # production (resolved to an unrelated brand instead of Dior) before
        # _is_same_brand_group was added.
        conn = FakeReferenceConn([
            _row(1, "Dior", "Sauvage", notes=["bergamot", "ambroxan", "pepper"]),
            _row(2, "Christian Dior", "Sauvage", notes=["bergamot", "elemi"]),
        ])
        result = await find_reference_perfume(conn, "cheaper alternative to Sauvage")
        assert result is not None
        assert result["brand"].lower() in ("dior", "christian dior")

    async def test_genuinely_unrelated_brands_at_the_same_tier_stay_ambiguous(self):
        # Guards against _is_same_brand_group over-correcting: two real,
        # unrelated houses both sell a perfume literally named "Black", both
        # with real note data - _is_same_brand_group must reject this
        # (neither brand string is a substring of the other), not sweep it
        # into a false "same house" grouping. Brand names deliberately don't
        # textually overlap with the query itself (unlike e.g. "Jack Black"
        # would), so this test isolates tier 2's ambiguity check rather than
        # incidentally exercising the unrelated, difflib-approximated fuzzy
        # tier further down the fallback chain.
        conn = FakeReferenceConn([
            _row(1, "Kenneth Cole", "Black", notes=["leather", "tobacco"]),
            _row(2, "Ted Baker", "Black", notes=["rum", "coffee"]),
        ])
        result = await find_reference_perfume(conn, "cheaper alternative to Black")
        assert result is None

    async def test_unambiguous_when_only_one_brand_has_that_name(self):
        # A second, unrelated perfume name shouldn't cause false ambiguity.
        conn = FakeReferenceConn([
            _row(1, "Creed", "Aventus", notes=["pineapple", "birch"]),
            _row(2, "Dior", "Sauvage", notes=["bergamot", "ambroxan"]),
        ])
        result = await find_reference_perfume(conn, "cheaper alternative to Aventus")
        assert result is not None
        assert result["brand"] == "Creed"

    async def test_multiple_flankers_of_the_same_brand_are_not_ambiguous(self):
        conn = FakeReferenceConn([
            _row(1, "Creed", "Aventus", notes=["pineapple", "birch"]),
            _row(2, "Creed", "Aventus Cologne", notes=["citrus"]),
        ])
        result = await find_reference_perfume(conn, "cheaper alternative to Aventus")
        assert result is not None
        assert result["brand"] == "Creed"

    async def test_short_query_returns_none(self):
        conn = FakeReferenceConn([_row(1, "Creed", "Aventus")])
        assert await find_reference_perfume(conn, "ab") is None

    async def test_no_match_anywhere_returns_none(self):
        conn = FakeReferenceConn([_row(1, "Creed", "Aventus")])
        assert await find_reference_perfume(conn, "something completely unrelated") is None


class _RecordingConn:
    """Records the SQL text and bound params passed to every fetchrow/fetch
    call, returning no rows for any of them - used to verify WHICH query
    string a given tier actually receives, directly, instead of indirectly
    inferring it through a similarity-threshold approximation (which is
    exactly the kind of test that can pass or fail based on test-double
    fidelity rather than the real behavior - see FakeReferenceConn's own
    docstring for a concrete instance of that trap)."""

    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []

    async def fetchrow(self, sql, *params):
        self.calls.append((sql, params))
        return None

    async def fetch(self, sql, *params):
        self.calls.append((sql, params))
        return []


class TestFuzzyTierUsesCleanedQuery:
    async def test_filler_words_are_stripped_before_the_fuzzy_tier_runs(self):
        # The real bug: word_similarity finds the best-matching SUBSTRING of
        # the longer argument, so a filler phrase left in the raw query
        # ("dupe for", "cheaper alternative to") isn't inert noise - it
        # actively creates false matches. Confirmed live against the real
        # catalog: raw query "dupe for Ajmal" matched "Avonfor"/"Aqua for
        # Her" (neither the brand nor the perfume asked about) purely
        # because both contain the word "for". This test locks in the fix
        # directly (what string reaches the fuzzy tier), not indirectly
        # through a similarity-approximation threshold.
        conn = _RecordingConn()
        await find_reference_perfume(conn, "dupe for Zzzznotarealperfumexyz")

        fuzzy_calls = [call for call in conn.calls if "word_similarity(brand" in call[0]]
        assert fuzzy_calls, "expected the fuzzy brand+perfume tier to have run"
        query_arg = fuzzy_calls[0][1][0]
        assert query_arg == "zzzznotarealperfumexyz"
        assert "for" not in query_arg
        assert "dupe" not in query_arg

