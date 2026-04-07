from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc, case

from app.models import PassportData, DashboardUser


def _apply_filters(
    query,
    start_date=None,
    end_date=None,
    citizenship=None,
    gender=None,
    age_group=None,
    min_confidence=None,
    is_foreigner=None,
    uploaded_by=None,
    recognition_status=None,
):
    if start_date:
        query = query.filter(PassportData.created_at >= start_date)
    if end_date:
        query = query.filter(PassportData.created_at <= end_date)
    if citizenship:
        query = query.filter(PassportData.citizenship == citizenship)
    if gender:
        query = query.filter(PassportData.gender == gender)
    if age_group:
        query = query.filter(PassportData.age_group == age_group)
    if min_confidence is not None:
        query = query.filter(PassportData.confidence >= min_confidence)
    if is_foreigner is not None:
        query = query.filter(PassportData.is_foreigner == is_foreigner)
    if uploaded_by is not None:
        query = query.filter(PassportData.uploaded_by == uploaded_by)
    if recognition_status:
        query = query.filter(PassportData.recognition_status == recognition_status)
    return query


# ─── Базовые агрегации ───


def get_total_count(db: Session, **filters) -> int:
    query = db.query(func.count(PassportData.id))
    query = _apply_filters(query, **filters)
    return query.scalar() or 0


def get_by_citizenship(db: Session, **filters) -> dict:
    query = db.query(PassportData.citizenship, func.count(PassportData.id)).group_by(
        PassportData.citizenship
    )
    query = _apply_filters(query, **filters)
    return {row[0] or "unknown": row[1] for row in query.all()}


def get_by_gender(db: Session, **filters) -> dict:
    query = db.query(PassportData.gender, func.count(PassportData.id)).group_by(
        PassportData.gender
    )
    query = _apply_filters(query, **filters)
    return {row[0] or "unknown": row[1] for row in query.all()}


def get_by_age_group(db: Session, **filters) -> dict:
    query = db.query(PassportData.age_group, func.count(PassportData.id)).group_by(
        PassportData.age_group
    )
    query = _apply_filters(query, **filters)
    return {row[0] or "unknown": row[1] for row in query.all()}


def get_confidence_stats(db: Session, **filters) -> dict:
    query = db.query(
        func.avg(PassportData.confidence),
        func.min(PassportData.confidence),
        func.max(PassportData.confidence),
    )
    query = _apply_filters(query, **filters)
    row = query.first()
    return {
        "avg": round(row[0] or 0, 2),
        "min": round(row[1] or 0, 2),
        "max": round(row[2] or 0, 2),
    }


def get_time_series(db: Session, group_by: str = "month", **filters) -> list:
    if group_by == "day":
        period_expr = func.to_char(PassportData.created_at, "YYYY-MM-DD")
    elif group_by == "week":
        period_expr = func.to_char(PassportData.created_at, "IYYY-IW")
    else:
        period_expr = func.to_char(PassportData.created_at, "YYYY-MM")

    query = (
        db.query(period_expr, func.count(PassportData.id))
        .group_by(period_expr)
        .order_by(period_expr)
    )
    query = _apply_filters(query, **filters)
    return [{"period": row[0], "count": row[1]} for row in query.all()]


def get_by_foreigner_status(db: Session, **filters) -> dict:
    query = db.query(PassportData.is_foreigner, func.count(PassportData.id)).group_by(
        PassportData.is_foreigner
    )
    query = _apply_filters(query, **filters)
    return {"local" if not row[0] else "foreign": row[1] for row in query.all()}


# ─── Полная аналитика одним запросом ───


def get_full_analytics(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    citizenship: Optional[str] = None,
    gender: Optional[str] = None,
    age_group: Optional[str] = None,
    min_confidence: Optional[float] = None,
    is_foreigner: Optional[bool] = None,
    time_group_by: str = "month",
) -> dict:
    filters = {
        "start_date": start_date,
        "end_date": end_date,
        "citizenship": citizenship,
        "gender": gender,
        "age_group": age_group,
        "min_confidence": min_confidence,
        "is_foreigner": is_foreigner,
    }

    return {
        "total": get_total_count(db, **filters),
        "by_citizenship": get_by_citizenship(db, **filters),
        "by_gender": get_by_gender(db, **filters),
        "by_age_group": get_by_age_group(db, **filters),
        "by_foreigner_status": get_by_foreigner_status(db, **filters),
        "confidence_stats": get_confidence_stats(db, **filters),
        "time_series": get_time_series(db, group_by=time_group_by, **filters),
    }


