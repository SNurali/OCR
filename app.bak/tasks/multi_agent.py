"""Multi-agent Celery chain: splits OCR pipeline into independent tasks.

Architecture:
    upload → detect_task → ocr_task → extract_task → validate_task → fraud_task → save_task

Each stage is a separate Celery task with its own queue and retry policy.
"""

import base64
import logging
import numpy as np
import cv2

from celery import chain, group
from app.celery_app import celery_app
from app.services.pipeline import pipeline
from app.services.antifraud_engine import antifraud_engine
from app.services.confidence_scorer import confidence_scorer
from app.database import SessionLocal
from app.models import PassportData

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.multi_agent.detect_document",
    bind=True,
    queue="ocr",
    max_retries=2,
    default_retry_delay=30,
)
def detect_document(self, image_b64: str, task_id: str) -> dict:
    """Stage 1: Document detection and preprocessing."""
    try:
        img_bytes = base64.b64decode(image_b64)
        nparr = np.frombuffer(img_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        from app.modules.preprocessing import preprocess_full
        from app.modules.detection import document_detector

        preprocessed = preprocess_full(image)
        detected_image, doc_found = document_detector.detect(image)

        ocr_image = detected_image if doc_found else preprocessed["enhanced"]
        _, buffer = cv2.imencode(".png", ocr_image)
        ocr_image_b64 = base64.b64encode(buffer).decode()

        return {
            "task_id": task_id,
            "image_b64": ocr_image_b64,
            "doc_found": doc_found,
            "preprocessing": {
                "doc_detected": preprocessed["doc_detected"],
                "shape": list(preprocessed["enhanced"].shape),
            },
        }
    except Exception as e:
        logger.error("detect_document failed: %s", e)
        raise self.retry(exc=e)


@celery_app.task(
    name="app.tasks.multi_agent.run_ocr",
    bind=True,
    queue="ocr",
    max_retries=2,
    default_retry_delay=30,
)
def run_ocr(self, image_b64: str, task_id: str) -> dict:
    """Stage 2: Run OCR with fallback/ensemble."""
    try:
        img_bytes = base64.b64decode(image_b64)
        nparr = np.frombuffer(img_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        from PIL import Image
        from app.services.ocr_fallback import ocr_fallback_engine

        pil_image = Image.fromarray(image.astype("uint8"))
        result = ocr_fallback_engine.execute_fallback_chain(
            pil_image, min_confidence=0.6
        )

        return {
            "task_id": task_id,
            "text": result.text,
            "confidence": result.confidence,
            "engine": result.strategy.value,
            "details": result.details,
        }
    except Exception as e:
        logger.error("run_ocr failed: %s", e)
        raise self.retry(exc=e)


@celery_app.task(
    name="app.tasks.multi_agent.extract_and_validate",
    queue="ocr",
)
def extract_and_validate(ocr_result: dict, task_id: str) -> dict:
    """Stage 3: Parse, validate, score."""
    from app.modules.mrz import mrz_parser
    from app.modules.parser import extract_from_text
    from app.modules.validation import validation_engine

    full_text = ocr_result["text"]
    mrz_lines, mrz_parsed = mrz_parser.extract_from_text(full_text)
    mrz_valid = bool(mrz_parsed.get("all_checks_valid") or mrz_parsed.get("valid"))

    extracted = extract_from_text(full_text, mrz_parsed)
    validation = validation_engine.validate(extracted, mrz_parsed)
    field_scores = confidence_scorer.score_fields(
        extracted, mrz_parsed, ocr_result["confidence"]
    )
    overall = confidence_scorer.overall(
        extracted, mrz_valid, ocr_result["confidence"], field_scores
    )

    return {
        "task_id": task_id,
        "extracted": extracted,
        "mrz_parsed": mrz_parsed,
        "mrz_valid": mrz_valid,
        "mrz_lines": mrz_lines,
        "validation": validation,
        "field_scores": field_scores,
        "overall_confidence": overall,
        "raw_text": full_text,
        "engine_used": ocr_result.get("engine", ""),
    }


@celery_app.task(
    name="app.tasks.multi_agent.fraud_and_save",
    queue="ocr",
)
def fraud_and_save(result: dict, ip_address: str = None) -> dict:
    """Stage 4: Fraud analysis + DB save."""
    db = SessionLocal()
    try:
        extracted = result["extracted"]
        fraud_alerts = []
        fraud_score = 0.0
        is_high_risk = False

        if ip_address:
            fraud_alerts = antifraud_engine.analyze(
                db=db, passport_data=extracted, ip_address=ip_address
            )
            fraud_score = antifraud_engine.get_risk_score(fraud_alerts)
            is_high_risk = antifraud_engine.is_high_risk(fraud_score)

        record = (
            db.query(PassportData)
            .filter(PassportData.task_id == result["task_id"])
            .first()
        )
        if record:
            record.first_name = extracted.get("first_name")
            record.last_name = extracted.get("last_name")
            record.middle_name = extracted.get("middle_name")
            record.birth_date = extracted.get("birth_date")
            record.gender = extracted.get("gender")
            record.nationality = extracted.get("nationality")
            record.passport_number = extracted.get("passport_number")
            record.confidence = result["overall_confidence"]
            record.validation_status = "high_risk_fraud" if is_high_risk else "valid"
            record.engine_used = result["engine_used"]
            record.fraud_risk_score = fraud_score
            db.commit()

        return {
            "task_id": result["task_id"],
            "status": "completed",
            "fraud_score": fraud_score,
            "is_high_risk": is_high_risk,
            "confidence": result["overall_confidence"],
        }
    except Exception as e:
        logger.error("fraud_and_save failed: %s", e)
        raise
    finally:
        db.close()


def build_ocr_chain(image_b64: str, task_id: str, ip_address: str = None):
    """Build a Celery chain for the full multi-agent pipeline."""
    return chain(
        detect_document.s(image_b64, task_id),
        run_ocr.s(task_id),
        extract_and_validate.s(task_id),
        fraud_and_save.s(ip_address),
    )
