import uuid
import base64
import imghdr
import logging
import magic
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import cv2
import numpy as np
import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import json

from app.database import get_db
from app.models import PassportData
from app.schemas import (
    PassportDataResponse,
    PassportListResponse,
    PassportOcrTestResponse,
    PassportScanResponse,
    PassportStatusResponse,
)
from app.tasks.ocr_task import process_ocr
from app.config import settings
from app.routers.admin import require_admin, require_observer_or_higher
from app.services.ocr_analyzer import analyze_passport_image
from app.services.dedup_service import (
    compute_image_hash,
    compute_perceptual_hash,
    check_duplicate,
    increment_duplicate_count,
)
from app.validators import (
    validate_date_format,
    validate_birth_date,
    validate_issue_date,
    normalize_gender,
    normalize_nationality,
    count_valid_fields,
    is_recognized_passport,
    weighted_confidence_score,
    validate_pinfl,
    is_blacklisted_name,
    is_blacklisted_passport,
    is_blacklisted_pinfl,
)
from app.limiter import limiter
from app.ip_throttle import check_ip_throttle, record_upload
from app.services.progress_service import get_progress, STAGE_LABELS

router = APIRouter()
logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(settings.UPLOAD_DIR)
try:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
except (PermissionError, OSError):
    UPLOAD_DIR = Path("/tmp/ocr-uploads")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/tiff",
    "image/bmp",
    "image/webp",
}


def _processing_completed(record: PassportData) -> bool:
    return bool(
        (record.processing_time_ms or 0) > 0
        or (record.raw_text or "").strip()
        or record.first_name
        or record.last_name
        or record.middle_name
        or record.birth_date
        or record.gender
        or record.nationality
        or record.passport_number
        or record.passport_series
        or record.issue_date
        or record.expiry_date
        or record.issued_by
        or record.pinfl
        or record.mrz_line1
        or record.mrz_line2
        or record.mrz_line3
        or record.mrz_valid
    )


@router.post(
    "/scan",
    summary="Загрузить файл в OCR-очередь",
    description="Асинхронная загрузка документа. Требуется авторизация с ролью admin.",
)
@limiter.limit("60/minute")
async def scan_passport(
    request: Request,
    file: UploadFile = File(...),
    copy_file: Optional[UploadFile] = File(default=None),
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_admin),
):
    """
    Загрузить паспорт на распознавание.

    - **file**: основное фото паспорта (обязательно)
    - **copy_file**: копия паспорта (опционально)

    Возвращает task_id для отслеживания статуса.
    При обнаружении дубликата возвращает существующую запись.
    """
    client_ip = request.client.host if request.client else "unknown"

    is_throttled, throttle_reason = check_ip_throttle(client_ip)
    if is_throttled:
        raise HTTPException(status_code=429, detail=throttle_reason)

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")

    ext = Path(file.filename).suffix.lower().lstrip(".")
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail=f"Unsupported format: {ext}")

    contents = await file.read()
    if len(contents) > settings.MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 10MB)")

    mime_type = magic.from_buffer(contents, mime=True)
    if mime_type not in ALLOWED_MIME_TYPES:
        logger.warning(
            "Rejected MIME type: %s from IP=%s filename=%s",
            mime_type,
            client_ip,
            file.filename,
        )
        raise HTTPException(
            status_code=415,
            detail=f"Invalid MIME type: {mime_type}. Allowed: {', '.join(ALLOWED_MIME_TYPES)}",
        )

    nparr = np.frombuffer(contents, np.uint8)
    image_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if image_cv is None:
        raise HTTPException(
            status_code=400, detail="Invalid image data - cannot decode"
        )

    image_hash = compute_image_hash(contents)
    perceptual_hash = compute_perceptual_hash(image_cv)

    is_dup, existing, dup_count = check_duplicate(db, image_hash, perceptual_hash)
    if is_dup:
        dup_count = increment_duplicate_count(db, existing)
        logger.info(
            "Duplicate upload: existing_task=%s, new_filename=%s, count=%d, IP=%s",
            existing.task_id,
            file.filename,
            dup_count,
            client_ip,
        )
        return {
            "task_id": existing.task_id,
            "status": "duplicate",
            "message": "Этот паспорт уже загружен ранее",
            "duplicate": True,
            "duplicate_count": dup_count,
            "existing_record": {
                "id": existing.id,
                "passport_number": existing.passport_number,
                "created_at": existing.created_at.isoformat()
                if existing.created_at
                else None,
            },
        }

    task_id = str(uuid.uuid4())
    safe_filename = os.path.basename(file.filename)
    filename = f"{task_id}_{safe_filename}"
    filepath = UPLOAD_DIR / filename

    with open(filepath, "wb") as f:
        f.write(contents)

    copy_path = None
    if copy_file:
        copy_contents = await copy_file.read()
        safe_copy_filename = os.path.basename(copy_file.filename)
        copy_filename = f"{task_id}_copy_{safe_copy_filename}"
        copy_path = UPLOAD_DIR / copy_filename
        with open(copy_path, "wb") as f:
            f.write(copy_contents)

    passport_data = PassportData(
        task_id=task_id,
        original_scan_path=str(filepath),
        copy_scan_path=str(copy_path) if copy_path else None,
        confidence=0.0,
        image_hash=image_hash,
        perceptual_hash=perceptual_hash,
        created_at=datetime.now(timezone.utc),
    )
    db.add(passport_data)
    db.commit()
    db.refresh(passport_data)

    logger.info(
        "Passport uploaded: task_id=%s, filename=%s, IP=%s, MIME=%s, phash=%s",
        task_id,
        file.filename,
        client_ip,
        mime_type,
        perceptual_hash[:16],
    )

    record_upload(client_ip)

    image_b64 = base64.b64encode(contents).decode("utf-8")
    # Pass IP address to OCR task for fraud detection
    process_ocr.apply_async(args=[task_id, image_b64, client_ip], queue="ocr")

    return {
        "task_id": task_id,
        "status": "processing",
        "message": "Passport uploaded. Processing started.",
        "duplicate": False,
    }


