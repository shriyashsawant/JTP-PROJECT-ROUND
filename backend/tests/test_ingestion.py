"""
Unit tests for the ingestion package (app/ingestion/): the PerfumeRecord
contract, the quality-gate validators, and the upsert's source-priority /
normalized-key matching logic. upsert.py is tested against a small in-memory
fake connection (no real DB) that simulates just enough of asyncpg's
fetchrow/fetch/execute surface to exercise the real SQL branches.
"""
import pytest
from pydantic import ValidationError

from app.ingestion.contracts import PerfumeRecord, normalize_name
from app.ingestion.upsert import upsert_perfume
from app.ingestion.validators import is_valid, validate_record


def _record(**overrides) -> PerfumeRecord:
    defaults = dict(brand="Dior", perfume="Sauvage", source="fra_cleaned", source_priority=3)
    defaults.update(overrides)
    return PerfumeRecord(**defaults)


class TestNormalizeName:
    def test_lowercases_and_strips_punctuation(self):
        assert normalize_name("  Dior!! ") == "dior"

    def test_collapses_whitespace(self):
        assert normalize_name("Jean   Paul  Gaultier") == "jean paul gaultier"

    def test_empty_and_none(self):
        assert normalize_name("") == ""
        assert normalize_name(None) == ""


class TestPerfumeRecordContract:
    def test_valid_record_constructs(self):
        record = _record()
        assert record.brand == "Dior"
        assert record.normalized_key == "dior|sauvage"

    def test_empty_brand_rejected_by_pydantic(self):
        with pytest.raises(ValidationError):
            _record(brand="")

    def test_empty_perfume_rejected_by_pydantic(self):
        with pytest.raises(ValidationError):
            _record(perfume="")

    def test_normalized_key_is_case_and_punctuation_insensitive(self):
        a = _record(brand="Acqua di Parma", perfume="Colonia Club")
        b = _record(brand="ACQUA DI PARMA", perfume="colonia, club!")
        assert a.normalized_key == b.normalized_key


class TestValidators:
    def test_clean_record_has_no_issues(self):
        assert validate_record(_record(real_price_inr=2000, rating=4.2, rating_count=100)) == []
        assert is_valid(_record(real_price_inr=2000))

    def test_non_positive_price_flagged(self):
        issues = validate_record(_record(real_price_inr=0))
        assert any("price" in i for i in issues)
        assert not is_valid(_record(real_price_inr=-5))

    def test_rating_out_of_range_flagged(self):
        issues = validate_record(_record(rating=7.5))
        assert any("rating" in i for i in issues)

    def test_negative_rating_count_flagged(self):
        issues = validate_record(_record(rating_count=-1))
        assert any("rating_count" in i for i in issues)

    def test_blank_accord_entry_flagged(self):
        issues = validate_record(_record(accords=["woody", "   "]))
        assert any("accord" in i for i in issues)

    def test_blank_note_entry_flagged(self):
        issues = validate_record(_record(notes=["musk", ""]))
        assert any("note" in i for i in issues)

    def test_missing_price_is_not_an_error(self):
        # real_price_inr is optional (only populated when a source has an
        # actual observed price) - None must not be flagged as invalid.
        assert validate_record(_record(real_price_inr=None)) == []


class FakeConn:
    """Minimal in-memory stand-in for asyncpg's Connection, just enough
    surface to exercise upsert_perfume's exact-match / normalized-key /
    priority-check branches without a real database."""

    def __init__(self, initial_rows=None):
        self.rows: list[dict] = [dict(r) for r in (initial_rows or [])]
        self._next_id = max((r["id"] for r in self.rows), default=0) + 1
        self.last_update_args: tuple | None = None
        self.last_insert_args: tuple | None = None

    async def fetchrow(self, sql, *args):
        assert "WHERE brand = $1 AND perfume = $2" in sql
        brand, perfume = args
        for r in self.rows:
            if r["brand"] == brand and r["perfume"] == perfume:
                return dict(r)
        return None

    async def fetch(self, sql, *args):
        assert "WHERE normalized_key = $1" in sql
        (key,) = args
        return [dict(r) for r in self.rows if r["normalized_key"] == key]

    async def execute(self, sql, *args):
        stripped = sql.strip()
        if stripped.startswith("UPDATE perfumes"):
            self.last_update_args = args
            row_id, *_rest = args
            source, source_priority, normalized_key = args[16], args[17], args[18]
            for r in self.rows:
                if r["id"] == row_id:
                    r["price_inr"] = args[6]
                    r["source"] = source
                    r["source_priority"] = source_priority
                    r["normalized_key"] = normalized_key
                    return
            raise AssertionError(f"UPDATE targeted a row id {row_id} that doesn't exist")
        elif stripped.startswith("INSERT INTO perfumes"):
            self.last_insert_args = args
            brand, perfume = args[0], args[1]
            if any(r["brand"] == brand and r["perfume"] == perfume for r in self.rows):
                return  # ON CONFLICT DO NOTHING
            self.rows.append({
                "id": self._next_id, "brand": brand, "perfume": perfume,
                "price_inr": args[7], "source": args[18],
                "source_priority": args[19], "normalized_key": args[20],
            })
            self._next_id += 1
        else:
            raise AssertionError(f"Unexpected SQL: {sql}")


