import base64
import logging
from datetime import datetime
from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import PassportData
from app.services.ocr_analyzer import analyze_passport_image

logger = logging.getLogger(__name__)


def _calculate_age_group(birth_date_str: str) -> str:
    if not birth_date_str:
        return "unknown"
    try:
        parts = birth_date_str.split(".")
        if len(parts) == 3:
            year = int(parts[2])
        else:
            year = int(birth_date_str.split("-")[0])
        age = datetime.utcnow().year - year
        if age < 18:
            return "0-18"
        elif age <= 25:
            return "19-25"
        elif age <= 35:
            return "26-35"
        elif age <= 45:
            return "36-45"
        elif age <= 55:
            return "46-55"
        elif age <= 65:
            return "56-65"
        else:
            return "65+"
    except Exception:
        return "unknown"


def _determine_citizenship(nationality: str) -> str:
    if not nationality:
        return "UZ"
    nat_upper = nationality.upper().strip()
    if nat_upper in ("UZB", "UZ", "O'ZBEKISTON", "УЗБ", "УЗБЕКИСТАН"):
        return "UZ"
    return nat_upper


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
) -> dict:
    db = SessionLocal()
    start_time = datetime.utcnow()

    try:
        logger.info(f"Starting VLM OCR task {task_id}")

        # Декодируем base64 в сырые байты — передаём напрямую в VLM
        image_bytes = base64.b64decode(image_b64)

        logger.info(f"Image decoded, size: {len(image_bytes)} bytes")

        # VLM-пайплайн принимает bytes напрямую
        analysis = analyze_passport_image(image_bytes)

        logger.info(f"VLM Analysis completed: {analysis.get('extracted')}")

        extracted = analysis["extracted"]
        validation = analysis["validation"]
        processing_time_ms = int(
            (datetime.utcnow() - start_time).total_seconds() * 1000
        )

        record = db.query(PassportData).filter(PassportData.task_id == task_id).first()
        if record:
            record.first_name = extracted.get("first_name", "")
            record.last_name = extracted.get("last_name", "")
            record.middle_name = extracted.get("middle_name", "")
            record.birth_date = extracted.get("birth_date", "")
            record.gender = extracted.get("gender", "")
            record.nationality = extracted.get("nationality", "")
            record.passport_number = extracted.get("passport_number", "")
            record.passport_series = (
                extracted.get("passport_number", "")[:2]
                if len(extracted.get("passport_number", "")) >= 2
                else ""
            )
            record.issue_date = extracted.get("issue_date", "")
            record.expiry_date = extracted.get("expiry_date", "")
            record.issued_by = extracted.get("issued_by", "")
            record.pinfl = extracted.get("pinfl", "")
            record.mrz_line1 = ""
            record.mrz_line2 = ""
            record.mrz_line3 = ""
            record.mrz_valid = validation.get("mrz_valid", False)
            record.confidence = validation.get("overall_confidence", 0.0)
            record.raw_text = ""
            record.processing_time_ms = processing_time_ms

            # Аналитические поля
            nationality = extracted.get("nationality", "")
            record.citizenship = _determine_citizenship(nationality)
            record.age_group = _calculate_age_group(extracted.get("birth_date", ""))
            record.is_foreigner = record.citizenship != "UZ"
            record.ocr_confidence_avg = validation.get("overall_confidence", 0.0) * 100
            record.mrz_confidence = 100.0 if validation.get("mrz_valid") else 0.0

            # Точность по каждому полю (на основе checks)
            checks = validation.get("checks", {})
            field_conf = {}
            for fname, fvalid in checks.items():
                field_conf[fname] = 100.0 if fvalid else 0.0

            record.field_confidence = field_conf

            # Статус распознавания
            filled = sum(1 for v in checks.values() if v)
            total_fields = len(checks)
            if filled == total_fields:
                record.recognition_status = "success"
            elif filled > total_fields / 2:
                record.recognition_status = "partial"
            else:
                record.recognition_status = "failed"

            db.commit()

        logger.info(f"VLM OCR task {task_id} completed in {processing_time_ms}ms")

        return {
            "task_id": task_id,
            "status": "completed",
            "confidence": record.confidence if record else 0.0,
        }

    except Exception as e:
        logger.error(f"VLM OCR task {task_id} failed: {str(e)}", exc_info=True)
        raise self.retry(exc=e)
    finally:
        db.close()
