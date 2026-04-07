import uuid
import base64
from datetime import datetime
from pathlib import Path
import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Request
from sqlalchemy.orm import Session

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
from app.limiter import limiter

router = APIRouter()

UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "uploads/passports"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


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
    response_model=PassportScanResponse,
    summary="Загрузить файл в OCR-очередь",
    description="Асинхронная загрузка документа. Требуется авторизация с ролью admin.",
)
@limiter.limit("60/minute")
async def scan_passport(
    request: Request,
    file: UploadFile = File(...),
    copy_file: UploadFile = File(None),
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_admin),
):
    """
    Загрузить паспорт на распознавание.

    - **file**: основное фото паспорта (обязательно)
    - **copy_file**: копия паспорта (опционально)

    Возвращает task_id для отслеживания статуса.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")

    ext = Path(file.filename).suffix.lower().lstrip(".")
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail=f"Unsupported format: {ext}")

    contents = await file.read()
    if len(contents) > settings.MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 10MB)")

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

    user_id = (
        token_data.get("user", {}).id
        if isinstance(token_data.get("user"), object)
        else token_data.get("payload", {}).get("sub")
    )

    passport_data = PassportData(
        task_id=task_id,
        original_scan_path=str(filepath),
        copy_scan_path=str(copy_path) if copy_path else None,
        confidence=0.0,
        uploaded_by=int(user_id) if user_id else None,
        created_at=datetime.utcnow(),
    )
    db.add(passport_data)
    db.commit()
    db.refresh(passport_data)

    image_b64 = base64.b64encode(contents).decode("utf-8")
    process_ocr.apply_async(args=[task_id, image_b64], queue="ocr")

    return {
        "task_id": task_id,
        "status": "processing",
        "message": "Passport uploaded. Processing started.",
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

    # Передаём сырые байты напрямую в VLM-пайплайн
    analysis = analyze_passport_image(contents)

    # Для обратной совместимости: определяем размеры через PIL
    from PIL import Image
    import io

    img = Image.open(io.BytesIO(contents))
    width, height = img.size

    return {
        "filename": file.filename,
        "image": {"width": width, "height": height},
        "doc_detected": True,  # VLM всегда работает с документом
        "ocr_confidence": analysis["validation"].get("overall_confidence", 0.0),
        "overall_confidence": analysis["validation"].get("overall_confidence", 0.0),
        "mrz_valid": analysis["validation"].get("mrz_valid", False),
        "mrz_lines": [],
        "mrz_data": {},
        "extracted_fields": analysis["extracted"],
        "validation": analysis["validation"],
        "raw_text": "",  # VLM не возвращает сырой текст
    }


@router.get(
    "/status/{id}",
    response_model=PassportStatusResponse,
    summary="Статус OCR-задачи",
)
async def get_status(
    id: str,
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_observer_or_higher),
):
    """Проверить статус обработки паспорта"""
    record = db.query(PassportData).filter(PassportData.task_id == id).first()

    if not record:
        raise HTTPException(status_code=404, detail="Passport not found")

    if _processing_completed(record):
        status = "completed"
    else:
        status = "processing"

    return {
        "task_id": id,
        "status": status,
        "confidence": record.confidence,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


@router.get(
    "/result/{id}",
    response_model=PassportDataResponse,
    summary="Результат OCR-задачи",
)
async def get_result(
    id: str,
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_observer_or_higher),
):
    """Получить результат распознавания паспорта"""
    record = db.query(PassportData).filter(PassportData.task_id == id).first()

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
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ],
    }
