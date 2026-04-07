"""
Тесты API для VLM-пайплайна OCR-сервиса.

Тестируют новый пайплайн на основе Google Gemini Vision API.
Используют mock для избежания реальных вызовов к API.
"""
import io
import base64
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_auth():
    """Мокаем авторизацию через dependency_overrides."""
    import app.routers.admin as admin_module

    async def fake_auth():
        return {"user": MagicMock(id=1), "payload": {"sub": "1"}, "role": "admin"}

    app.dependency_overrides[admin_module.require_observer_or_higher] = fake_auth
    app.dependency_overrides[admin_module.require_admin] = fake_auth
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def sample_passport_image():
    """Минимальное JPEG-изображение для тестов."""
    # 10x10 пиксель JPEG (минимально валидный)
    from PIL import Image
    buf = io.BytesIO()
    img = Image.new("RGB", (10, 10), color="white")
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf.read()


@pytest.fixture
def mock_vlm_result():
    """Результат VLM-экстракции для мока."""
    return {
        "first_name": "NURALI",
        "last_name": "SULAYMANOV",
        "middle_name": "SHAXBOZ O'G'LI",
        "birth_date": "15.09.1986",
        "gender": "M",
        "nationality": "O'ZBEKISTON",
        "passport_number": "AM7979201",
        "issue_date": "20.03.2023",
        "expiry_date": "20.03.2033",
        "issued_by": "IIV FVD",
        "pinfl": "31509860230078",
    }


class TestVLMHealthEndpoint:
    """Тесты health endpoint."""

    def test_health_check(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestVLMTestOcrEndpoint:
    """Тесты /api/passport/test-ocr."""

    @patch("app.services.vlm_extractor.VLMExtractor.extract")
    def test_test_ocr_returns_extracted_data(
        self, mock_extract, client, sample_passport_image, mock_vlm_result
    ):
        """Тест-OCR возвращает извлечённые данные."""
        mock_extract.return_value = mock_vlm_result

        response = client.post(
            "/api/passport/test-ocr",
            files={"file": ("passport.jpg", io.BytesIO(sample_passport_image), "image/jpeg")},
        )

        assert response.status_code == 200
        data = response.json()
        assert "extracted_fields" in data
        assert data["extracted_fields"]["first_name"] == "NURALI"
        assert data["extracted_fields"]["last_name"] == "SULAYMANOV"
        assert data["extracted_fields"]["pinfl"] == "31509860230078"

    @patch("app.services.vlm_extractor.VLMExtractor.extract")
    def test_test_ocr_validation_structure(
        self, mock_extract, client, sample_passport_image, mock_vlm_result
    ):
        """Response содержит правильную структуру валидации."""
        mock_extract.return_value = mock_vlm_result

        response = client.post(
            "/api/passport/test-ocr",
            files={"file": ("passport.jpg", io.BytesIO(sample_passport_image), "image/jpeg")},
        )

        assert response.status_code == 200
        data = response.json()
        assert "validation" in data
        assert "checks" in data["validation"]
        assert "overall_confidence" in data["validation"]
        assert "all_valid" in data["validation"]

    def test_test_ocr_invalid_file_type(self, client):
        """Отклоняет неподдерживаемые типы файлов."""
        response = client.post(
            "/api/passport/test-ocr",
            files={"file": ("document.pdf", b"fake pdf content", "application/pdf")},
        )

        assert response.status_code == 415

    def test_test_ocr_no_filename(self, client):
        """Отклоняет файлы без имени."""
        response = client.post(
            "/api/passport/test-ocr",
            files={"file": ("", io.BytesIO(b"content"), "image/jpeg")},
        )

        # FastAPI возвращает 422 при пустом имени файла
        assert response.status_code in (400, 422)


class TestVLMAnalyzer:
    """Тесты анализатора изображений."""

    @patch("app.services.vlm_extractor.VLMExtractor.extract")
    def test_analyze_passport_image_returns_result(self, mock_extract, sample_passport_image, mock_vlm_result):
        """analyze_passport_image возвращает правильную структуру."""
        from app.services.ocr_analyzer import analyze_passport_image

        mock_extract.return_value = mock_vlm_result

        result = analyze_passport_image(sample_passport_image)

        assert "extracted" in result
        assert "validation" in result
        assert result["extracted"]["first_name"] == "NURALI"
        assert result["extracted"]["last_name"] == "SULAYMANOV"

    def test_analyze_passport_image_empty_without_api_key(self, sample_passport_image):
        """Без API ключа возвращает пустые поля."""
        from app.services.ocr_analyzer import analyze_passport_image
        from app.services.vlm_extractor import vlm_extractor

        if not vlm_extractor.enabled:
            result = analyze_passport_image(sample_passport_image)
            assert "extracted" in result
            assert "validation" in result
            assert result["extracted"]["first_name"] == ""
            assert result["extracted"]["pinfl"] == ""


class TestVLMExtractorEdgeCases:
    """Тесты edge cases для VLM экстрактора."""

    @patch("app.services.vlm_extractor.VLMExtractor.extract")
    def test_vlm_returns_partial_data(self, mock_extract, sample_passport_image):
        """VLM может вернуть частично заполненные поля."""
        from app.services.ocr_analyzer import analyze_passport_image

        mock_extract.return_value = {
            "first_name": "NURALI",
            "last_name": "SULAYMANOV",
            "middle_name": "",
            "birth_date": "15.09.1986",
            "gender": "M",
            "nationality": "O'ZBEKISTON",
            "passport_number": "",
            "issue_date": "",
            "expiry_date": "",
            "issued_by": "",
            "pinfl": "31509860230078",
        }

        result = analyze_passport_image(sample_passport_image)

        assert result["extracted"]["first_name"] == "NURALI"
        assert result["extracted"]["passport_number"] == ""
        # PINFL валиден
        assert result["validation"]["checks"]["pinfl"] is True
        # passport_number не валиден (пустой)
        assert result["validation"]["checks"]["passport_number"] is False

    @patch("app.services.vlm_extractor.VLMExtractor.extract")
    def test_vlm_invalid_pinfl_rejected(self, mock_extract, sample_passport_image):
        """Невалидный ПИНФЛ отклоняется валидатором."""
        from app.services.ocr_analyzer import analyze_passport_image

        mock_extract.return_value = {
            "first_name": "TEST",
            "last_name": "USER",
            "middle_name": "",
            "birth_date": "01.01.2000",
            "gender": "M",
            "nationality": "UZB",
            "passport_number": "AB1234567",
            "issue_date": "01.01.2020",
            "expiry_date": "01.01.2030",
            "issued_by": "TEST",
            "pinfl": "12345",  # Невалидный — не 14 цифр
        }

        result = analyze_passport_image(sample_passport_image)
        assert result["validation"]["checks"]["pinfl"] is False
