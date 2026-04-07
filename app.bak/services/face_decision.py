import numpy as np
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class FaceDecisionEngine:
    """Final decision engine for face verification."""

    def __init__(self):
        self.thresholds = {
            "high": 0.80,
            "medium": 0.75,
            "low": 0.70,
        }
        self.liveness_min = 0.55
        self.anti_spoof_min = 0.50
        self.quality_min = 0.35

    def decide(
        self,
        similarity: float,
        liveness_result: Dict,
        anti_spoof_result: Dict,
        doc_quality: Dict,
        selfie_quality: Dict,
    ) -> Dict:
        """Make final verification decision."""
        decisions = {
            "liveness": self._check_liveness(liveness_result),
            "anti_spoof": self._check_anti_spoof(anti_spoof_result),
            "similarity": self._check_similarity(
                similarity, doc_quality, selfie_quality
            ),
            "quality": self._check_quality(doc_quality, selfie_quality),
        }

        match = all(d["passed"] for d in decisions.values())

        risk_factors = []
        if not decisions["liveness"]["passed"]:
            risk_factors.append("liveness_failed")
        if not decisions["anti_spoof"]["passed"]:
            risk_factors.append("anti_spoof_failed")
        if not decisions["similarity"]["passed"]:
            risk_factors.append("similarity_below_threshold")
        if not decisions["quality"]["passed"]:
            risk_factors.append("low_quality")

        fraud_risk = self._assess_fraud_risk(decisions, risk_factors)

        confidence = self._compute_confidence(
            similarity,
            liveness_result,
            anti_spoof_result,
            doc_quality,
            selfie_quality,
            decisions,
        )

        return {
            "match": match,
            "similarity": round(similarity, 4),
            "liveness_score": liveness_result.get("overall_score", 0.0),
            "anti_spoof_score": anti_spoof_result.get("overall_score", 0.0),
            "doc_quality": doc_quality.get("overall_score", 0.0),
            "selfie_quality": selfie_quality.get("overall_score", 0.0),
            "confidence": round(confidence, 4),
            "fraud_risk": fraud_risk,
            "risk_factors": risk_factors,
            "decisions": {k: v["passed"] for k, v in decisions.items()},
            "threshold_used": decisions["similarity"].get("threshold", 0.0),
        }

    def _check_liveness(self, liveness_result: Dict) -> Dict:
        score = liveness_result.get("overall_score", 0.0)
        passed = score >= self.liveness_min
        return {
            "passed": passed,
            "score": score,
            "threshold": self.liveness_min,
        }

    def _check_anti_spoof(self, anti_spoof_result: Dict) -> Dict:
        score = anti_spoof_result.get("overall_score", 0.0)
        passed = score >= self.anti_spoof_min
        return {
            "passed": passed,
            "score": score,
            "threshold": self.anti_spoof_min,
        }

    def _check_similarity(
        self,
        similarity: float,
        doc_quality: Dict,
        selfie_quality: Dict,
    ) -> Dict:
        avg_quality = (
            doc_quality.get("overall_score", 0.5)
            + selfie_quality.get("overall_score", 0.5)
        ) / 2

        if avg_quality >= 0.7:
            level = "high"
        elif avg_quality >= 0.45:
            level = "medium"
        else:
            level = "low"

        threshold = self.thresholds[level]
        passed = similarity >= threshold

        return {
            "passed": passed,
            "similarity": similarity,
            "threshold": threshold,
            "quality_level": level,
        }

    def _check_quality(self, doc_quality: Dict, selfie_quality: Dict) -> Dict:
        doc_passed = doc_quality.get("overall_score", 0.0) >= self.quality_min
        selfie_passed = selfie_quality.get("overall_score", 0.0) >= self.quality_min
        passed = doc_passed and selfie_passed

        return {
            "passed": passed,
            "doc_score": doc_quality.get("overall_score", 0.0),
            "selfie_score": selfie_quality.get("overall_score", 0.0),
            "threshold": self.quality_min,
        }

    def _assess_fraud_risk(self, decisions: Dict, risk_factors: list) -> str:
        critical = [
            "liveness_failed",
            "anti_spoof_failed",
        ]
        has_critical = any(f in risk_factors for f in critical)

        if has_critical:
            return "critical"
        if len(risk_factors) >= 2:
            return "high"
        if len(risk_factors) == 1:
            return "medium"
        return "low"

    def _compute_confidence(
        self,
        similarity: float,
        liveness_result: Dict,
        anti_spoof_result: Dict,
        doc_quality: Dict,
        selfie_quality: Dict,
        decisions: Dict,
    ) -> float:
        weights = {
            "similarity": 0.35,
            "liveness": 0.25,
            "anti_spoof": 0.20,
            "doc_quality": 0.10,
            "selfie_quality": 0.10,
        }

        confidence = (
            similarity * weights["similarity"]
            + liveness_result.get("overall_score", 0.0) * weights["liveness"]
            + anti_spoof_result.get("overall_score", 0.0) * weights["anti_spoof"]
            + doc_quality.get("overall_score", 0.0) * weights["doc_quality"]
            + selfie_quality.get("overall_score", 0.0) * weights["selfie_quality"]
        )

        penalty = 0.0
        for key, decision in decisions.items():
            if not decision["passed"]:
                penalty += 0.1

        confidence = max(0.0, confidence - penalty)
        return float(np.clip(confidence, 0.0, 1.0))


face_decision_engine = FaceDecisionEngine()
