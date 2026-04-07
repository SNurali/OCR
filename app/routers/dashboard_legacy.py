from collections import Counter, defaultdict
from datetime import datetime, time
from pathlib import Path
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.auth import create_dashboard_token, verify_password
from app.config import settings
from app.database import get_db
from app.models import DashboardUser, PassportData
from app.routers.admin import require_admin, require_observer_or_higher
from app.schemas import DashboardLoginRequest, DashboardTokenResponse


router = APIRouter()

UPLOAD_DIR = Path("/app/uploads/passports")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _parse_date(value: str | None, end_of_day: bool = False) -> datetime | None:
    if not value:
        return None

    normalized = value.strip()
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            parsed = datetime.strptime(normalized, "%Y-%m-%d")
        except ValueError:
            return None

    if "T" not in normalized and len(normalized) <= 10:
        parsed = datetime.combine(parsed.date(), time.max if end_of_day else time.min)

    return parsed


def _apply_record_filters(
    query,
    nationality: str | None,
    status: str | None,
    date_from: str | None,
    date_to: str | None,
):
    if nationality:
        query = query.filter(PassportData.nationality.ilike(f"%{nationality}%"))

    if status == "approved":
        query = query.filter(
            PassportData.passport_number.isnot(None),
            PassportData.passport_number != "",
        )
    elif status == "pending":
        query = query.filter(
            or_(
                PassportData.passport_number.is_(None),
                PassportData.passport_number == "",
            )
        )
    elif status == "rejected":
        query = query.filter(PassportData.id == -1)

    parsed_from = _parse_date(date_from)
    parsed_to = _parse_date(date_to, end_of_day=True)

    if parsed_from:
        query = query.filter(PassportData.created_at >= parsed_from)
    if parsed_to:
        query = query.filter(PassportData.created_at <= parsed_to)

    return query


def _get_status(record: PassportData) -> str:
    if record.passport_number:
        return "approved"
    return "pending"


def _scan_entries(record: PassportData) -> list[dict]:
    scans: list[dict] = []
    scan_sources = [
        (record.original_scan_path, "original", 1),
        (record.copy_scan_path, "copy", 2),
    ]

    for path_value, scan_type, suffix in scan_sources:
        if not path_value:
            continue

        path = Path(path_value)
        if not path.exists():
            continue

        stat = path.stat()
        scans.append(
            {
                "id": record.id * 10 + suffix,
                "filename": path.name,
                "type": scan_type,
                "file_size": stat.st_size,
                "uploaded_at": record.created_at.isoformat()
                if record.created_at
                else None,
            }
        )

    return scans


def _record_summary(record: PassportData) -> dict:
    scans = _scan_entries(record)
    return {
        "id": record.id,
        "task_id": record.task_id,
        "document_type": "passport",
        "nationality": record.nationality or "",
        "scan_count": len(scans),
        "confidence": record.confidence or 0.0,
        "fraud_score": 0.0,
        "status": _get_status(record),
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "passport_series": record.passport_series or "",
    }


@router.post("/auth/login", response_model=DashboardTokenResponse)
def dashboard_login(
    request: DashboardLoginRequest,
    db: Session = Depends(get_db),
):
    user = (
        db.query(DashboardUser)
        .filter(DashboardUser.username == request.username)
        .first()
    )

    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    token = create_dashboard_token(user.id, user.username)
    return DashboardTokenResponse(access_token=token, expires_in=8 * 60 * 60)


