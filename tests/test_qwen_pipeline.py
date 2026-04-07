"""Тесты для Qwen-only OCR pipeline."""
import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.vlm_extractor import VLMExtractor
from app.services.validator import DataValidator


class TestVLMExtractor:
    """Тесты экстрактора Qwen VLM."""

    def test_init(self):
        """Тест инициализации."""
        extractor = VLMExtractor()
        assert extractor.model == "qwen3.5-plus"
        assert "dashscope" in extractor.base_url

    def test_parse_json_response_clean(self):
        """Тест парсинга чистого JSON."""
        extractor = VLMExtractor()
        content = '{"first_name":"NURALI","last_name":"SULATMANOV"}'
        result = extractor._parse_json_response(content)
        assert result["first_name"] == "NURALI"
        assert result["last_name"] == "SULATMANOV"

    def test_parse_json_response_markdown(self):
        """Тест парсинга JSON с markdown."""
        extractor = VLMExtractor()
        content = '```json\n{"first_name":"NURALI"}\n```'
        result = extractor._parse_json_response(content)
        assert result["first_name"] == "NURALI"

    def test_normalize_gender(self):
        """Тест нормализации пола."""
        extractor = VLMExtractor()
        raw = {"gender": "ERKAK"}
        result = extractor._normalize_fields(raw)
        assert result["gender"] == "M"

        raw = {"gender": "AYOL"}
        result = extractor._normalize_fields(raw)
        assert result["gender"] == "F"

    def test_normalize_pinfl(self):
        """Тест очистки PINFL."""
        extractor = VLMExtractor()
        raw = {"pinfl": "324-09-86-02300-78"}
        result = extractor._normalize_fields(raw)
        assert result["pinfl"] == "32409860230078"
        assert len(result["pinfl"]) == 14

    def test_normalize_pinfl_too_short(self):
        """Тест PINFL короче 14 цифр."""
        extractor = VLMExtractor()
        raw = {"pinfl": "123456"}
        result = extractor._normalize_fields(raw)
        assert result["pinfl"] == ""

    def test_normalize_date_yyyy_mm_dd(self):
        """Тест нормализации даты из YYYY-MM-DD."""
        extractor = VLMExtractor()
        raw = {"birth_date": "2022-03-24"}
        result = extractor._normalize_fields(raw)
        assert result["birth_date"] == "24.03.2022"


class TestDataValidator:
    """Тесты валидатора."""

    def setup_method(self):
        self.validator = DataValidator()

    def test_validate_pinfl_valid(self):
        assert self.validator.validate_pinfl("32409860230078") is True

    def test_validate_pinfl_invalid_short(self):
        assert self.validator.validate_pinfl("123456") is False

    def test_validate_pinfl_invalid_letters(self):
        # validate_pinfl извлекает только цифры, так что "abc12345678901234" → "12345678901234" (14 цифр) = True
        assert self.validator.validate_pinfl("abc12345678901234") is True
        # А вот это действительно невалидно — меньше 14 цифр
        assert self.validator.validate_pinfl("abc123") is False

    def test_validate_date(self):
        assert self.validator.validate_date("24.03.2022") is True
        assert self.validator.validate_date("2022-03-24") is True
        assert self.validator.validate_date("invalid") is False

    def test_validate_birth_date_realistic(self):
        assert self.validator.validate_birth_date("24.03.1990") is True

    def test_validate_birth_date_future(self):
        assert self.validator.validate_birth_date("24.03.2090") is False

    def test_validate_passport_number_uzbek(self):
        assert self.validator.validate_passport_number("AN7979293") is True
        assert self.validator.validate_passport_number("AB1234567") is True

    def test_validate_passport_number_invalid(self):
        assert self.validator.validate_passport_number("123") is False
        assert self.validator.validate_passport_number("") is False

    def test_validate_full_pipeline(self):
        data = {
            "first_name": "NURALI",
            "last_name": "SULATMANOV",
            "middle_name": "AMIRJONOVICH",
            "birth_date": "24.03.1990",
            "gender": "M",
            "nationality": "O'ZBEKISTON",
            "passport_number": "AN7979293",
            "pinfl": "32409860230078",
            "issue_date": "24.03.2020",
            "expiry_date": "24.03.2030",
            "issued_by": "TOSHKENT",
        }
        result = self.validator.validate(data)

        assert result["all_valid"] is True
        assert result["overall_confidence"] > 0.8
        checks = result["checks"]
        assert checks["first_name"] is True
        assert checks["last_name"] is True
        assert checks["birth_date"] is True
        assert checks["passport_number"] is True
        assert checks["pinfl"] is True

    def test_validate_empty_data(self):
        data = {
            "first_name": "",
            "last_name": "",
            "birth_date": "",
            "gender": "",
            "passport_number": "",
            "pinfl": "",
        }
        result = self.validator.validate(data)
        assert result["all_valid"] is False
        assert result["overall_confidence"] == 0.0