@router.post(
    "/test-ocr",
    response_model=PassportOcrTestResponse,
    summary="Синхронный OCR тест",
    description="Проверяет одно изображение без создания отдельной заявки в списке обработок.",
)
async def test_passport_ocr(
    file: UploadFile = File(...),
    token_data: dict = Depends(require_observer_or_higher),
):
    _ = token_data

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")

    ext = Path(file.filename).suffix.lower().lstrip(".")
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail=f"Unsupported format: {ext}")

    contents = await file.read()
    if len(contents) > settings.MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 10MB)")

    nparr = np.frombuffer(contents, np.uint8)
    image_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if image_cv is None:
        raise HTTPException(status_code=400, detail="Invalid image data")

    analysis = analyze_passport_image(image_cv)
    height, width = image_cv.shape[:2]

    return {
        "filename": file.filename,
        "image": {"width": width, "height": height},
        "doc_detected": analysis["preprocessed"]["doc_detected"],
        "ocr_confidence": analysis["ocr_result"].get("confidence", 0.0),
        "overall_confidence": analysis.get("overall_confidence", 0.0),
        "mrz_valid": analysis["mrz_valid"],
        "mrz_lines": analysis["mrz_lines"],
        "mrz_data": analysis["mrz_parsed"],
        "extracted_fields": analysis["extracted"],
        "validation": analysis["validation"],
        "raw_text": analysis.get("raw_text", analysis["ocr_result"].get("text", "")),
    }


