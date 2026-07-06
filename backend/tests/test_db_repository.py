"""Unit tests for db_repository.py's pure helper functions (no DB needed)."""
from app.services.db_repository import (
    _build_exclusion_patterns,
    _candidate_pool_size,
    _parse_concentration_type,
    _resolve_pyramid,
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


class TestCandidatePoolSize:
    def test_without_budget_scales_with_limit(self):
        assert _candidate_pool_size(5, has_budget=False) == 25
        assert _candidate_pool_size(20, has_budget=False) == 50  # capped at 50

    def test_with_budget_uses_wider_pool(self):
        assert _candidate_pool_size(5, has_budget=True) == 100
        assert _candidate_pool_size(30, has_budget=True) == 200  # capped at 200

    def test_small_limit_has_a_floor(self):
        assert _candidate_pool_size(1, has_budget=False) == 25
        assert _candidate_pool_size(1, has_budget=True) == 100


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
