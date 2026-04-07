import pytest
import numpy as np
import cv2
from app.services.face_engine import FaceEngine
from app.services.liveness import LivenessDetector
from app.services.anti_spoof import AntiSpoofDetector
from app.services.face_quality import FaceQualityChecker
from app.services.face_decision import FaceDecisionEngine
from app.utils.encryption import encrypt_field, decrypt_field


def create_test_face_image(size=(200, 200)):
    """Create a synthetic face-like image for testing."""
    img = np.zeros((size[0], size[1], 3), dtype=np.uint8)
    cx, cy = size[1] // 2, size[0] // 2

    cv2.ellipse(img, (cx, cy), (60, 80), 0, 0, 360, (180, 140, 120), -1)
    cv2.circle(img, (cx - 20, cy - 20), 8, (50, 50, 50), -1)
    cv2.circle(img, (cx + 20, cy - 20), 8, (50, 50, 50), -1)
    cv2.ellipse(img, (cx, cy + 15), (15, 10), 0, 0, 180, (100, 60, 60), 2)

    noise = np.random.randint(0, 30, img.shape, dtype=np.uint8)
    img = cv2.add(img, noise)

    return img


class TestFaceEngine:
    @pytest.fixture
    def engine(self):
        return FaceEngine()

    def test_cosine_similarity_identical(self, engine):
        emb = np.random.randn(512).astype(np.float32)
        sim = engine.compare_faces(emb, emb.copy())
        assert abs(sim - 1.0) < 0.001

    def test_cosine_similarity_orthogonal(self, engine):
        emb1 = np.zeros(512, dtype=np.float32)
        emb1[0] = 1.0
        emb2 = np.zeros(512, dtype=np.float32)
        emb2[1] = 1.0
        sim = engine.compare_faces(emb1, emb2)
        assert abs(sim) < 0.001

    def test_cosine_similarity_random(self, engine):
        emb1 = np.random.randn(512).astype(np.float32)
        emb2 = np.random.randn(512).astype(np.float32)
        sim = engine.compare_faces(emb1, emb2)
        assert 0.0 <= sim <= 1.0

    def test_compare_faces_none(self, engine):
        sim = engine.compare_faces(None, None)
        assert sim == 0.0

    def test_compare_faces_one_none(self, engine):
        emb = np.random.randn(512).astype(np.float32)
        assert engine.compare_faces(emb, None) == 0.0
        assert engine.compare_faces(None, emb) == 0.0

    def test_batch_comparison(self, engine):
        emb1 = np.random.randn(512).astype(np.float32)
        embs = [np.random.randn(512).astype(np.float32) for _ in range(5)]
        results = engine.compare_faces_batch(emb1, embs)
        assert len(results) == 5
        assert all(0.0 <= s <= 1.0 for s in results)

    def test_batch_with_none(self, engine):
        emb1 = np.random.randn(512).astype(np.float32)
        embs = [
            np.random.randn(512).astype(np.float32),
            None,
            np.random.randn(512).astype(np.float32),
        ]
        results = engine.compare_faces_batch(emb1, embs)
        assert results[1] == 0.0

    def test_embedding_to_from_base64(self, engine):
        emb = np.random.randn(512).astype(np.float32)
        b64 = engine.embedding_to_base64(emb)
        restored = engine.embedding_from_base64(b64)
        assert np.allclose(emb, restored)


class TestLivenessDetector:
    @pytest.fixture
    def detector(self):
        return LivenessDetector()

    def test_texture_analysis(self, detector):
        img = np.random.randint(50, 200, (112, 112, 3), dtype=np.uint8)
        result = detector._texture_analysis(img)
        assert "score" in result
        assert 0.0 <= result["score"] <= 1.0
        assert "entropy" in result

    def test_frequency_analysis(self, detector):
        img = np.random.randint(50, 200, (112, 112, 3), dtype=np.uint8)
        result = detector._frequency_analysis(img)
        assert "score" in result
        assert 0.0 <= result["score"] <= 1.0

    def test_color_distribution(self, detector):
        img = np.random.randint(50, 200, (112, 112, 3), dtype=np.uint8)
        result = detector._color_distribution(img)
        assert "score" in result
        assert 0.0 <= result["score"] <= 1.0

    def test_reflection_check(self, detector):
        white = np.ones((112, 112, 3), dtype=np.uint8) * 250
        result = detector._reflection_check(white)
        assert result["bright_ratio"] > 0.9
        assert result["score"] < 0.5

    def test_full_check(self, detector):
        img = np.random.randint(50, 200, (112, 112, 3), dtype=np.uint8)
        result = detector.check(img)
        assert "overall_score" in result
        assert "is_live" in result
        assert "risk_level" in result
        assert 0.0 <= result["overall_score"] <= 1.0

    def test_risk_levels(self, detector):
        assert detector._risk_level(0.9) == "low"
        assert detector._risk_level(0.6) == "medium"
        assert detector._risk_level(0.3) == "high"


