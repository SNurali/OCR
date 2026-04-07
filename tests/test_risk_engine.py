import pytest
import json
import numpy as np
from app.services.risk_engine import RiskEngine


class TestRiskEngine:
    @pytest.fixture
    def engine(self):
        return RiskEngine()

    def test_approve_decision(self, engine):
        result = engine.compute(
            face_similarity=0.90,
            liveness_score=0.90,
            anti_spoof_score=0.85,
            doc_quality=0.80,
            selfie_quality=0.75,
            ocr_confidence=0.85,
            mrz_valid=True,
            repeat_attempts=0,
            device_risk=0.0,
            fraud_history_score=0.0,
        )
        assert result["decision"] == "approve"
        assert result["final_risk_score"] > 0.75
        assert result["recommended_action"]["manual_review"] is False
        assert result["recommended_action"]["action"] == "auto_approve"

    def test_review_required_decision(self, engine):
        result = engine.compute(
            face_similarity=0.72,
            liveness_score=0.70,
            anti_spoof_score=0.65,
            doc_quality=0.60,
            selfie_quality=0.55,
            ocr_confidence=0.50,
            mrz_valid=False,
            repeat_attempts=1,
            device_risk=0.2,
            fraud_history_score=0.0,
        )
        assert result["decision"] == "review_required"
        assert result["recommended_action"]["manual_review"] is True
        assert result["recommended_action"]["sla_minutes"] == 30

    def test_reject_decision(self, engine):
        result = engine.compute(
            face_similarity=0.40,
            liveness_score=0.35,
            anti_spoof_score=0.30,
            doc_quality=0.30,
            selfie_quality=0.25,
            ocr_confidence=0.20,
            mrz_valid=False,
            repeat_attempts=5,
            device_risk=0.8,
            fraud_history_score=0.6,
        )
        assert result["decision"] == "reject"
        assert result["recommended_action"]["block_retries"] is True
        assert result["recommended_action"]["retry_after_minutes"] == 60

    def test_liveness_hard_reject(self, engine):
        result = engine.compute(
            face_similarity=0.95,
            liveness_score=0.20,
            anti_spoof_score=0.90,
            doc_quality=0.80,
            selfie_quality=0.75,
        )
        assert result["decision"] == "reject"
        assert "low_liveness" in result["risk_factors"]

    def test_anti_spoof_hard_reject(self, engine):
        result = engine.compute(
            face_similarity=0.95,
            liveness_score=0.90,
            anti_spoof_score=0.20,
            doc_quality=0.80,
            selfie_quality=0.75,
        )
        assert result["decision"] == "reject"
        assert "suspected_spoof" in result["risk_factors"]

    def test_repeat_attempts_penalty(self, engine):
        result_low = engine.compute(
            face_similarity=0.80,
            liveness_score=0.80,
            anti_spoof_score=0.80,
            doc_quality=0.70,
            selfie_quality=0.70,
            repeat_attempts=0,
        )
        result_high = engine.compute(
            face_similarity=0.80,
            liveness_score=0.80,
            anti_spoof_score=0.80,
            doc_quality=0.70,
            selfie_quality=0.70,
            repeat_attempts=5,
        )
        assert result_high["final_risk_score"] < result_low["final_risk_score"]
        assert "multiple_attempts" in result_high["risk_factors"]

    def test_mrz_bonus(self, engine):
        result_with_mrz = engine.compute(
            face_similarity=0.75,
            liveness_score=0.75,
            anti_spoof_score=0.75,
            doc_quality=0.60,
            selfie_quality=0.60,
            mrz_valid=True,
        )
        result_without_mrz = engine.compute(
            face_similarity=0.75,
            liveness_score=0.75,
            anti_spoof_score=0.75,
            doc_quality=0.60,
            selfie_quality=0.60,
            mrz_valid=False,
        )
        assert (
            result_with_mrz["final_risk_score"] > result_without_mrz["final_risk_score"]
        )

    def test_risk_score_bounds(self, engine):
        result = engine.compute(
            face_similarity=0.0,
            liveness_score=0.0,
            anti_spoof_score=0.0,
            doc_quality=0.0,
            selfie_quality=0.0,
            repeat_attempts=10,
            device_risk=1.0,
            fraud_history_score=1.0,
        )
        assert 0.0 <= result["final_risk_score"] <= 1.0

    def test_penalty_breakdown(self, engine):
        result = engine.compute(
            face_similarity=0.80,
            liveness_score=0.80,
            anti_spoof_score=0.80,
            doc_quality=0.70,
            selfie_quality=0.70,
            repeat_attempts=3,
            device_risk=0.5,
            fraud_history_score=0.4,
        )
        breakdown = result["penalty_breakdown"]
        assert "repeat_penalty" in breakdown
        assert "device_penalty" in breakdown
        assert "fraud_penalty" in breakdown
        assert "total_penalty" in breakdown
        assert breakdown["repeat_penalty"] > 0
        assert breakdown["device_penalty"] > 0
        assert breakdown["fraud_penalty"] > 0

    def test_recommended_action_structure(self, engine):
        for decision in ["approve", "review_required", "reject"]:
            result = engine._recommended_action(decision)
            assert "action" in result
            assert "manual_review" in result
            assert "notify_user" in result
            assert "log_level" in result