@router.get(
    "/status/{task_id}",
    response_model=PassportStatusResponse,
    summary="Статус OCR-задачи",
)
async def get_status(
    task_id: str,
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_observer_or_higher),
):
    """Проверить статус обработки паспорта"""
    record = db.query(PassportData).filter(PassportData.task_id == task_id).first()

    if not record:
        raise HTTPException(status_code=404, detail="Passport not found")

    if _processing_completed(record):
        status = "completed"
    else:
        status = "processing"

    return {
        "task_id": task_id,
        "status": status,
        "confidence": record.confidence,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


@router.get("/status/{task_id}/sse", summary="SSE поток статуса OCR-задачи")
async def status_sse(
    task_id: str,
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_observer_or_higher),
):
    """Server-Sent Events для мониторинга статуса OCR в реальном времени с прогрессом."""
    record = db.query(PassportData).filter(PassportData.task_id == task_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Passport not found")

    async def event_stream():
        import asyncio

        max_attempts = 60
        for _ in range(max_attempts):
            progress = get_progress(task_id)

            if progress:
                stage = progress.get("stage", "unknown")
                progress_pct = progress.get("progress", 0)
                details = progress.get("details", {})

                if stage == "completed":
                    final_status = details.get("final_status", "completed")
                    confidence = details.get("confidence", 0.0)
                    yield f"data: {json.dumps({'status': final_status, 'confidence': confidence, 'progress': 100, 'stage': stage, 'stage_label': 'Completed'})}\n\n"
                    return

                if stage == "error":
                    yield f"data: {json.dumps({'status': 'error', 'error': details.get('error', 'Unknown error'), 'progress': 0, 'stage': stage})}\n\n"
                    return

                stage_label = STAGE_LABELS.get(stage, stage)
                yield f"data: {json.dumps({'status': 'processing', 'progress': progress_pct, 'stage': stage, 'stage_label': stage_label})}\n\n"

            db.expire(record)
            db.refresh(record)

            if _processing_completed(record):
                valid_fields = count_valid_fields(
                    {
                        "passport_number": record.passport_number or "",
                        "birth_date": record.birth_date or "",
                        "first_name": record.first_name or "",
                        "last_name": record.last_name or "",
                        "pinfl": record.pinfl or "",
                        "mrz_valid": record.mrz_valid or False,
                    }
                )
                status_label = "completed" if valid_fields >= 2 else "low_confidence"
                yield f"data: {json.dumps({'status': status_label, 'confidence': record.confidence, 'progress': 100, 'stage': 'completed', 'stage_label': 'Completed', 'valid_fields': valid_fields})}\n\n"
                return

            await asyncio.sleep(1)

        yield f"data: {json.dumps({'status': 'timeout', 'message': 'OCR processing timeout', 'progress': 0, 'stage': 'timeout'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/result/{task_id}",
    response_model=PassportDataResponse,
    summary="Результат OCR-задачи",
)
async def get_result(
    task_id: str,
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_observer_or_higher),
):
    """Получить результат распознавания паспорта"""
    record = db.query(PassportData).filter(PassportData.task_id == task_id).first()

    if not record:
        raise HTTPException(status_code=404, detail="Passport not found")

    if not _processing_completed(record):
        raise HTTPException(status_code=400, detail="Processing not completed yet")

    return PassportDataResponse(
        id=record.id,
        task_id=record.task_id,
        first_name=record.first_name or "",
        last_name=record.last_name or "",
        middle_name=record.middle_name or "",
        birth_date=record.birth_date or "",
        gender=record.gender or "",
        nationality=record.nationality or "",
        passport_number=record.passport_number or "",
        passport_series=record.passport_series or "",
        issue_date=record.issue_date or "",
        expiry_date=record.expiry_date or "",
        issued_by=record.issued_by or "",
        pinfl=record.pinfl or "",
        mrz_line1=record.mrz_line1,
        mrz_line2=record.mrz_line2,
        mrz_line3=record.mrz_line3,
        mrz_valid=record.mrz_valid or False,
        confidence=record.confidence or 0.0,
        validation_status=record.validation_status or "pending",
        field_confidence=record.field_confidence,
        low_confidence_fields=(
            [f for f, c in (record.field_confidence or {}).items() if c < 0.85]
            if record.field_confidence
            else None
        ),
        engine_used=record.engine_used,
        raw_text=record.raw_text,
        created_at=record.created_at.isoformat() if record.created_at else None,
    )


@router.get(
    "/list",
    response_model=PassportListResponse,
    summary="Список обработанных загрузок",
)
async def list_passports(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    nationality: str = Query(None),
    gender: str = Query(None),
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_observer_or_higher),
):
    """Список всех обработанных паспортов с фильтрацией"""
    query = db.query(PassportData)

    if nationality:
        query = query.filter(PassportData.nationality.ilike(f"%{nationality}%"))
    if gender:
        query = query.filter(PassportData.gender.ilike(f"%{gender}%"))

    total = query.count()
    records = (
        query.order_by(PassportData.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "data": [
            {
                "id": r.id,
                "task_id": r.task_id,
                "first_name": r.first_name,
                "last_name": r.last_name,
                "gender": r.gender,
                "nationality": r.nationality,
                "birth_date": r.birth_date,
                "passport_series": r.passport_series,
                "passport_number": r.passport_number,
                "confidence": r.confidence,
                "duplicate_count": r.duplicate_count or 1,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ],
    }