class TestAntiSpoofDetector:
    @pytest.fixture
    def detector(self):
        return AntiSpoofDetector()

    def test_moire_detection(self, detector):
        img = np.random.randint(50, 200, (112, 112, 3), dtype=np.uint8)
        result = detector._detect_moire(img)
        assert "score" in result
        assert 0.0 <= result["score"] <= 1.0

    def test_screen_pattern(self, detector):
        img = np.random.randint(50, 200, (112, 112, 3), dtype=np.uint8)
        result = detector._detect_screen_pattern(img)
        assert "score" in result
        assert 0.0 <= result["score"] <= 1.0

    def test_depth_estimate(self, detector):
        img = np.random.randint(50, 200, (112, 112, 3), dtype=np.uint8)
        result = detector._estimate_depth(img)
        assert "score" in result
        assert 0.0 <= result["score"] <= 1.0

    def test_edge_analysis(self, detector):
        img = np.random.randint(50, 200, (112, 112, 3), dtype=np.uint8)
        result = detector._analyze_edges(img)
        assert "score" in result
        assert "num_contours" in result

    def test_print_attack(self, detector):
        img = np.random.randint(50, 200, (112, 112, 3), dtype=np.uint8)
        result = detector._detect_print_attack(img)
        assert "score" in result
        assert "color_diversity" in result

    def test_full_check(self, detector):
        img = np.random.randint(50, 200, (112, 112, 3), dtype=np.uint8)
        result = detector.check(img)
        assert "overall_score" in result
        assert "is_real" in result
        assert "risk_level" in result
        assert 0.0 <= result["overall_score"] <= 1.0


class TestFaceQualityChecker:
    @pytest.fixture
    def checker(self):
        return FaceQualityChecker()

    def test_blur_check_sharp(self, checker):
        img = np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)
        result = checker._check_blur(img)
        assert "score" in result
        assert "variance" in result

    def test_blur_check_blurry(self, checker):
        img = np.ones((112, 112, 3), dtype=np.uint8) * 128
        result = checker._check_blur(img)
        assert result["variance"] == 0.0
        assert result["score"] < 0.5

    def test_brightness_check(self, checker):
        dark = np.ones((112, 112, 3), dtype=np.uint8) * 20
        bright = np.ones((112, 112, 3), dtype=np.uint8) * 240
        normal = np.ones((112, 112, 3), dtype=np.uint8) * 128

        assert checker._check_brightness(dark)["score"] < 0.5
        assert checker._check_brightness(bright)["score"] < 0.5
        assert checker._check_brightness(normal)["score"] > 0.5

    def test_face_size_check(self, checker):
        small = np.ones((20, 20, 3), dtype=np.uint8)
        large = np.ones((200, 200, 3), dtype=np.uint8)

        assert checker._check_face_size(small)["score"] < 0.5
        assert checker._check_face_size(large)["score"] >= 0.8

    def test_full_quality_check(self, checker):
        img = np.random.randint(50, 200, (112, 112, 3), dtype=np.uint8)
        result = checker.check(img)
        assert "overall_score" in result
        assert "quality_level" in result
        assert "usable" in result
        assert result["quality_level"] in ("high", "medium", "low")


class TestFaceDecisionEngine:
    @pytest.fixture
    def engine(self):
        return FaceDecisionEngine()

    def test_decide_all_pass(self, engine):
        result = engine.decide(
            similarity=0.88,
            liveness_result={"overall_score": 0.85},
            anti_spoof_result={"overall_score": 0.80},
            doc_quality={"overall_score": 0.80},
            selfie_quality={"overall_score": 0.75},
        )
        assert result["match"] is True
        assert result["fraud_risk"] == "low"
        assert result["confidence"] > 0.7

    def test_decide_low_similarity(self, engine):
        result = engine.decide(
            similarity=0.50,
            liveness_result={"overall_score": 0.85},
            anti_spoof_result={"overall_score": 0.80},
            doc_quality={"overall_score": 0.80},
            selfie_quality={"overall_score": 0.75},
        )
        assert result["match"] is False
        assert "similarity_below_threshold" in result["risk_factors"]

    def test_decide_liveness_fail(self, engine):
        result = engine.decide(
            similarity=0.88,
            liveness_result={"overall_score": 0.30},
            anti_spoof_result={"overall_score": 0.80},
            doc_quality={"overall_score": 0.80},
            selfie_quality={"overall_score": 0.75},
        )
        assert result["match"] is False
        assert result["fraud_risk"] == "critical"

    def test_decide_anti_spoof_fail(self, engine):
        result = engine.decide(
            similarity=0.88,
            liveness_result={"overall_score": 0.85},
            anti_spoof_result={"overall_score": 0.20},
            doc_quality={"overall_score": 0.80},
            selfie_quality={"overall_score": 0.75},
        )
        assert result["match"] is False
        assert result["fraud_risk"] == "critical"

    def test_decide_low_quality(self, engine):
        result = engine.decide(
            similarity=0.88,
            liveness_result={"overall_score": 0.85},
            anti_spoof_result={"overall_score": 0.80},
            doc_quality={"overall_score": 0.20},
            selfie_quality={"overall_score": 0.20},
        )
        assert result["match"] is False

    def test_dynamic_threshold_quality_based(self, engine):
        result_high = engine._check_similarity(
            0.78, {"overall_score": 0.9}, {"overall_score": 0.9}
        )
        result_low = engine._check_similarity(
            0.78, {"overall_score": 0.3}, {"overall_score": 0.3}
        )

        assert result_high["threshold"] == 0.80
        assert result_low["threshold"] == 0.70

    def test_confidence_computation(self, engine):
        decisions = {
            "liveness": {"passed": True},
            "anti_spoof": {"passed": True},
            "similarity": {"passed": True},
            "quality": {"passed": True},
        }
        confidence = engine._compute_confidence(
            0.88,
            {"overall_score": 0.85},
            {"overall_score": 0.80},
            {"overall_score": 0.80},
            {"overall_score": 0.75},
            decisions,
        )
        assert 0.0 <= confidence <= 1.0
        assert confidence > 0.6
