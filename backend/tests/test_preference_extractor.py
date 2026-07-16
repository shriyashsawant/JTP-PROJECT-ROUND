"""
Unit tests for the new backend helper extractors and the 3-layer preference extractor service.
"""
import pytest
from unittest.mock import AsyncMock, patch

from app.services.intent_detector import detect_age, detect_skin_type, detect_note_families
from app.services.preference_extractor import extract_preferences


class TestAgeSkinScentExtractors:
    def test_detect_age_digits(self):
        assert detect_age("I am 22 years old") == 22
        assert detect_age("22yo") == 22
        assert detect_age("22 y/o") == 22
        assert detect_age("22, love hiking") == 22
        assert detect_age("I am 22") == 22

    def test_detect_age_words(self):
        assert detect_age("I'm twenty-two years old") == 22
        assert detect_age("I am twenty five") == 25
        assert detect_age("thirty years old") == 30
        assert detect_age("under 25") is None  # no age keyword/pattern
        assert detect_age("worn this for 10 years") is None  # outside 13-100 bounds

    def test_detect_skin_type(self):
        assert detect_skin_type("I have dry skin") == "dry"
        assert detect_skin_type("my skin is oily") == "oily"
        assert detect_skin_type("skin type is normal") == "normal"
        assert detect_skin_type("regular fragrance query") is None

    def test_detect_note_families(self):
        families = detect_note_families("I want a fresh citrusy and woodsy scent")
        assert "citrus" in families
        assert "woody" in families
        assert "fresh_aquatic" in families

        assert detect_note_families("nothing") == []


@pytest.mark.asyncio
async def test_preference_extractor_service_local_only():
    """Assert preference_extractor extracts locally first."""
    # We monkeypatch detect_scenarios to avoid ML model load
    with patch("app.services.preference_extractor.detect_scenarios", AsyncMock(return_value=["gym"])), \
         patch("app.services.preference_extractor.classify_off_topic", AsyncMock(return_value={"is_fragrance": True})):
        
        result = await extract_preferences("22yo guy wanting a fresh citrusy scent for the gym under 2000")
        
        assert result["gender"] == "male"
        assert "gym" in result["scenarios"]
        assert "citrus" in result["note_families"]
        assert result["budget"] == 2000.0
        assert result["age"] == 22
        assert result["is_off_topic"] is False
        assert result["is_dupe_intent"] is False


@pytest.mark.asyncio
async def test_preference_extractor_service_llm_fallback(monkeypatch):
    """Assert preference_extractor falls back to LLM for missing core fields."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "groq_api_key", "test_key")

    mock_llm_result = {
        "gender": "female",
        "scenarios": ["date"],
        "note_families": ["floral"],
        "avoid_notes": ["vanilla"],
        "hours_required": 8,
        "longevity_requested": True,
        "projection_preference": "moderate",
        "budget": 5000.0,
        "age": 30,
        "skin_type": "dry"
    }

    with patch("app.services.preference_extractor.detect_scenarios", AsyncMock(return_value=[])), \
         patch("app.services.preference_extractor.classify_off_topic", AsyncMock(return_value={"is_fragrance": True})), \
         patch("app.services.preference_extractor._extractor_breaker.call", AsyncMock(return_value=mock_llm_result)):
        
        # Query with missing fields
        result = await extract_preferences("something nice")
        
        assert result["gender"] == "female"
        assert result["scenarios"] == ["date"]
        assert result["note_families"] == ["floral"]
        assert result["avoid_notes"] == ["vanilla"]
        assert result["budget"] == 5000.0
        assert result["age"] == 30
        assert result["skin_type"] == "dry"
