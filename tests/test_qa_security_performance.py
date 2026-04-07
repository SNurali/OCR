import pytest
import asyncio
import base64
import uuid
from httpx import AsyncClient
from app.main import app
import logging

logger = logging.getLogger(__name__)


class TestSecurityVulnerabilities:
    """Test security vulnerabilities and attack vectors"""

    @pytest.mark.asyncio
    async def test_jwt_bypass_attempt(self):
        """Test JWT token bypass"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Try without token
            response = await client.post(
                "/api/ocr/passport", json={"document_image": "fake_image"}
            )

            assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_invalid_jwt_token(self):
        """Test with invalid JWT token"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/ocr/passport",
                json={"document_image": "fake_image"},
                headers={"Authorization": "Bearer invalid_token"},
            )

            assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_expired_jwt_token(self):
        """Test with expired JWT token"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Use expired token
            expired_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNjAwMDAwMDAwfQ.invalid"

            response = await client.post(
                "/api/ocr/passport",
                json={"document_image": "fake_image"},
                headers={"Authorization": f"Bearer {expired_token}"},
            )

            assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_idempotency_key_enforcement(self):
        """Test idempotency key prevents duplicate processing"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            idempotency_key = str(uuid.uuid4())

            with open("tests/fixtures/valid_passport.jpg", "rb") as f:
                image_data = base64.b64encode(f.read()).decode()

            # First request
            response1 = await client.post(
                "/api/kyc/face-verify",
                json={"document_image": image_data, "selfie_image": image_data},
                headers={
                    "Authorization": "Bearer test_token",
                    "Idempotency-Key": idempotency_key,
                },
            )

            assert response1.status_code == 202
            task_id_1 = response1.json()["task_id"]

            # Second request with same idempotency key
            response2 = await client.post(
                "/api/kyc/face-verify",
                json={"document_image": image_data, "selfie_image": image_data},
                headers={
                    "Authorization": "Bearer test_token",
                    "Idempotency-Key": idempotency_key,
                },
            )

            assert response2.status_code == 202
            task_id_2 = response2.json()["task_id"]

            # Should return same task ID
            assert task_id_1 == task_id_2

    @pytest.mark.asyncio
    async def test_sql_injection_attempt(self):
        """Test SQL injection prevention"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Try SQL injection in task_id
            response = await client.get(
                "/api/ocr/result/'; DROP TABLE ocr_results; --",
                headers={"Authorization": "Bearer test_token"},
            )

            # Should not execute SQL
            assert response.status_code in [404, 400]

    @pytest.mark.asyncio
    async def test_unauthorized_data_access(self):
        """Test prevention of accessing other user's data"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Create task as user 1
            with open("tests/fixtures/valid_passport.jpg", "rb") as f:
                image_data = base64.b64encode(f.read()).decode()

            response1 = await client.post(
                "/api/ocr/passport",
                json={"document_image": image_data},
                headers={"Authorization": "Bearer user1_token"},
            )

            task_id = response1.json()["task_id"]

            # Try to access as user 2
            response2 = await client.get(
                f"/api/ocr/result/{task_id}",
                headers={"Authorization": "Bearer user2_token"},
            )

            # Should be forbidden
            assert response2.status_code == 403

    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Test rate limiting protection"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Make many requests rapidly
            responses = []
            for i in range(70):  # Limit is 60/min
                response = await client.get(
                    "/api/health", headers={"Authorization": "Bearer test_token"}
                )
                responses.append(response.status_code)

            # Should have some 429 (Too Many Requests)
            assert 429 in responses

    @pytest.mark.asyncio
    async def test_xss_prevention(self):
        """Test XSS prevention in responses"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(
                "/api/health", headers={"Authorization": "Bearer test_token"}
            )

            # Response should not contain unescaped HTML
            assert "<script>" not in response.text
            assert response.headers.get("Content-Type") == "application/json"


class TestPerformance:
    """Test performance under load"""

    @pytest.mark.asyncio
    async def test_single_ocr_latency(self):
        """Test single OCR request latency"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            with open("tests/fixtures/valid_passport.jpg", "rb") as f:
                image_data = base64.b64encode(f.read()).decode()

            import time

            start = time.time()

            response = await client.post(
                "/api/ocr/passport",
                json={"document_image": image_data},
                headers={"Authorization": "Bearer test_token"},
            )

            latency = (time.time() - start) * 1000  # ms

            assert response.status_code == 202
            assert latency < 1000  # Should be < 1 second

    @pytest.mark.asyncio
    async def test_face_verification_latency(self):
        """Test face verification latency"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            with open("tests/fixtures/valid_passport.jpg", "rb") as f:
                doc_image = base64.b64encode(f.read()).decode()

            with open("tests/fixtures/selfie_same_person.jpg", "rb") as f:
                selfie_image = base64.b64encode(f.read()).decode()

            import time

            start = time.time()

            response = await client.post(
                "/api/kyc/face-verify",
                json={"document_image": doc_image, "selfie_image": selfie_image},
                headers={"Authorization": "Bearer test_token"},
            )

            latency = (time.time() - start) * 1000  # ms

            assert response.status_code == 202
            assert latency < 2000  # Should be < 2 seconds

    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test handling concurrent requests"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            with open("tests/fixtures/valid_passport.jpg", "rb") as f:
                image_data = base64.b64encode(f.read()).decode()

            # Send 10 concurrent requests
            tasks = []
            for i in range(10):
                task = client.post(
                    "/api/ocr/passport",
                    json={"document_image": image_data},
                    headers={"Authorization": "Bearer test_token"},
                )
                tasks.append(task)

            responses = await asyncio.gather(*tasks)

            # All should succeed
            assert all(r.status_code == 202 for r in responses)

            # All should have unique task IDs
            task_ids = [r.json()["task_id"] for r in responses]
            assert len(set(task_ids)) == len(task_ids)

    @pytest.mark.asyncio
    async def test_queue_processing_time(self):
        """Test Celery queue processing time"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            with open("tests/fixtures/valid_passport.jpg", "rb") as f:
                image_data = base64.b64encode(f.read()).decode()

            response = await client.post(
                "/api/ocr/passport",
                json={"document_image": image_data},
                headers={"Authorization": "Bearer test_token"},
            )

            task_id = response.json()["task_id"]

            import time

            start = time.time()

            # Poll for result
            while True:
                result_response = await client.get(
                    f"/api/ocr/result/{task_id}",
                    headers={"Authorization": "Bearer test_token"},
                )

                if result_response.json()["status"] == "completed":
                    break

                await asyncio.sleep(0.5)

                if time.time() - start > 30:  # 30 second timeout
                    pytest.fail("OCR processing took too long")

            processing_time = (time.time() - start) * 1000  # ms

            # Should complete within 30 seconds
            assert processing_time < 30000

    @pytest.mark.asyncio
    async def test_memory_efficiency(self):
        """Test memory efficiency with large images"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Use large image
            with open("tests/fixtures/large_passport.jpg", "rb") as f:
                image_data = base64.b64encode(f.read()).decode()

            response = await client.post(
                "/api/ocr/passport",
                json={"document_image": image_data},
                headers={"Authorization": "Bearer test_token"},
            )

            # Should handle large images
            assert response.status_code == 202


class TestConsistency:
    """Test consistency and determinism"""

    @pytest.mark.asyncio
    async def test_same_input_same_output(self):
        """Test that same input produces same output"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            with open("tests/fixtures/valid_passport.jpg", "rb") as f:
                image_data = base64.b64encode(f.read()).decode()

            # First request
            response1 = await client.post(
                "/api/ocr/passport",
                json={"document_image": image_data},
                headers={"Authorization": "Bearer test_token"},
            )

            task_id_1 = response1.json()["task_id"]
            await asyncio.sleep(2)

            result1_response = await client.get(
                f"/api/ocr/result/{task_id_1}",
                headers={"Authorization": "Bearer test_token"},
            )
            result1 = result1_response.json()["data"]

            # Second request with same image
            response2 = await client.post(
                "/api/ocr/passport",
                json={"document_image": image_data},
                headers={"Authorization": "Bearer test_token"},
            )

            task_id_2 = response2.json()["task_id"]
            await asyncio.sleep(2)

            result2_response = await client.get(
                f"/api/ocr/result/{task_id_2}",
                headers={"Authorization": "Bearer test_token"},
            )
            result2 = result2_response.json()["data"]

            # Results should be identical
            assert result1["first_name"] == result2["first_name"]
            assert result1["last_name"] == result2["last_name"]
            assert result1["passport_number"] == result2["passport_number"]

    @pytest.mark.asyncio
    async def test_shadow_mode_divergence_tracking(self):
        """Test shadow mode divergence detection"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Enable shadow mode
            admin_response = await client.put(
                "/api/admin/feature-flags/FEATURE_SHADOW_MODE",
                json={"enabled": True, "rollout_percentage": 100},
                headers={"Authorization": "Bearer admin_token"},
            )

            assert admin_response.status_code == 200

            with open("tests/fixtures/valid_passport.jpg", "rb") as f:
                image_data = base64.b64encode(f.read()).decode()

            response = await client.post(
                "/api/ocr/passport",
                json={"document_image": image_data},
                headers={"Authorization": "Bearer test_token"},
            )

            task_id = response.json()["task_id"]

            await asyncio.sleep(2)

            # Check shadow mode results
            shadow_response = await client.get(
                f"/api/admin/shadow-mode/task/{task_id}",
                headers={"Authorization": "Bearer admin_token"},
            )

            assert shadow_response.status_code == 200
            shadow_results = shadow_response.json()

            # Should have comparison results
            assert len(shadow_results) > 0
