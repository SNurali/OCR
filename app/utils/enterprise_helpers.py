from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.services.shadow_mode import ShadowModeService
from app.services.feature_flags import FeatureFlagService
import asyncio
import logging

logger = logging.getLogger(__name__)


class ShadowModeExecutor:
    """Execute shadow mode comparisons for pipeline stages"""

    @staticmethod
    async def execute_ocr_shadow(
        db: Session,
        task_id: str,
        user_id: int,
        production_result: Dict[str, Any],
        shadow_ocr_func,
        document_image: bytes,
    ) -> Optional[Dict[str, Any]]:
        """Execute OCR in shadow mode and compare results"""

        if not ShadowModeService.is_shadow_mode_enabled(db):
            return None

        try:
            # Run shadow OCR in parallel
            shadow_result = await shadow_ocr_func(document_image)

            # Record comparison
            ShadowModeService.record_comparison(
                db, task_id, user_id, "ocr", production_result, shadow_result
            )

            logger.info(
                f"Shadow OCR comparison recorded for task {task_id}",
                extra={"task_id": task_id},
            )

            return shadow_result
        except Exception as e:
            logger.error(
                f"Shadow OCR execution failed: {str(e)}", extra={"task_id": task_id}
            )
            return None

    @staticmethod
    async def execute_face_shadow(
        db: Session,
        task_id: str,
        user_id: int,
        production_result: Dict[str, Any],
        shadow_face_func,
        doc_image: bytes,
        selfie_image: bytes,
    ) -> Optional[Dict[str, Any]]:
        """Execute face verification in shadow mode and compare results"""

        if not ShadowModeService.is_shadow_mode_enabled(db):
            return None

        try:
            # Run shadow face verification in parallel
            shadow_result = await shadow_face_func(doc_image, selfie_image)

            # Record comparison
            ShadowModeService.record_comparison(
                db,
                task_id,
                user_id,
                "face_verification",
                production_result,
                shadow_result,
            )

            logger.info(
                f"Shadow face comparison recorded for task {task_id}",
                extra={"task_id": task_id},
            )

            return shadow_result
        except Exception as e:
            logger.error(
                f"Shadow face execution failed: {str(e)}", extra={"task_id": task_id}
            )
            return None

    @staticmethod
    async def execute_risk_engine_shadow(
        db: Session,
        task_id: str,
        user_id: int,
        production_result: Dict[str, Any],
        shadow_risk_func,
        ocr_data: Dict[str, Any],
        face_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Execute risk engine in shadow mode and compare results"""

        if not ShadowModeService.is_shadow_mode_enabled(db):
            return None

        try:
            # Run shadow risk engine in parallel
            shadow_result = await shadow_risk_func(ocr_data, face_data)

            # Record comparison
            ShadowModeService.record_comparison(
                db, task_id, user_id, "risk_engine", production_result, shadow_result
            )

            logger.info(
                f"Shadow risk engine comparison recorded for task {task_id}",
                extra={"task_id": task_id},
            )

            return shadow_result
        except Exception as e:
            logger.error(
                f"Shadow risk engine execution failed: {str(e)}",
                extra={"task_id": task_id},
            )
            return None


class FeatureFlagChecker:
    """Helper to check feature flags in services"""

    @staticmethod
    def is_liveness_enabled(db: Session) -> bool:
        return FeatureFlagService.is_enabled(db, "FEATURE_LIVENESS")

    @staticmethod
    def is_face_match_enabled(db: Session) -> bool:
        return FeatureFlagService.is_enabled(db, "FEATURE_FACE_MATCH")

    @staticmethod
    def is_anti_spoof_enabled(db: Session) -> bool:
        return FeatureFlagService.is_enabled(db, "FEATURE_ANTI_SPOOF")

    @staticmethod
    def is_hybrid_ocr_enabled(db: Session) -> bool:
        return FeatureFlagService.is_enabled(db, "FEATURE_HYBRID_OCR")

    @staticmethod
    def is_fraud_detection_enabled(db: Session) -> bool:
        return FeatureFlagService.is_enabled(db, "FEATURE_FRAUD_DETECTION")

    @staticmethod
    def is_shadow_mode_enabled(db: Session) -> bool:
        return FeatureFlagService.is_enabled(db, "FEATURE_SHADOW_MODE")
