"""Pipeline orchestrator: coordinates all OCR processing stages."""

import time
import logging
from typing import Dict, Any, Optional
import numpy as np
from PIL import Image

from app.modules.preprocessing import preprocess_full
from app.modules.detection import document_detector
from app.modules.ocr import ocr_engine
from app.modules.mrz import mrz_parser
from app.modules.parser import extract_from_text
from app.modules.validation import validation_engine
from app.services.confidence_scorer import confidence_scorer
from app.services.progress_service import publish_progress, calculate_stage_progress
from app.services.antifraud_engine import antifraud_engine
from app.services.anti_fraud import anti_fraud_checker
from app.services.ocr_fallback import ocr_fallback_engine
from app.config import settings

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.85


class OCRPipeline:
    """
    Full OCR pipeline:
    input → preprocessing → document detection → OCR → MRZ extraction → parsing → validation → confidence scoring → anti-fraud check
    """

    def process(
        self,
        image: np.ndarray,
        task_id: Optional[str] = None,
        ip_address: str = None,
        db_session: Optional[Any] = None,
    ) -> Dict[str, Any]:
        start = time.time()
        stages = {}

        try:
            # Stage 0: Image-level anti-fraud check (blur, glare, moire, copy detection)
            logger.info("Stage 0: Image anti-fraud analysis")
            if task_id:
                publish_progress(
                    task_id, "image_check", calculate_stage_progress("preprocessing")
                )

            image_fraud = anti_fraud_checker.check(image)
            stages["image_fraud"] = {
                "overall_score": image_fraud["overall_score"],
                "blocked": image_fraud["blocked"],
                "risk_level": image_fraud["risk_level"],
                "blur": image_fraud["blur"]["score"],
                "glare": image_fraud["glare"]["score"],
                "moire": image_fraud["moire"]["score"],
                "copy_detection": image_fraud["copy_detection"]["score"],
            }

            if image_fraud["blocked"]:
                elapsed_ms = int((time.time() - start) * 1000)
                logger.warning(
                    f"Image blocked by anti-fraud: score={image_fraud['overall_score']}, risk={image_fraud['risk_level']}"
                )
                return {
                    "status": "blocked",
                    "final_status": "image_quality_failed",
                    "data": {},
                    "mrz_lines": [],
                    "mrz_parsed": {},
                    "mrz_valid": False,
                    "field_confidence": {},
                    "overall_confidence": 0.0,
                    "validation": {"status": "not_run", "all_critical_pass": False},
                    "raw_text": "",
                    "processing_time_ms": elapsed_ms,
                    "stages": stages,
                    "engine_used": "none",
                    "fraud_analysis": {
                        "image_check": image_fraud,
                        "alerts": [],
                        "risk_score": 1.0 - image_fraud["overall_score"],
                        "is_high_risk": True,
                    },
                }

            # Stage 1: Preprocessing
            logger.info("Stage 1: Preprocessing")
            if task_id:
                publish_progress(
                    task_id, "preprocessing", calculate_stage_progress("preprocessing")
                )
            preprocessed = preprocess_full(image)
            stages["preprocessing"] = {
                "doc_detected": preprocessed["doc_detected"],
                "shape": list(preprocessed["enhanced"].shape),
            }

            # Stage 2: Document detection (optional crop)
            logger.info("Stage 2: Document detection")
            if task_id:
                publish_progress(
                    task_id, "detection", calculate_stage_progress("detection")
                )
            detected_image, doc_found = document_detector.detect(image)
            stages["detection"] = {
                "doc_found": doc_found,
                "shape": list(detected_image.shape) if doc_found else None,
            }

            ocr_image = detected_image if doc_found else preprocessed["enhanced"]

            # Stage 3: OCR with fallback strategy
            logger.info("Stage 3: OCR recognition")
            if task_id:
                publish_progress(task_id, "ocr", calculate_stage_progress("ocr"))

            # Convert numpy array to PIL Image for fallback engine
            pil_image = Image.fromarray(ocr_image.astype("uint8"))
            ocr_result = ocr_fallback_engine.execute_fallback_chain(
                pil_image, min_confidence=0.6
            )

            stages["ocr"] = {
                "engine": ocr_result.strategy.value,
                "confidence": ocr_result.confidence,
                "text_length": len(ocr_result.text),
                "fallback_chain": ocr_result.details.get("fallback_chain", {}),
            }

            # Stage 4: MRZ extraction — try both Tesseract and EasyOCR, pick best
            logger.info("Stage 4: MRZ extraction")
            if task_id:
                publish_progress(task_id, "mrz", calculate_stage_progress("mrz"))
            mrz_lines = []
            mrz_parsed = {}

            # Use OCR result from fallback chain
            full_text = ocr_result.text

            # Approach A: Tesseract on MRZ zone (for comparison)
            mrz_tess_text, mrz_tess_conf = ocr_engine.ocr_mrz(
                ocr_image
            )  # Original engine
            logger.info(
                f"Tesseract MRZ: conf={mrz_tess_conf:.3f}, len={len(mrz_tess_text)}"
            )

            best_mrzed = None
            best_score = -1

            for source_name, source_text in [
                ("tesseract", mrz_tess_text),
                ("fallback", full_text),  # Use fallback result
            ]:
                if not source_text.strip():
                    continue

                lines_cand, parsed_cand = mrz_parser.extract_from_text(source_text)
                if not parsed_cand:
                    continue

                score = 0
                if parsed_cand.get("all_checks_valid"):
                    score = 1000
                elif parsed_cand.get("valid"):
                    score = 500
                elif parsed_cand.get("partial"):
                    score = 100

                checks = sum(
                    [
                        parsed_cand.get("passport_check_valid", False),
                        parsed_cand.get("birth_check_valid", False),
                        parsed_cand.get("expiry_check_valid", False),
                        parsed_cand.get("composite_check_valid", False),
                    ]
                )
                score += checks * 50

                if parsed_cand.get("surname") and len(parsed_cand["surname"]) > 2:
                    score += 30
                if (
                    parsed_cand.get("given_names")
                    and len(parsed_cand["given_names"]) > 2
                ):
                    score += 20
                if (
                    parsed_cand.get("birth_date")
                    and len(parsed_cand["birth_date"]) >= 10
                ):
                    score += 20

                logger.info(
                    f"MRZ from {source_name}: score={score}, valid={parsed_cand.get('all_checks_valid', False)}"
                )

                if score > best_score:
                    best_score = score
                    best_mrzed = (lines_cand, parsed_cand, source_name)

            if best_mrzed:
                mrz_lines, mrz_parsed, mrz_source = best_mrzed
                logger.info(f"Best MRZ source: {mrz_source}, score={best_score}")
            else:
                logger.info("No MRZ data found")

            mrz_valid = bool(
                mrz_parsed.get("all_checks_valid") or mrz_parsed.get("valid")
            )

            stages["mrz"] = {
                "found": len(mrz_lines) > 0,
                "valid": mrz_valid,
                "lines_count": len(mrz_lines),
                "type": mrz_parsed.get("type", ""),
                "source": mrz_source if best_mrzed else None,
            }

            # Stage 5: Parsing (MRZ-first)
            logger.info("Stage 5: Parsing")
            if task_id:
                publish_progress(
                    task_id, "parsing", calculate_stage_progress("parsing")
                )
            extracted = extract_from_text(full_text, mrz_parsed)
            stages["parsing"] = {
                "fields_extracted": sum(1 for v in extracted.values() if v),
                "total_fields": len(extracted),
            }

            # Stage 6: Validation
            logger.info("Stage 6: Validation")
            if task_id:
                publish_progress(
                    task_id, "validation", calculate_stage_progress("validation")
                )
            validation = validation_engine.validate(extracted, mrz_parsed)
            stages["validation"] = {
                "status": validation["status"],
                "all_critical_pass": validation["all_critical_pass"],
            }

            # Stage 7: Confidence scoring (per-field)
            logger.info("Stage 7: Confidence scoring")
            if task_id:
                publish_progress(
                    task_id, "confidence", calculate_stage_progress("confidence")
                )
            field_scores = confidence_scorer.score_fields(
                extracted, mrz_parsed, ocr_result.confidence
            )
            overall_confidence = confidence_scorer.overall(
                extracted, mrz_valid, ocr_result.confidence, field_scores
            )
            stages["confidence"] = {
                "overall": overall_confidence,
                "low_confidence_fields": [
                    f for f, s in field_scores.items() if s < CONFIDENCE_THRESHOLD
                ],
            }

            # Stage 8: Anti-fraud check
            logger.info("Stage 8: Anti-fraud analysis")
            if task_id:
                publish_progress(
                    task_id, "antifraud", calculate_stage_progress("antifraud")
                )

            fraud_alerts = []
            fraud_score = 0.0
            is_high_risk = False

            if db_session and ip_address:
                fraud_alerts = antifraud_engine.analyze(
                    db=db_session, passport_data=extracted, ip_address=ip_address
                )
                fraud_score = antifraud_engine.get_risk_score(fraud_alerts)
                is_high_risk = antifraud_engine.is_high_risk(fraud_score)

            stages["antifraud"] = {
                "alerts_count": len(fraud_alerts),
                "risk_score": fraud_score,
                "high_risk": is_high_risk,
                "alerts": [alert.__dict__ for alert in fraud_alerts]
                if fraud_alerts
                else [],
            }

            # Determine final status considering fraud
            if validation["status"] == "invalid":
                final_status = "invalid"
            elif is_high_risk:
                final_status = "high_risk_fraud"
            elif validation["status"] == "needs_review":
                final_status = "needs_review"
            elif overall_confidence < CONFIDENCE_THRESHOLD:
                final_status = "low_confidence"
            else:
                final_status = "valid"

            elapsed_ms = int((time.time() - start) * 1000)

            return {
                "status": "completed",
                "final_status": final_status,
                "data": extracted,
                "mrz_lines": mrz_lines,
                "mrz_parsed": mrz_parsed,
                "mrz_valid": mrz_valid,
                "field_confidence": field_scores,
                "overall_confidence": overall_confidence,
                "validation": validation,
                "raw_text": full_text,
                "processing_time_ms": elapsed_ms,
                "stages": stages,
                "engine_used": ocr_result.strategy.value,
                "fraud_analysis": {
                    "image_check": image_fraud,
                    "alerts": fraud_alerts,
                    "risk_score": fraud_score,
                    "is_high_risk": is_high_risk,
                },
            }

        except Exception as e:
            elapsed_ms = int((time.time() - start) * 1000)
            logger.error(f"Pipeline failed after {elapsed_ms}ms: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "processing_time_ms": elapsed_ms,
                "stages": stages,
            }


pipeline = OCRPipeline()