# ─── Статистика по пользователям ───


def get_by_user(db: Session, **filters) -> list:
    """Статистика по каждому пользователю: кто сколько обработал, средняя точность."""
    query = (
        db.query(
            DashboardUser.id.label("user_id"),
            DashboardUser.username,
            DashboardUser.role,
            func.count(PassportData.id).label("total"),
            func.avg(PassportData.confidence).label("avg_confidence"),
            func.sum(case((PassportData.is_foreigner == True, 1), else_=0)).label(
                "foreign_count"
            ),
            func.sum(case((PassportData.is_foreigner == False, 1), else_=0)).label(
                "local_count"
            ),
        )
        .outerjoin(PassportData, PassportData.uploaded_by == DashboardUser.id)
        .group_by(DashboardUser.id, DashboardUser.username, DashboardUser.role)
        .order_by(func.count(PassportData.id).desc())
    )
    query = _apply_filters(query, **filters)

    results = []
    for row in query.all():
        total = row.total or 0
        results.append(
            {
                "user_id": row.user_id,
                "username": row.username,
                "role": row.role,
                "total": total,
                "avg_confidence": round(row.avg_confidence or 0, 2),
                "foreign_count": int(row.foreign_count or 0),
                "local_count": int(row.local_count or 0),
            }
        )
    return results


# ─── Детальная точность по полям ───


def get_accuracy_detail(db: Session, **filters) -> dict:
    """Точность распознавания по каждому полю паспорта."""
    query = db.query(PassportData.field_confidence).filter(
        PassportData.field_confidence.isnot(None),
        PassportData.field_confidence != {},
    )
    query = _apply_filters(query, **filters)

    rows = query.all()
    if not rows:
        return {"fields": {}, "overall": {"success": 0, "partial": 0, "failed": 0}}

    field_totals = {}
    field_success = {}

    for (fc,) in rows:
        if isinstance(fc, dict):
            for field_name, conf in fc.items():
                field_totals[field_name] = field_totals.get(field_name, 0) + 1
                if conf >= 80:
                    field_success[field_name] = field_success.get(field_name, 0) + 1

    fields = {}
    for fname, total in field_totals.items():
        success = field_success.get(fname, 0)
        fields[fname] = {
            "total": total,
            "success": success,
            "success_rate": round(success / total * 100, 1) if total else 0,
        }

    status_counts = db.query(
        PassportData.recognition_status,
        func.count(PassportData.id),
    ).group_by(PassportData.recognition_status)
    status_counts = _apply_filters(status_counts, **filters)

    overall = {"success": 0, "partial": 0, "failed": 0}
    for status, cnt in status_counts.all():
        if status in overall:
            overall[status] = cnt

    return {"fields": fields, "overall": overall}


# ─── Список записей с пагинацией ───


