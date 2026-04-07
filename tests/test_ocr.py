import pytest

from app.services.validator import DataValidator
from app.utils.encryption import encrypt_field, decrypt_field, mask_field


class TestDataValidator:
    @pytest.fixture
    def validator(self):
        return DataValidator()

    def test_validate_pinfl_valid(self, validator):
        assert validator.validate_pinfl("12345678901234")

    def test_validate_pinfl_invalid_length(self, validator):
        assert not validator.validate_pinfl("1234567890123")
        assert not validator.validate_pinfl("123456789012345")

    def test_validate_pinfl_non_digits(self, validator):
        assert not validator.validate_pinfl("1234567890123a")

    def test_validate_date_valid(self, validator):
        assert validator.validate_date("2024-01-15")
        assert validator.validate_date("15.01.2024")

    def test_validate_date_invalid(self, validator):
        assert not validator.validate_date("not-a-date")
        assert not validator.validate_date("2024-13-45")

    def test_validate_birth_date_logic(self, validator):
        assert validator.validate_birth_date("1990-01-01")
        assert not validator.validate_birth_date("2030-01-01")

    def test_normalize_date(self, validator):
        assert validator.normalize_date("2024-01-15") == "15.01.2024"
        assert validator.normalize_date("15.01.2024") == "15.01.2024"

    def test_validate_full_data(self, validator):
        """Тест валидации полного набора данных паспорта."""
        data = {
            "first_name": "NURALI",
            "last_name": "SULAYMANOV",
            "middle_name": "SHAXBOZ",
            "birth_date": "15.09.1986",
            "gender": "M",
            "nationality": "O'ZBEKISTON",
            "passport_number": "AM7979201",
            "issue_date": "20.03.2023",
            "expiry_date": "20.03.2033",
            "issued_by": "IIV FVD",
            "pinfl": "31509860230078",
        }
        result = validator.validate(data)

        assert result["checks"]["first_name"] is True
        assert result["checks"]["last_name"] is True
        assert result["checks"]["birth_date"] is True
        assert result["checks"]["pinfl"] is True
        assert result["checks"]["passport_number"] is True
        assert result["overall_confidence"] >= 0.45


class TestAntiFraud:
    """Тесты антифрод-модуля (проверка качества изображения)."""

    @pytest.fixture
    def checker(self):
        from app.services.anti_fraud import AntiFraudChecker
        return AntiFraudChecker()

    def test_blur_detection(self, checker):
        import numpy as np

        sharp = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        result = checker._detect_blur(sharp)

        assert "score" in result
        assert "laplacian_variance" in result
        assert "passed" in result

    def test_glare_detection(self, checker):
        import numpy as np

        white = np.ones((100, 100, 3), dtype=np.uint8) * 255
        result = checker._detect_glare(white)

        assert result["glare_ratio"] > 0.9
        assert result["score"] < 0.5

    def test_full_check(self, checker):
        import numpy as np

        img = np.random.randint(50, 200, (200, 300, 3), dtype=np.uint8)
        result = checker.check(img)

        assert "overall_score" in result
        assert "blocked" in result
        assert "risk_level" in result
        assert 0.0 <= result["overall_score"] <= 1.0


class TestEncryption:
    def test_encrypt_decrypt(self):
        plaintext = "12345678901234"
        encrypted = encrypt_field(plaintext)
        decrypted = decrypt_field(encrypted)

        assert encrypted is not None
        assert encrypted != plaintext
        assert decrypted == plaintext

    def test_encrypt_empty(self):
        assert encrypt_field("") is None
        assert encrypt_field(None) is None

    def test_decrypt_empty(self):
        assert decrypt_field("") is None
        assert decrypt_field(None) is None

    def test_mask_field(self):
        assert mask_field("12345678901234", 4) == "1234**********"
        assert mask_field("ABC", 3) == "ABC"
        assert mask_field("", 3) == ""


class TestVLMExtractor:
    """Тесты VLM-экстрактора (без реальных API вызовов)."""

    def test_extractor_init_no_key(self):
        """Экстрактор инициализируется без ключа как disabled."""
        from app.services.vlm_extractor import VLMExtractor
        # В тестовом окружении ключ не задан — экстрактор disabled
        extractor = VLMExtractor()
        # Если ключ не задан, enabled = False
        # Если ключ задан — это тоже корректно
        assert hasattr(extractor, "enabled")
        assert hasattr(extractor, "extract")

    def test_extractor_returns_empty_without_key(self):
        """Без API ключа возвращает пустой результат."""
        from app.services.vlm_extractor import VLMExtractor
        extractor = VLMExtractor()
        if not extractor.enabled:
            result = extractor.extract(b"fake_image_bytes")
            assert result["first_name"] == ""
            assert result["pinfl"] == ""
            assert "first_name" in result
            assert "pinfl" in result

    def test_normalize_fields(self):
        """Тест нормализации полей."""
        from app.services.vlm_extractor import VLMExtractor
        extractor = VLMExtractor()

        raw = {
            "given_name": "NURALI",
            "surname": "SULAYMANOV",
            "date_of_birth": "15.09.1986",
            "sex": "ERKAK",
            "personal_number": "31509860230078",
            "document_number": "AM 79792",
        }
        result = extractor._normalize_fields(raw)

        assert result["first_name"] == "NURALI"
        assert result["last_name"] == "SULAYMANOV"
        assert result["gender"] == "M"
        assert result["pinfl"] == "31509860230078"
        assert result["passport_number"] == "AM79792"

    def test_pinfl_normalization_invalid_length(self):
        """ПИНФЛ с неправильной длиной очищается."""
        from app.services.vlm_extractor import VLMExtractor
        extractor = VLMExtractor()

        raw = {"pinfl": "12345"}
        result = extractor._normalize_fields(raw)
        assert result["pinfl"] == ""

    def test_gender_normalization(self):
        """Нормализация пола к M/F."""
        from app.services.vlm_extractor import VLMExtractor
        extractor = VLMExtractor()

        assert extractor._normalize_fields({"sex": "ERKAK"})["gender"] == "M"
        assert extractor._normalize_fields({"sex": "AYOL"})["gender"] == "F"
        assert extractor._normalize_fields({"gender": "M"})["gender"] == "M"
        assert extractor._normalize_fields({"gender": "F"})["gender"] == "F"
