import pytest
from unittest.mock import patch, MagicMock
from app.services.llm_extractor import LLMExtractor
import httpx
import json

@pytest.fixture
def mock_llm_extractor():
    extractor = LLMExtractor()
    extractor._prompt_template = "MOCK PROMPT {raw_text} {mrz_json}"
    return extractor

def test_llm_extraction_success(mock_llm_extractor):
    with patch("ollama.Client") as MockClient:
        mock_client_instance = MagicMock()
        MockClient.return_value = mock_client_instance
        
        # Mocking a valid JSON response from Ollama
        mock_response = {
            "message": {
                "content": '```json\n{"surname": "TESTOV", "given_name": "TEST", "patronymic": "TESTOVICH", "sex": "ERKKAK"}\n```'
            }
        }
        mock_client_instance.chat.return_value = mock_response
        
        # Setting client explicitly
        mock_llm_extractor._client = mock_client_instance
        
        raw_text = "TESTOV TEST TESTOVICH"
        mrz_data = {"surname": "TESTOV", "given_names": "TEST"}
        
        result = mock_llm_extractor.extract_fields(raw_text, mrz_data)
        
        assert result is not None
        assert result.get("surname") == "TESTOV"
        assert result.get("given_name") == "TEST"
        assert result.get("patronymic") == "TESTOVICH"
        assert result.get("sex") == "ERKKAK"

def test_llm_extraction_invalid_json_fallback(mock_llm_extractor):
    with patch("ollama.Client") as MockClient:
        mock_client_instance = MagicMock()
        MockClient.return_value = mock_client_instance
        
        # Mocking an invalid JSON response
        mock_response = {
            "message": {
                "content": "Not a JSON"
            }
        }
        mock_client_instance.chat.return_value = mock_response
        mock_llm_extractor._client = mock_client_instance
        
        raw_text = "TESTOV TEST"
        mrz_data = {}
        
        result = mock_llm_extractor.extract_fields(raw_text, mrz_data)
        
        # Should gracefully return None, triggering Regex fallback in analyzer
        assert result is None

def test_llm_extraction_timeout(mock_llm_extractor):
    with patch("ollama.Client") as MockClient:
        mock_client_instance = MagicMock()
        MockClient.return_value = mock_client_instance
        
        mock_client_instance.chat.side_effect = httpx.TimeoutException("Timeout")
        mock_llm_extractor._client = mock_client_instance
        
        raw_text = "TESTOV TEST"
        mrz_data = {}
        
        result = mock_llm_extractor.extract_fields(raw_text, mrz_data)
        
        assert result is None

def test_llm_disabled(mock_llm_extractor):
    mock_llm_extractor.enabled = False
    result = mock_llm_extractor.extract_fields("TEST", {})
    assert result is None
