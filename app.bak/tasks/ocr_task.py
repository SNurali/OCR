import base64
import logging
from datetime import datetime, timezone
import numpy as np
import cv2
from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import PassportData, UsageRecord
from app.services.pipeline import pipeline
from app.validators import (
    validate_birth_date,
    validate_issue_date,
    normalize_gender,
    normalize_nationality,
    count_valid_fields,
)
from app.services.progress_service import complete_progress, error_progress
from app.services.antifraud_engine import antifraud_engine
from app.utils.metrics import (
    ocr_tasks_total,
    ocr_task_duration,
    ocr_confidence,
    ocr_fraud_alerts_total,
    ocr_documents_processed_total,
    ocr_engine_fallback_total,
)

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.ocr_task.process_ocr",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def process_ocr(
    self,
    task_id: str,
    image_b64: str,
    ip_address: str = None,
    api_key_id: int = 0,
) -> dict:
    db = SessionLocal()
    start_time = datetime.now(timezone.utc)

    try:
        logger.info("Starting OCR pipeline task %s", task_id)

        img_bytes = base64.b64decode(image_b64)
        nparr = np.frombuffer(img_bytes, np.uint8)
        image_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image_cv is None:
            raise ValueError("Invalid image data")

        logger.info("Image decoded, shape: %s", image_cv.shape)

        # Pass db session and ip_address to pipeline for anti-fraud checks
        result = pipeline.process(
            image_cv, task_id=task_id, ip_address=ip_address, db_session=db
        )

        if result["status"] == "error":
            raise RuntimeError(f"Pipeline error: {result.get('error', 'unknown')}")

        data = result["data"]
        processing_time_ms = int(
            (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        )

        record = db.query(PassportData).filter(PassportData.task_id == task_id).first()
        if record:
            raw_first = data.get("first_name", "") or ""
            raw_last = data.get("last_name", "") or ""
            raw_middle = data.get("middle_name", "") or ""
            raw_birth = data.get("birth_date", "") or ""
            raw_gender = data.get("gender", "") or ""
            raw_nationality = data.get("nationality", "") or ""
            raw_passport_number = data.get("passport_number", "") or ""
            raw_passport_series = data.get("passport_series", "") or ""
            raw_issue_date = data.get("issue_date", "") or ""
            raw_expiry_date = data.get("expiry_date", "") or ""
            raw_issued_by = data.get("issued_by", "") or ""
            raw_pinfl = data.get("pinfl", "") or ""

            normalized_gender = normalize_gender(raw_gender)
            normalized_nationality = normalize_nationality(raw_nationality)

            if raw_birth and not validate_birth_date(raw_birth):
                logger.warning(
                    "Invalid birth_date '%s' for task %s, storing as empty",
                    raw_birth,
                    task_id,
                )
                record.birth_date = None
            else:
                record.birth_date = raw_birth or None

            if raw_issue_date and not validate_issue_date(raw_issue_date):
                logger.warning(
                    "Invalid issue_date '%s' for task %s, storing as empty",
                    raw_issue_date,
                    task_id,
                )
                record.issue_date = None
            else:
                record.issue_date = raw_issue_date or None

            if raw_expiry_date and not validate_birth_date(raw_expiry_date):
                logger.warning(
                    "Invalid expiry_date '%s' for task %s, storing as empty",
                    raw_expiry_date,
                    task_id,
                )
                record.expiry_date = None
            else:
                record.expiry_date = raw_expiry_date or None

            record.first_name = raw_first or None
            record.last_name = raw_last or None
            record.middle_name = raw_middle or None
            record.gender = normalized_gender
            record.nationality = normalized_nationality
            record.passport_number = raw_passport_number or None
            record.passport_series = raw_passport_series or None
            record.issued_by = raw_issued_by or None
            record.pinfl = raw_pinfl or None

            mrz_lines = result.get("mrz_lines", [])
            record.mrz_line1 = mrz_lines[0] if len(mrz_lines) > 0 else None
            record.mrz_line2 = mrz_lines[1] if len(mrz_lines) > 1 else None
            record.mrz_line3 = mrz_lines[2] if len(mrz_lines) > 2 else None
            record.mrz_valid = result.get("mrz_valid", False)

            record.confidence = result.get("overall_confidence", 0.0)

            valid_fields = count_valid_fields(
                {
                    "passport_number": raw_passport_number,
                    "birth_date": raw_birth,
                    "first_name": raw_first,
                    "last_name": raw_last,
                    "pinfl": raw_pinfl,
                    "mrz_valid": record.mrz_valid,
                }
            )

            # Update validation status based on fraud analysis
            fraud_analysis = result.get("fraud_analysis", {})
            is_high_risk = fraud_analysis.get("is_high_risk", False)

            if is_high_risk:
                record.validation_status = "high_risk_fraud"
            elif valid_fields >= 2:
                record.validation_status = "valid"
            else:
                record.validation_status = "low_confidence"

            record.field_confidence = result.get("field_confidence", {})
            record.engine_used = result.get("engine_used", "")
            record.document_type = result.get("mrz_parsed", {}).get("type", "")
            record.pipeline_stages = result.get("stages", {})
            record.raw_text = result.get("raw_text", "")
            record.processing_time_ms = processing_time_ms
            record.fraud_risk_score = fraud_analysis.get("risk_score", 0.0)
            record.fraud_alerts = fraud_analysis.get("alerts", [])

            db.commit()

            usage = UsageRecord(
                api_key_id=api_key_id,
                document_id=record.id,
                action="ocr_scan",
                processing_time_ms=processing_time_ms,
                confidence=record.confidence,
                engine_used=result.get("engine_used", ""),
                cost_cents=0,
            )
            db.add(usage)
            db.commit()

            complete_progress(task_id, record.validation_status, record.confidence)

            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            ocr_task_duration.observe(elapsed)
            ocr_confidence.observe(record.confidence)
            ocr_tasks_total.labels(
                status="completed", engine_used=result.get("engine_used", "unknown")
            ).inc()
            ocr_documents_processed_total.labels(
                document_type=result.get("mrz_parsed", {}).get("type", "unknown"),
                final_status=result.get("final_status", "unknown"),
            ).inc()

            if record.mrz_valid:
                ocr_mrz_valid_total.labels(valid="true").inc()
            else:
                ocr_mrz_valid_total.labels(valid="false").inc()

            fraud_analysis = result.get("fraud_analysis", {})
            image_check = fraud_analysis.get("image_check", {})
            if image_check.get("blocked"):
                ocr_fraud_alerts_total.labels(
                    alert_type="image_blocked", severity="high"
                ).inc()

            alerts = fraud_analysis.get("alerts", [])
            for alert in alerts:
                alert_type = getattr(alert, "rule_name", "unknown")
                severity = getattr(alert, "severity", "unknown")
                ocr_fraud_alerts_total.labels(
                    alert_type=alert_type, severity=severity
                ).inc()

            stages = result.get("stages", {})
            fallback_chain = stages.get("ocr", {}).get("fallback_chain", {})
            if isinstance(fallback_chain, dict):
                engines_used = list(fallback_chain.keys())
                for i in range(len(engines_used) - 1):
                    ocr_engine_fallback_total.labels(
                        from_engine=engines_used[i], to_engine=engines_used[i + 1]
                    ).inc()

            logger.info(
                "OCR pipeline task %s completed in %dms, status=%s, confidence=%.3f, valid_fields=%d, fraud_risk=%.3f",
                task_id,
                processing_time_ms,
                record.validation_status,
                record.confidence,
                valid_fields,
                record.fraud_risk_score,
            )

        return {
            "task_id": task_id,
            "status": "completed",
            "confidence": result.get("overall_confidence", 0.0),
            "final_status": result.get("final_status", "pending"),
            "fraud_analysis": result.get("fraud_analysis", {}),
        }

    except Exception as e:
        logger.error("OCR pipeline task %s failed: %s", task_id, str(e), exc_info=True)
        error_progress(task_id, str(e))
        ocr_tasks_total.labels(status="error", engine_used="unknown").inc()
        ocr_errors_total.labels(reason=str(type(e).__name__)).inc()
        raise self.retry(exc=e)
    finally:
        db.close()
