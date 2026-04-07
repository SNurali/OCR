import pytest
import asyncio
import base64
from httpx import AsyncClient
from app.main import app
import logging

logger = logging.getLogger(__name__)


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    @pytest.mark.asyncio
    async def test_poor_lighting_ocr(self):
        """Test OCR with poor lighting conditions"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            with open("tests/fixtures/passport_poor_lighting.jpg", "rb") as f:
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
            # Should still process but with lower confidence
            assert result["status"] == "completed"
            assert result["data"]["confidence"] < 0.8

    @pytest.mark.asyncio
    async def test_blurry_document_ocr(self):
        """Test OCR with blurry document"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            with open("tests/fixtures/passport_blurry.jpg", "rb") as f:
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
            # Blurry should have low confidence
            assert result["data"]["confidence"] < 0.7

    @pytest.mark.asyncio
    async def test_rotated_document_ocr(self):
        """Test OCR with rotated document"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            with open("tests/fixtures/passport_rotated_45.jpg", "rb") as f:
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
            # Should handle rotation via PaddleOCR
            assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_partially_covered_face(self):
        """Test face verification with partially covered face"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            with open("tests/fixtures/passport_photo.jpg", "rb") as f:
                doc_image = base64.b64encode(f.read()).decode()

            with open("tests/fixtures/selfie_partially_covered.jpg", "rb") as f:
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
            # Should detect low quality
            assert result["data"]["selfie_quality_score"] < 0.7

    @pytest.mark.asyncio
    async def test_cropped_mrz_lines(self):
        """Test OCR with cropped/cut MRZ lines"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            with open("tests/fixtures/passport_cropped_mrz.jpg", "rb") as f:
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
            # MRZ should be invalid
            assert result["data"]["mrz_valid"] == False

    @pytest.mark.asyncio
    async def test_extreme_angle_face(self):
        """Test face verification with extreme angle"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            with open("tests/fixtures/passport_photo.jpg", "rb") as f:
                doc_image = base64.b64encode(f.read()).decode()

            with open("tests/fixtures/selfie_extreme_angle.jpg", "rb") as f:
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
            # Should detect quality issue
            assert result["data"]["selfie_quality_score"] < 0.8

    @pytest.mark.asyncio
    async def test_very_small_face(self):
        """Test face verification with very small face in image"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            with open("tests/fixtures/passport_photo.jpg", "rb") as f:
                doc_image = base64.b64encode(f.read()).decode()

            with open("tests/fixtures/selfie_small_face.jpg", "rb") as f:
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
            # Should fail to detect face or low quality
            assert (
                result["data"]["self_face_detected"] == False
                or result["data"]["selfie_quality_score"] < 0.6
            )


class TestFraudAttacks:
    """Test fraud detection against various attack vectors"""

    @pytest.mark.asyncio
    async def test_screen_replay_attack(self):
        """Test detection of screen-based replay attack"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            with open("tests/fixtures/screen_replay.jpg", "rb") as f:
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
            # Should detect as spoof
            assert result["data"]["anti_spoof_score"] < 0.5
            assert result["data"]["liveness_score"] < 0.5

    @pytest.mark.asyncio
    async def test_printed_passport_attack(self):
        """Test detection of printed passport photo"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            with open("tests/fixtures/printed_passport.jpg", "rb") as f:
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
            # Should detect fraud
            assert result["data"]["fraud_score"] > 0.6
            assert result["data"]["fraud_blocked"] == True

    @pytest.mark.asyncio
    async def test_deepfake_detection(self):
        """Test detection of deepfake face"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            with open("tests/fixtures/passport_photo.jpg", "rb") as f:
                doc_image = base64.b64encode(f.read()).decode()

            with open("tests/fixtures/deepfake_face.jpg", "rb") as f:
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
            # Should detect as high fraud risk
            assert result["data"]["fraud_risk"] == "high"
            assert result["data"]["anti_spoof_score"] < 0.5

    @pytest.mark.asyncio
    async def test_different_person_attack(self):
        """Test detection of different person using stolen passport"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            with open("tests/fixtures/passport_person1.jpg", "rb") as f:
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
            # Should reject
            assert result["data"]["match"] == False
            assert result["data"]["similarity"] < 0.7

    @pytest.mark.asyncio
    async def test_similar_person_attack(self):
        """Test detection of similar-looking person"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            with open("tests/fixtures/passport_person1.jpg", "rb") as f:
                doc_image = base64.b64encode(f.read()).decode()

            with open("tests/fixtures/selfie_similar_person.jpg", "rb") as f:
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
            # Should reject or mark for review
            assert (
                result["data"]["match"] == False or result["data"]["similarity"] < 0.85
            )

    @pytest.mark.asyncio
    async def test_multiple_fraud_signals(self):
        """Test detection with multiple fraud signals"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Use low-quality, spoofed image
            with open("tests/fixtures/fraud_multiple_signals.jpg", "rb") as f:
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
            # Should have high fraud risk
            assert result["data"]["fraud_risk"] == "high"
