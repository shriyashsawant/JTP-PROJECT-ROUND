"""Unit tests for request-schema validation constraints in models/schemas.py."""
import pytest
from pydantic import ValidationError

from app.models.schemas import BudgetSearchRequest, ContextSearchRequest


class TestContextSearchRequest:
    def test_valid_minimal_request(self):
        req = ContextSearchRequest(query="fresh summer scent")
        assert req.query == "fresh summer scent"
        assert req.limit == 5

    def test_empty_query_rejected(self):
        with pytest.raises(ValidationError):
            ContextSearchRequest(query="")

    def test_overlong_query_rejected(self):
        # Guards against arbitrarily large text being pushed through the
        # embedding model on every request.
        with pytest.raises(ValidationError):
            ContextSearchRequest(query="x" * 501)

    def test_max_length_query_accepted(self):
        req = ContextSearchRequest(query="x" * 500)
        assert len(req.query) == 500

    def test_negative_budget_rejected(self):
        with pytest.raises(ValidationError):
            ContextSearchRequest(query="test", budget=-1)

    def test_limit_bounds(self):
        with pytest.raises(ValidationError):
            ContextSearchRequest(query="test", limit=0)
        with pytest.raises(ValidationError):
            ContextSearchRequest(query="test", limit=61)
        # 60 (raised from an earlier 20) must be accepted - the chat UI's
        # "Show More" pagination needs headroom beyond a handful of results.
        assert ContextSearchRequest(query="test", limit=60).limit == 60

    def test_invalid_gender_literal_rejected(self):
        with pytest.raises(ValidationError):
            ContextSearchRequest(query="test", gender="other")

    def test_valid_gender_literals_accepted(self):
        for g in ("male", "female", "unisex"):
            assert ContextSearchRequest(query="test", gender=g).gender == g


class TestBudgetSearchRequest:
    def test_valid_minimal_request(self):
        req = BudgetSearchRequest(query="Dior Sauvage")
        assert req.budget is None

    def test_budget_below_minimum_rejected(self):
        with pytest.raises(ValidationError):
            BudgetSearchRequest(query="test", budget=50)

    def test_budget_at_minimum_accepted(self):
        req = BudgetSearchRequest(query="test", budget=100)
        assert req.budget == 100

    def test_overlong_query_rejected(self):
        with pytest.raises(ValidationError):
            BudgetSearchRequest(query="x" * 501)