def get_passport_records(
    db: Session,
    page: int = 1,
    per_page: int = 50,
    **filters,
) -> dict:
    """Список всех записей с пагинацией, поиском и сортировкой."""
    query = db.query(PassportData).options(joinedload(PassportData.uploader))
    query = _apply_filters(query, **filters)

    total = query.count()
    records = (
        query.order_by(desc(PassportData.created_at))
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    items = []
    for r in records:
        uploader_name = None
        if r.uploader:
            uploader_name = r.uploader.username
        items.append(
            {
                "id": r.id,
                "task_id": r.task_id,
                "first_name": r.first_name,
                "last_name": r.last_name,
                "birth_date": r.birth_date,
                "gender": r.gender,
                "nationality": r.nationality,
                "citizenship": r.citizenship,
                "age_group": r.age_group,
                "is_foreigner": r.is_foreigner,
                "passport_number": r.passport_number,
                "passport_series": r.passport_series,
                "pinfl": r.pinfl,
                "confidence": r.confidence,
                "mrz_valid": r.mrz_valid,
                "recognition_status": r.recognition_status,
                "processing_time_ms": r.processing_time_ms,
                "uploaded_by": uploader_name,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    }


# ─── Детальная карточка записи ───


def get_passport_detail(db: Session, record_id: int) -> Optional[dict]:
    """Полная информация по одной записи."""
    r = (
        db.query(PassportData)
        .options(joinedload(PassportData.uploader))
        .filter(PassportData.id == record_id)
        .first()
    )
    if not r:
        return None

    uploader_name = r.uploader.username if r.uploader else None

    return {
        "id": r.id,
        "task_id": r.task_id,
        "first_name": r.first_name,
        "last_name": r.last_name,
        "middle_name": r.middle_name,
        "birth_date": r.birth_date,
        "gender": r.gender,
        "nationality": r.nationality,
        "citizenship": r.citizenship,
        "age_group": r.age_group,
        "is_foreigner": r.is_foreigner,
        "passport_number": r.passport_number,
        "passport_series": r.passport_series,
        "issue_date": r.issue_date,
        "expiry_date": r.expiry_date,
        "issued_by": r.issued_by,
        "pinfl": r.pinfl,
        "mrz_line1": r.mrz_line1,
        "mrz_line2": r.mrz_line2,
        "mrz_line3": r.mrz_line3,
        "mrz_valid": r.mrz_valid,
        "confidence": r.confidence,
        "ocr_confidence_avg": r.ocr_confidence_avg,
        "mrz_confidence": r.mrz_confidence,
        "field_confidence": r.field_confidence,
        "field_errors": r.field_errors,
        "recognition_status": r.recognition_status,
        "processing_time_ms": r.processing_time_ms,
        "raw_text": r.raw_text,
        "original_scan_path": r.original_scan_path,
        "copy_scan_path": r.copy_scan_path,
        "uploaded_by": uploader_name,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


# ─── Сравнение периодов ───


def compare_periods(
    db: Session,
    start_date_1: datetime,
    end_date_1: datetime,
    start_date_2: datetime,
    end_date_2: datetime,
    **base_filters,
) -> dict:
    """Сравнение двух периодов."""
    f1 = {**base_filters, "start_date": start_date_1, "end_date": end_date_1}
    f2 = {**base_filters, "start_date": start_date_2, "end_date": end_date_2}

    return {
        "period_1": {
            "start": start_date_1.isoformat(),
            "end": end_date_1.isoformat(),
            "total": get_total_count(db, **f1),
            "confidence_stats": get_confidence_stats(db, **f1),
            "by_foreigner_status": get_by_foreigner_status(db, **f1),
        },
        "period_2": {
            "start": start_date_2.isoformat(),
            "end": end_date_2.isoformat(),
            "total": get_total_count(db, **f2),
            "confidence_stats": get_confidence_stats(db, **f2),
            "by_foreigner_status": get_by_foreigner_status(db, **f2),
        },
    }


# ─── Экспорт в CSV ───


def export_to_csv(db: Session, **filters) -> str:
    """Экспорт всех записей в CSV формат."""
    import csv
    import io

    query = db.query(PassportData).options(joinedload(PassportData.uploader))
    query = _apply_filters(query, **filters)
    query = query.order_by(desc(PassportData.created_at))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "ID",
            "Дата",
            "ФИО",
            "Дата рождения",
            "Пол",
            "Гражданство",
            "Возрастная группа",
            "Иностранец",
            "Номер паспорта",
            "Серия",
            "ПИНФЛ",
            "Уверенность",
            "MRZ валиден",
            "Статус",
            "Загрузил",
            "Время обработки (мс)",
        ]
    )

    for r in query.all():
        uploader_name = r.uploader.username if r.uploader else ""
        writer.writerow(
            [
                r.id,
                r.created_at.isoformat() if r.created_at else "",
                f"{r.last_name} {r.first_name} {r.middle_name}".strip(),
                r.birth_date or "",
                r.gender or "",
                r.citizenship or "",
                r.age_group or "",
                "Да" if r.is_foreigner else "Нет",
                r.passport_number or "",
                r.passport_series or "",
                r.pinfl or "",
                round(r.confidence, 2) if r.confidence else 0,
                "Да" if r.mrz_valid else "Нет",
                r.recognition_status or "",
                uploader_name,
                r.processing_time_ms or 0,
            ]
        )

    return output.getvalue()