class TestUpsertPerfume:
    async def test_inserts_when_no_existing_row(self):
        conn = FakeConn()
        record = _record(real_price_inr=2000)
        await upsert_perfume(conn, record, "[0.1]", 50.0, 50.0)
        assert len(conn.rows) == 1
        assert conn.rows[0]["brand"] == "Dior"
        assert conn.rows[0]["source_priority"] == 3

    async def test_updates_exact_match_when_new_priority_is_higher_or_equal(self):
        conn = FakeConn(initial_rows=[{
            "id": 1, "brand": "Dior", "perfume": "Sauvage",
            "price_inr": 1500, "source": "da_fragrance", "source_priority": 1,
            "normalized_key": "dior|sauvage",
        }])
        record = _record(real_price_inr=3000, source="scraper_merged", source_priority=5)
        await upsert_perfume(conn, record, "[0.1]", 50.0, 50.0)
        assert len(conn.rows) == 1  # updated in place, not duplicated
        assert conn.rows[0]["price_inr"] == 3000
        assert conn.rows[0]["source_priority"] == 5

    async def test_lower_priority_source_does_not_overwrite(self):
        conn = FakeConn(initial_rows=[{
            "id": 1, "brand": "Dior", "perfume": "Sauvage",
            "price_inr": 5000, "source": "scraper_merged", "source_priority": 5,
            "normalized_key": "dior|sauvage",
        }])
        record = _record(real_price_inr=999, source="da_fragrance", source_priority=1)
        await upsert_perfume(conn, record, "[0.1]", 50.0, 50.0)
        assert conn.rows[0]["price_inr"] == 5000  # untouched
        assert conn.last_update_args is None
        assert conn.last_insert_args is None

    async def test_falls_back_to_normalized_key_match_when_no_exact_match(self):
        # Existing row stored with different casing/punctuation than the
        # incoming record - exact (brand, perfume) match misses, but the
        # normalized_key lookup should still find and update it.
        conn = FakeConn(initial_rows=[{
            "id": 1, "brand": "DIOR", "perfume": "sauvage!",
            "price_inr": 1000, "source": "da_fragrance", "source_priority": 1,
            "normalized_key": "dior|sauvage",
        }])
        record = _record(real_price_inr=4000, source="fra_cleaned", source_priority=3)
        await upsert_perfume(conn, record, "[0.1]", 50.0, 50.0)
        assert len(conn.rows) == 1
        assert conn.rows[0]["price_inr"] == 4000

    async def test_ambiguous_normalized_key_match_falls_back_to_insert(self):
        # Two existing rows already share a normalized_key (the real
        # "Acqua di Parma / Colonia Club" vs "Colonia C.L.U.B." case found in
        # the live dataset) - must not guess which one to update.
        conn = FakeConn(initial_rows=[
            {"id": 1, "brand": "Acqua di Parma", "perfume": "Colonia Club",
             "price_inr": 2316, "source": "legacy_seed", "source_priority": 0,
             "normalized_key": "acqua di parma|colonia club"},
            {"id": 2, "brand": "Acqua di Parma", "perfume": "Colonia C.L.U.B.",
             "price_inr": 3470, "source": "legacy_seed", "source_priority": 0,
             "normalized_key": "acqua di parma|colonia club"},
        ])
        record = _record(
            brand="Acqua di Parma", perfume="Colonia Club Deluxe",
            real_price_inr=5000, source="scraper_merged", source_priority=5,
        )
        await upsert_perfume(conn, record, "[0.1]", 50.0, 50.0)
        # Neither existing row was touched; a new row was inserted instead.
        assert len(conn.rows) == 3
        assert conn.rows[0]["price_inr"] == 2316
        assert conn.rows[1]["price_inr"] == 3470
        assert conn.rows[2]["price_inr"] == 5000