@router.get("/statistics")
def get_statistics(
    nationality: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_observer_or_higher),
):
    query = _apply_record_filters(
        db.query(PassportData),
        nationality=nationality,
        status=status,
        date_from=date_from,
        date_to=date_to,
    )
    records = query.order_by(PassportData.created_at.desc()).all()

    total = len(records)
    approved_count = sum(1 for record in records if _get_status(record) == "approved")
    rejected_count = 0
    pending_count = total - approved_count
    confidence_sum = sum(record.confidence or 0.0 for record in records)
    nationality_counter = Counter(record.nationality or "Unknown" for record in records)

    daily_breakdown_map: dict[str, dict[str, int | str]] = defaultdict(
        lambda: {"date": "", "total": 0, "approved": 0, "rejected": 0, "pending": 0}
    )
    age_groups = {
        "0-18": 0,
        "19-25": 0,
        "26-35": 0,
        "36-45": 0,
        "46-55": 0,
        "56-65": 0,
        "65+": 0,
    }
    male_count = 0
    female_count = 0

    for record in records:
        created_at = record.created_at or datetime.utcnow()
        day_key = created_at.date().isoformat()
        day_entry = daily_breakdown_map[day_key]
        day_entry["date"] = day_key
        day_entry["total"] += 1
        record_status = _get_status(record)
        day_entry[record_status] += 1

        gender = (record.gender or "").upper()
        if gender in {"M", "MALE", "МУЖ", "ERKAK"}:
            male_count += 1
        elif gender in {"F", "FEMALE", "ЖЕН", "AYOL"}:
            female_count += 1

        if record.birth_date:
            try:
                age = (
                    datetime.utcnow() - datetime.strptime(record.birth_date, "%d.%m.%Y")
                ).days // 365
            except ValueError:
                age = None

            if age is not None:
                if age <= 18:
                    age_groups["0-18"] += 1
                elif age <= 25:
                    age_groups["19-25"] += 1
                elif age <= 35:
                    age_groups["26-35"] += 1
                elif age <= 45:
                    age_groups["36-45"] += 1
                elif age <= 55:
                    age_groups["46-55"] += 1
                elif age <= 65:
                    age_groups["56-65"] += 1
                else:
                    age_groups["65+"] += 1

    date_range = "all time"
    if date_from or date_to:
        date_range = f"{date_from or '...'} - {date_to or '...'}"

    return {
        "total_applications": total,
        "total_by_nationality": dict(nationality_counter),
        "approved_count": approved_count,
        "rejected_count": rejected_count,
        "pending_count": pending_count,
        "average_confidence": round(confidence_sum / total, 4) if total else 0.0,
        "fraud_blocked_count": 0,
        "date_range": date_range,
        "daily_breakdown": [
            daily_breakdown_map[key] for key in sorted(daily_breakdown_map.keys())
        ],
        "male_count": male_count,
        "female_count": female_count,
        "age_groups": age_groups,
        "current_user": token_data["user"].username,
    }


@router.post("/search")
def search_applications(
    filters: dict,
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_observer_or_higher),
):
    query = _apply_record_filters(
        db.query(PassportData),
        nationality=filters.get("nationality"),
        status=filters.get("status"),
        date_from=filters.get("date_from"),
        date_to=filters.get("date_to"),
    )

    page = max(int(filters.get("page") or 1), 1)
    limit = max(min(int(filters.get("limit") or 20), 100), 1)
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
        "results": [_record_summary(record) for record in records],
        "current_user": token_data["user"].username,
    }


@router.get("/application/{ocr_result_id}")
def get_application_details(
    ocr_result_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_observer_or_higher),
):
    record = db.query(PassportData).filter(PassportData.id == ocr_result_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Application not found")

    return {
        "ocr_result": {
            **_record_summary(record),
            "first_name": record.first_name or "",
            "last_name": record.last_name or "",
            "middle_name": record.middle_name or "",
            "birth_date": record.birth_date or "",
            "gender": record.gender or "",
            "passport_number": record.passport_number or "",
            "issue_date": record.issue_date or "",
            "expiry_date": record.expiry_date or "",
            "issued_by": record.issued_by or "",
            "pinfl": record.pinfl or "",
            "raw_text": record.raw_text or "",
            "processing_time_ms": record.processing_time_ms or 0,
        },
        "scans": _scan_entries(record),
        "face_verification": None,
        "fraud_events": [],
        "viewer": token_data["user"].username,
    }


@router.get("/scan/{scan_id}")
def get_scan_file(
    scan_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_observer_or_higher),
):
    _ = token_data
    record_id = scan_id // 10
    scan_suffix = scan_id % 10

    record = db.query(PassportData).filter(PassportData.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Scan not found")

    scan_path = (
        record.original_scan_path
        if scan_suffix == 1
        else record.copy_scan_path
        if scan_suffix == 2
        else None
    )
    if not scan_path:
        raise HTTPException(status_code=404, detail="Scan not found")

    path = Path(scan_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Scan file not found")

    return FileResponse(path, filename=path.name)


@router.post("/upload-passport/{ocr_result_id}")
async def upload_passport_scan(
    ocr_result_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_admin),
):
    _ = token_data
    record = db.query(PassportData).filter(PassportData.id == ocr_result_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="OCR result not found")

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")

    ext = Path(file.filename).suffix.lower().lstrip(".")
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file format")

    contents = await file.read()
    if len(contents) > settings.MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large")

    filename = (
        f"{record.task_id}_legacy_copy_{uuid.uuid4().hex}_{Path(file.filename).name}"
    )
    filepath = UPLOAD_DIR / filename
    filepath.write_bytes(contents)

    record.copy_scan_path = str(filepath)
    db.commit()

    return {"message": "Passport copy uploaded", "filename": filename}
