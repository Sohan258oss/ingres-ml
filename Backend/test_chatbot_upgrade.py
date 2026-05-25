"""
Comprehensive test suite for the chatbot intelligence upgrade.
Tests: greetings, educational KB, typo tolerance, intent recognition,
fallback system, empty response guard, and existing feature preservation.
"""
import pytest
import sys
import os
from unittest.mock import patch, AsyncMock, MagicMock

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["HF_TOKEN"] = "dummy"

from Backend.main import (
    app, KNOWLEDGE_BASE, TIPS, WHY_MAP,
    detect_greeting, detect_thanks, detect_bye,
    extract_definition_subject, fuzzy_match_key, _char_ratio,
)

# ---- Fixtures ----

@pytest.fixture(autouse=True)
def mock_genai():
    with patch("Backend.main.get_smart_response") as mock:
        async def side_effect(query, context):
            for ch in context:
                yield ch
        mock.side_effect = side_effect
        yield mock

@pytest.fixture(autouse=True)
def mock_mongo():
    with patch("motor.motor_asyncio.AsyncIOMotorClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_db = MagicMock()
        mock_client.__getitem__.return_value = mock_db
        mock_assessments = MagicMock()
        mock_db.assessments = mock_assessments
        mock_state_trends = MagicMock()
        mock_db.state_trends = mock_state_trends
        mock_assessments.find_one = AsyncMock(return_value={
            "state": "Karnataka", "district_name": "Bangalore",
            "block_name": "North", "extraction": 90.0, "category": "Stressed"
        })
        mock_assessments.distinct = AsyncMock(side_effect=lambda col: {
            "state": ["Karnataka", "Punjab", "Bihar"],
            "district_name": ["Bangalore", "Amritsar", "Patna"],
            "block_name": ["North", "Central", "South"]
        }.get(col, []))
        yield {
            "client": mock_client, "db": mock_db,
            "assessments": mock_assessments, "state_trends": mock_state_trends
        }


# ===================== UNIT TESTS =====================

class TestGreetingDetection:
    def test_basic_greetings(self):
        assert detect_greeting("hi") is True
        assert detect_greeting("hello") is True
        assert detect_greeting("hey") is True
        assert detect_greeting("namaste") is True

    def test_greeting_with_punctuation(self):
        assert detect_greeting("hello!") is True
        assert detect_greeting("hey!!!") is True
        assert detect_greeting("hi.") is True

    def test_greeting_with_extra_text(self):
        assert detect_greeting("hi there") is True
        assert detect_greeting("hello bot") is True
        assert detect_greeting("hey how are you") is True

    def test_non_greetings(self):
        assert detect_greeting("what is groundwater") is False
        assert detect_greeting("show me data for Punjab") is False
        assert detect_greeting("conservation tips") is False


class TestThanksDetection:
    def test_basic_thanks(self):
        assert detect_thanks("thanks") is True
        assert detect_thanks("thank you") is True
        assert detect_thanks("ty") is True

    def test_non_thanks(self):
        assert detect_thanks("what is groundwater") is False


class TestByeDetection:
    def test_basic_bye(self):
        assert detect_bye("bye") is True
        assert detect_bye("goodbye") is True
        assert detect_bye("see you") is True

    def test_non_bye(self):
        assert detect_bye("what is groundwater") is False


class TestDefinitionExtraction:
    def test_basic_definitions(self):
        assert extract_definition_subject("what is groundwater") == "groundwater"
        assert extract_definition_subject("what is an aquifer") == "aquifer"
        assert extract_definition_subject("what is agriculture?") == "agriculture"

    def test_define_prefix(self):
        assert extract_definition_subject("define recharge") == "recharge"
        assert extract_definition_subject("explain extraction") == "extraction"
        assert extract_definition_subject("tell me about water scarcity") == "water scarcity"

    def test_no_subject(self):
        assert extract_definition_subject("show me data") is None
        assert extract_definition_subject("why is Punjab stressed") is None


class TestFuzzyMatching:
    def test_exact_match(self):
        assert _char_ratio("aquifer", "aquifer") == 1.0

    def test_typo_similarity(self):
        score = _char_ratio("aqufer", "aquifer")
        assert score > 0.5

    def test_fuzzy_match_key_exact(self):
        assert fuzzy_match_key("groundwater", KNOWLEDGE_BASE) == "groundwater"

    def test_fuzzy_match_key_substring(self):
        assert fuzzy_match_key("what about recharge", KNOWLEDGE_BASE) == "recharge"

    def test_fuzzy_match_key_typo(self):
        result = fuzzy_match_key("aqufer", KNOWLEDGE_BASE, threshold=0.50)
        assert result == "aquifer"

    def test_fuzzy_match_key_no_match(self):
        result = fuzzy_match_key("xyzabc123", KNOWLEDGE_BASE, threshold=0.50)
        assert result is None


# ===================== INTEGRATION TESTS =====================

from fastapi.testclient import TestClient

@patch('Backend.main.semantic_search.search')
class TestGreetingResponses:
    def test_hello_response(self, mock_search):
        mock_search.return_value = []
        with TestClient(app) as client:
            response = client.post("/ask", json={"message": "hello"})
            assert response.status_code == 200
            data = response.json()
            assert "INGRES" in data["text"]
            assert len(data.get("suggestions", [])) > 0

    def test_hi_response(self, mock_search):
        mock_search.return_value = []
        with TestClient(app) as client:
            response = client.post("/ask", json={"message": "hi"})
            assert response.status_code == 200
            data = response.json()
            assert data["text"]  # Not empty
            assert "suggestions" in data

    def test_namaste_response(self, mock_search):
        mock_search.return_value = []
        with TestClient(app) as client:
            response = client.post("/ask", json={"message": "namaste"})
            assert response.status_code == 200
            data = response.json()
            assert "INGRES" in data["text"]


@patch('Backend.main.semantic_search.search')
class TestEducationalQuestions:
    def test_what_is_groundwater(self, mock_search):
        mock_search.return_value = []
        with TestClient(app) as client:
            response = client.post("/ask", json={"message": "what is groundwater?"})
            assert response.status_code == 200
            data = response.json()
            assert "groundwater" in data["text"].lower()
            assert data["text"].strip()

    def test_what_is_agriculture(self, mock_search):
        mock_search.return_value = []
        with TestClient(app) as client:
            response = client.post("/ask", json={"message": "what is agriculture?"})
            assert response.status_code == 200
            data = response.json()
            assert "agriculture" in data["text"].lower()

    def test_what_is_water_scarcity(self, mock_search):
        mock_search.return_value = []
        with TestClient(app) as client:
            response = client.post("/ask", json={"message": "what is water scarcity?"})
            assert response.status_code == 200
            data = response.json()
            assert "scarcity" in data["text"].lower()

    def test_what_is_groundwater_depletion(self, mock_search):
        mock_search.return_value = []
        with TestClient(app) as client:
            response = client.post("/ask", json={"message": "what is groundwater depletion?"})
            assert response.status_code == 200
            data = response.json()
            assert "depletion" in data["text"].lower()

    def test_what_is_rainfall_recharge(self, mock_search):
        mock_search.return_value = []
        with TestClient(app) as client:
            response = client.post("/ask", json={"message": "what is rainfall recharge?"})
            assert response.status_code == 200
            data = response.json()
            assert "recharge" in data["text"].lower()

    def test_define_aquifer(self, mock_search):
        mock_search.return_value = []
        with TestClient(app) as client:
            response = client.post("/ask", json={"message": "define aquifer"})
            assert response.status_code == 200
            data = response.json()
            assert "aquifer" in data["text"].lower()

    def test_explain_water_conservation(self, mock_search):
        mock_search.return_value = []
        with TestClient(app) as client:
            response = client.post("/ask", json={"message": "explain water conservation"})
            assert response.status_code == 200
            data = response.json()
            assert "conservation" in data["text"].lower()

    def test_sustainable_management(self, mock_search):
        mock_search.return_value = []
        with TestClient(app) as client:
            response = client.post("/ask", json={"message": "what is sustainable groundwater management?"})
            assert response.status_code == 200
            data = response.json()
            assert "sustainable" in data["text"].lower()


@patch('Backend.main.semantic_search.search')
class TestThankYouBye:
    def test_thanks_response(self, mock_search):
        mock_search.return_value = []
        with TestClient(app) as client:
            response = client.post("/ask", json={"message": "thanks!"})
            assert response.status_code == 200
            data = response.json()
            assert "welcome" in data["text"].lower()

    def test_bye_response(self, mock_search):
        mock_search.return_value = []
        with TestClient(app) as client:
            response = client.post("/ask", json={"message": "bye"})
            assert response.status_code == 200
            data = response.json()
            assert "goodbye" in data["text"].lower() or "bye" in data["text"].lower()


@patch('Backend.main.semantic_search.search')
class TestFallbackBehavior:
    def test_gibberish_does_not_crash(self, mock_search):
        mock_search.return_value = []
        with TestClient(app) as client:
            response = client.post("/ask", json={"message": "asdfghjkl"})
            assert response.status_code == 200
            data = response.json()
            assert data["text"].strip()  # Never empty

    def test_random_question_gives_guidance(self, mock_search):
        mock_search.return_value = []
        with TestClient(app) as client:
            response = client.post("/ask", json={"message": "who won the world cup"})
            assert response.status_code == 200
            data = response.json()
            assert data["text"].strip()


# ===================== EXISTING FEATURE PRESERVATION =====================

@patch('Backend.main.semantic_search.search')
class TestExistingFeatures:
    def test_knowledge_base_query(self, mock_search):
        mock_search.return_value = [{"name": "aquifer", "score": 0.9}]
        with TestClient(app) as client:
            response = client.post("/ask", json={"message": "aquifer"})
            assert response.status_code == 200
            data = response.json()
            assert "aquifer" in data["text"].lower()

    def test_why_query(self, mock_search):
        mock_search.return_value = [{"name": "punjab", "score": 0.9}]
        with TestClient(app) as client:
            response = client.post("/ask", json={"message": "why Punjab"})
            assert response.status_code == 200
            data = response.json()
            assert "Punjab" in data["text"]

    def test_health_endpoint(self, mock_search):
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "Online"

    def test_news_endpoint(self, mock_search):
        with TestClient(app) as client:
            response = client.get("/get-news")
            assert response.status_code == 200
            data = response.json()
            assert "news" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
