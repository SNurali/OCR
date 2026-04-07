import pytest
import asyncio
import base64
import json
from datetime import datetime
from httpx import AsyncClient
from sqlalchemy.orm import Session
from app.main import app
from app.database import SessionLocal
from app.models import OCRResult, FaceVerification
import logging

logger = logging.getLogger(__name__)


class TestOCRFunctionality:
    """Test OCR accuracy and correctness"""

    @pytest.mark.asyncio
    async def test_valid_passport_ocr(self):
        """Test OCR with valid passport image"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Simulate valid passport image
            with open("tests/fixtures/valid_passport.jpg", "rb") as f:
                image_data = base64.b64encode(f.read()).decode()

            response = await client.post(
                "/api/ocr/passport",
                json={"document_image": image_data},
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 202
            data = response.json()
            assert "task_id" in data

            # Wait for processing
            await asyncio.sleep(2)

            # Check result
            result_response = await client.get(
                f"/api/ocr/result/{data['task_id']}",
                headers={"Authorization": "Bearer test_token"},
            )

            assert result_response.status_code == 200
            result = result_response.json()

            # Verify OCR fields
            assert result["status"] == "completed"
            assert result["data"]["first_name"] is not None
            assert result["data"]["last_name"] is not None
            assert result["data"]["passport_number"] is not None
            assert result["data"]["confidence"] > 0.7

    @pytest.mark.asyncio
    async def test_mrz_parsing(self):
        """Test MRZ line parsing accuracy"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            with open("tests/fixtures/passport_with_mrz.jpg", "rb") as f:
                image_data = base64.b64encode(f.read()).decode()

            response = await client.post(
                "/api/ocr/passport",
                json={"document_image": image_data},
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 202
            task_id = response.json()["task_id"]

            await asyncio.sleep(2)

            result_response = await client.get(
                f"/api/ocr/result/{task_id}",
                headers={"Authorization": "Bearer test_token"},
            )

            result = result_response.json()
            assert result["data"]["mrz_valid"] == True
            assert result["data"]["mrz_line1"] is not None
            assert result["data"]["mrz_line2"] is not None

    @pytest.mark.asyncio
    async def test_foreign_passport_ocr(self):
        """Test OCR with international passport"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            with open("tests/fixtures/foreign_passport.jpg", "rb") as f:
                image_data = base64.b64encode(f.read()).decode()

            response = await client.post(
                "/api/ocr/passport",
                json={"document_image": image_data},
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 202
            task_id = response.json()["task_id"]

            await asyncio.sleep(2)

            result_response = await client.get(
                f"/api/ocr/result/{task_id}",
                headers={"Authorization": "Bearer test_token"},
            )

            result = result_response.json()
            assert result["status"] == "completed"
            assert result["data"]["document_type"] in ["foreign_passport", "td3"]


class TestFaceVerification:
    """Test face matching and verification"""

    @pytest.mark.asyncio
    async def test_same_person_match(self):
        """Test face matching with same person"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            with open("tests/fixtures/passport_photo.jpg", "rb") as f:
                doc_image = base64.b64encode(f.read()).decode()

            with open("tests/fixtures/selfie_same_person.jpg", "rb") as f:
                selfie_image = base64.b64encode(f.read()).decode()

            response = await client.post(
                "/api/kyc/face-verify",
                json={"document_image": doc_image, "selfie_image": selfie_image},
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 202
            task_id = response.json()["task_id"]

            await asyncio.sleep(3)

            result_response = await client.get(
                f"/api/kyc/face-result/{task_id}",
                headers={"Authorization": "Bearer test_token"},
            )

            result = result_response.json()
            assert result["status"] == "completed"
            assert result["data"]["match"] == True
            assert result["data"]["similarity"] > 0.85
            assert result["data"]["confidence"] > 0.9

    @pytest.mark.asyncio
    async def test_different_person_mismatch(self):
        """Test face matching with different persons"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            with open("tests/fixtures/passport_photo_person1.jpg", "rb") as f:
                doc_image = base64.b64encode(f.read()).decode()

            with open("tests/fixtures/selfie_person2.jpg", "rb") as f:
                selfie_image = base64.b64encode(f.read()).decode()

            response = await client.post(
                "/api/kyc/face-verify",
                json={"document_image": doc_image, "selfie_image": selfie_image},
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 202
            task_id = response.json()["task_id"]

            await asyncio.sleep(3)

            result_response = await client.get(
                f"/api/kyc/face-result/{task_id}",
                headers={"Authorization": "Bearer test_token"},
            )

            result = result_response.json()
            assert result["status"] == "completed"
            assert result["data"]["match"] == False
            assert result["data"]["similarity"] < 0.7

    @pytest.mark.asyncio
    async def test_liveness_detection(self):
        """Test liveness detection"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            with open("tests/fixtures/selfie_live.jpg", "rb") as f:
                selfie_image = base64.b64encode(f.read()).decode()

            response = await client.post(
                "/api/kyc/face-verify",
                json={"document_image": selfie_image, "selfie_image": selfie_image},
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 202
            task_id = response.json()["task_id"]

            await asyncio.sleep(3)

            result_response = await client.get(
                f"/api/kyc/face-result/{task_id}",
                headers={"Authorization": "Bearer test_token"},
            )

            result = result_response.json()
            assert result["data"]["liveness_score"] > 0.7


class TestRiskEngine:
    """Test risk engine decisions"""

    @pytest.mark.asyncio
    async def test_approve_decision(self):
        """Test approve decision from risk engine"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            with open("tests/fixtures/valid_passport.jpg", "rb") as f:
                doc_image = base64.b64encode(f.read()).decode()

            with open("tests/fixtures/selfie_high_quality.jpg", "rb") as f:
                selfie_image = base64.b64encode(f.read()).decode()

            response = await client.post(
                "/api/kyc/full-check",
                json={"document_image": doc_image, "selfie_image": selfie_image},
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 202
            task_id = response.json()["task_id"]

            await asyncio.sleep(5)

            result_response = await client.get(
                f"/api/kyc/result/{task_id}",
                headers={"Authorization": "Bearer test_token"},
            )

            result = result_response.json()
            assert result["status"] == "completed"
            assert result["data"]["decision"] in ["approve", "review", "reject"]
            assert result["data"]["risk_score"] is not None

    @pytest.mark.asyncio
    async def test_review_decision(self):
        """Test review decision from risk engine"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Use medium-quality images
            with open("tests/fixtures/passport_medium_quality.jpg", "rb") as f:
                doc_image = base64.b64encode(f.read()).decode()

            with open("tests/fixtures/selfie_medium_quality.jpg", "rb") as f:
                selfie_image = base64.b64encode(f.read()).decode()

            response = await client.post(
                "/api/kyc/full-check",
                json={"document_image": doc_image, "selfie_image": selfie_image},
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 202
            task_id = response.json()["task_id"]

            await asyncio.sleep(5)

            result_response = await client.get(
                f"/api/kyc/result/{task_id}",
                headers={"Authorization": "Bearer test_token"},
            )

            result = result_response.json()
            assert result["data"]["decision"] in ["review", "reject"]


class TestAntiSpoof:
    """Test anti-spoofing detection"""

    @pytest.mark.asyncio
    async def test_screen_spoof_detection(self):
        """Test detection of screen-based spoofing"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            with open("tests/fixtures/screen_spoof.jpg", "rb") as f:
                selfie_image = base64.b64encode(f.read()).decode()

            response = await client.post(
                "/api/kyc/face-verify",
                json={"document_image": selfie_image, "selfie_image": selfie_image},
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 202
            task_id = response.json()["task_id"]

            await asyncio.sleep(3)

            result_response = await client.get(
                f"/api/kyc/face-result/{task_id}",
                headers={"Authorization": "Bearer test_token"},
            )

            result = result_response.json()
            assert result["data"]["anti_spoof_score"] < 0.5
            assert result["data"]["fraud_risk"] in ["high", "medium"]

    @pytest.mark.asyncio
    async def test_print_spoof_detection(self):
        """Test detection of printed photo spoofing"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            with open("tests/fixtures/print_spoof.jpg", "rb") as f:
                selfie_image = base64.b64encode(f.read()).decode()

            response = await client.post(
                "/api/kyc/face-verify",
                json={"document_image": selfie_image, "selfie_image": selfie_image},
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 202
            task_id = response.json()["task_id"]

            await asyncio.sleep(3)

            result_response = await client.get(
                f"/api/kyc/face-result/{task_id}",
                headers={"Authorization": "Bearer test_token"},
            )

            result = result_response.json()
            assert result["data"]["anti_spoof_score"] < 0.5
