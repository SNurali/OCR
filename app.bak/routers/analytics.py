from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from sqlalchemy import and_, extract, func, or_
from sqlalchemy.orm import Session

from app.auth import decode_dashboard_token, optional_oauth2_scheme
from app.database import get_db
from app.models import PassportData, DashboardUser, UsageRecord, APIKey
from app.schemas import (
    AccessLogsResponse,
    AgeGroupReportResponse,
    DailyBreakdownResponse,
    GenderByAgeResponse,
    GenderReportResponse,
    MonthlyStatsResponse,
    NationalityReportResponse,
    SummaryResponse,
    TimeReportResponse,
    YearlyStatsResponse,
)
from app.validators import (
    validate_birth_date,
    validate_date_format,
    count_valid_fields,
    is_recognized_passport,
)

import logging

router = APIRouter()
logger = logging.getLogger(__name__)

MALE_GENDERS = ["M", "MALE", "МУЖ", "ERKAK"]
FEMALE_GENDERS = ["F", "FEMALE", "ЖЕН", "AYOL"]


def _has_value(column):
    return and_(column.isnot(None), column != "")


def _recognized_passport_clause():
    """
    Паспорт считается распознанным если есть минимум 2 валидных поля.
    Это предотвращает попадание мусорных записей в аналитику.
    """
    valid_birth_date = and_(
        _has_value(PassportData.birth_date),
        PassportData.birth_date.like("__.__.____"),
    )
    valid_passport_number = _has_value(PassportData.passport_number)
    valid_name = or_(
        _has_value(PassportData.first_name),
        _has_value(PassportData.last_name),
    )
    valid_pinfl = _has_value(PassportData.pinfl)
    valid_mrz = PassportData.mrz_valid.is_(True)

    pairs = [
        and_(valid_passport_number, valid_birth_date),
        and_(valid_passport_number, valid_name),
        and_(valid_passport_number, valid_pinfl),
        and_(valid_passport_number, valid_mrz),
        and_(valid_birth_date, valid_name),
        and_(valid_birth_date, valid_pinfl),
        and_(valid_birth_date, valid_mrz),
        and_(valid_name, valid_pinfl),
        and_(valid_name, valid_mrz),
        and_(valid_pinfl, valid_mrz),
    ]

    return or_(*pairs)


def _recognized_passports_query(db: Session):
    return db.query(PassportData).filter(_recognized_passport_clause())


def _count_by_gender(query, genders: list[str]) -> int:
    return query.filter(func.upper(PassportData.gender).in_(genders)).count()


def require_observer_or_higher(
    token: Optional[str] = Query(
        None,
        description="JWT токен в query. Нужен для legacy dashboard compatibility.",
    ),
    bearer_token: Optional[str] = Security(optional_oauth2_scheme),
    db: Session = Depends(get_db),
):
    """Проверка: наблюдатель или администратор (только чтение)"""
    try:
        raw_token = bearer_token or token
        if not raw_token:
            raise HTTPException(status_code=401, detail="JWT token is required")

        payload = decode_dashboard_token(raw_token)
        user = (
            db.query(DashboardUser)
            .filter(DashboardUser.id == int(payload["sub"]))
            .first()
        )

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user.role not in ["admin", "observer"]:
            raise HTTPException(
                status_code=403, detail="Observer or administrator role required"
            )

        if not user.is_active:
            raise HTTPException(status_code=403, detail="User is not active")

        return {"user": user, "payload": payload}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Ошибка авторизации: {str(e)}")


@router.get(
    "/summary",
    response_model=SummaryResponse,
    summary="Сводка по распознанным паспортам",
    description=(
        "Возвращает верхнеуровневые метрики dashboard. В `total_passports` попадают "
        "только загрузки, где OCR распознал минимум 2 паспортных поля. "
        "`total_uploads` содержит все загруженные файлы."
    ),
)
def get_summary(
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_observer_or_higher),
):
    """
    Общая сводка по всем паспортам

    🔓 Доступно: admin, observer
    """
    total_uploads = db.query(PassportData).count()
    recognized_query = _recognized_passports_query(db)
    total = recognized_query.count()
    male_count = _count_by_gender(_recognized_passports_query(db), MALE_GENDERS)
    female_count = _count_by_gender(_recognized_passports_query(db), FEMALE_GENDERS)
    avg_age = calculate_average_age(_recognized_passports_query(db))

    unrecognized = max(total_uploads - total, 0)

    if unrecognized > 0:
        logger.info(
            "Analytics summary: %d total, %d recognized, %d unrecognized",
            total_uploads,
            total,
            unrecognized,
        )

    return {
        "total_passports": total,
        "total_uploads": total_uploads,
        "unrecognized_uploads": unrecognized,
        "male_count": male_count,
        "female_count": female_count,
        "male_percent": round(male_count / total * 100, 2) if total else 0,
        "female_percent": round(female_count / total * 100, 2) if total else 0,
        "average_age": round(avg_age, 1) if avg_age else 0,
    }


@router.get(
    "/gender-report",
    response_model=GenderReportResponse,
    summary="Отчет по полу",
)
def get_gender_report(
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_observer_or_higher),
):
    """
    Отчет по полу: кто больше - мужчин или женщин

    🔓 Доступно: admin, observer
    """
    base_query = _recognized_passports_query(db)
    total = base_query.count()
    male_count = _count_by_gender(_recognized_passports_query(db), MALE_GENDERS)
    female_count = _count_by_gender(_recognized_passports_query(db), FEMALE_GENDERS)

    unknown_count = total - male_count - female_count

    return {
        "total": total,
        "male": {
            "count": male_count,
            "percent": round(male_count / total * 100, 2) if total else 0,
        },
        "female": {
            "count": female_count,
            "percent": round(female_count / total * 100, 2) if total else 0,
        },
        "unknown": {
            "count": unknown_count,
            "percent": round(unknown_count / total * 100, 2) if total else 0,
        },
        "more": "male"
        if male_count > female_count
        else "female"
        if female_count > male_count
        else "equal",
        "difference": abs(male_count - female_count),
    }


@router.get(
    "/age-report",
    response_model=AgeGroupReportResponse,
    summary="Отчет по возрастным группам",
)
def get_age_report(
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_observer_or_higher),
):
    """
    Отчет по возрастным группам

    🔓 Доступно: admin, observer
    """
    age_groups = {
        "0-18": 0,
        "19-25": 0,
        "26-35": 0,
        "36-45": 0,
        "46-55": 0,
        "56-65": 0,
        "65+": 0,
    }

    records = (
        _recognized_passports_query(db)
        .filter(_has_value(PassportData.birth_date))
        .with_entities(PassportData.birth_date)
        .all()
    )

    skipped = 0
    for (birth_date,) in records:
        age = calculate_age_from_birthdate(birth_date)
        if age is None:
            skipped += 1
            logger.warning(
                "Skipped invalid birth_date for age report: '%s' (task context)",
                birth_date,
            )
            continue

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

    if skipped > 0:
        logger.info("Age report: skipped %d records with invalid birth_date", skipped)

    total = sum(age_groups.values())

    return {
        "total": total,
        "groups": age_groups,
        "percentages": {
            k: round(v / total * 100, 2) if total else 0 for k, v in age_groups.items()
        },
        "average_age": calculate_average_age(_recognized_passports_query(db)),
    }


@router.get(
    "/nationality-report",
    response_model=NationalityReportResponse,
    summary="Отчет по гражданству",
)
def get_nationality_report(
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_observer_or_higher),
    limit: int = Query(20, description="Топ N национальностей"),
):
    """
    Отчет по гражданству/национальности

    🔓 Доступно: admin, observer
    """
    results = (
        db.query(PassportData.nationality, func.count(PassportData.id).label("count"))
        .filter(_recognized_passport_clause())
        .filter(_has_value(PassportData.nationality))
        .group_by(PassportData.nationality)
        .order_by(func.count(PassportData.id).desc())
        .limit(limit)
        .all()
    )

    total = (
        _recognized_passports_query(db)
        .filter(_has_value(PassportData.nationality))
        .count()
    )

    return {
        "total": total,
        "nationalities": [
            {
                "name": r.nationality,
                "count": r.count,
                "percent": round(r.count / total * 100, 2) if total else 0,
            }
            for r in results
        ],
    }


@router.get(
    "/time-report",
    response_model=TimeReportResponse,
    summary="Поступления за период",
)
def get_time_report(
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_observer_or_higher),
    period: str = Query("month", description="period: day, week, month, year"),
):
    """
    Отчет по времени: поступления за период

    🔓 Доступно: admin, observer
    """
    now = datetime.now(timezone.utc)

    if period == "day":
        start_date = now - timedelta(days=1)
    elif period == "week":
        start_date = now - timedelta(weeks=1)
    elif period == "month":
        start_date = now - timedelta(days=30)
    elif period == "year":
        start_date = now - timedelta(days=365)
    else:
        start_date = now - timedelta(days=30)

    count = (
        _recognized_passports_query(db)
        .filter(PassportData.created_at >= start_date)
        .count()
    )

    return {
        "period": period,
        "start_date": start_date.isoformat(),
        "end_date": now.isoformat(),
        "count": count,
        "average_per_day": round(count / ((now - start_date).days or 1), 2),
    }


@router.get(
    "/monthly-stats",
    response_model=MonthlyStatsResponse,
    summary="Статистика по месяцам",
)
def get_monthly_stats(
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_observer_or_higher),
    year: int = Query(None, description="Год (по умолчанию текущий)"),
):
    """
    Статистика по месяцам за год

    🔓 Доступно: admin, observer
    """
    if not year:
        year = datetime.now(timezone.utc).year

    monthly_data = (
        db.query(
            extract("month", PassportData.created_at).label("month"),
            func.count(PassportData.id).label("count"),
        )
        .filter(_recognized_passport_clause())
        .filter(extract("year", PassportData.created_at) == year)
        .group_by(extract("month", PassportData.created_at))
        .order_by("month")
        .all()
    )

    months = {
        1: "Январь",
        2: "Февраль",
        3: "Март",
        4: "Апрель",
        5: "Май",
        6: "Июнь",
        7: "Июль",
        8: "Август",
        9: "Сентябрь",
        10: "Октябрь",
        11: "Ноябрь",
        12: "Декабрь",
    }

    result = []
    for month_num, month_name in months.items():
        count = next((c for m, c in monthly_data if m == month_num), 0)
        result.append({"month": month_num, "month_name": month_name, "count": count})

    total = sum(r["count"] for r in result)

    return {
        "year": year,
        "total": total,
        "months": result,
        "average_per_month": round(total / 12, 2),
    }


@router.get(
    "/yearly-stats",
    response_model=YearlyStatsResponse,
    summary="Статистика по годам",
)
def get_yearly_stats(
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_observer_or_higher),
):
    """
    Статистика по годам

    🔓 Доступно: admin, observer
    """
    yearly_data = (
        db.query(
            extract("year", PassportData.created_at).label("year"),
            func.count(PassportData.id).label("count"),
        )
        .filter(_recognized_passport_clause())
        .group_by(extract("year", PassportData.created_at))
        .order_by("year")
        .all()
    )

    return {
        "years": [{"year": int(y), "count": c} for y, c in yearly_data],
        "total": sum(c for _, c in yearly_data),
    }


@router.get(
    "/gender-by-age",
    response_model=GenderByAgeResponse,
    summary="Пол по возрастным группам",
)
def get_gender_by_age(
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_observer_or_higher),
):
    """
    Соотношение пола по возрастным группам

    🔓 Доступно: admin, observer
    """
    records = (
        _recognized_passports_query(db)
        .filter(_has_value(PassportData.birth_date), _has_value(PassportData.gender))
        .with_entities(PassportData.birth_date, PassportData.gender)
        .all()
    )

    result = {
        "0-18": {"male": 0, "female": 0},
        "19-25": {"male": 0, "female": 0},
        "26-35": {"male": 0, "female": 0},
        "36-45": {"male": 0, "female": 0},
        "46-55": {"male": 0, "female": 0},
        "56-65": {"male": 0, "female": 0},
        "65+": {"male": 0, "female": 0},
    }

    for birth_date, gender in records:
        age = calculate_age_from_birthdate(birth_date)
        if age is None:
            continue

        gender = gender.upper()
        is_male = gender in MALE_GENDERS
        is_female = gender in FEMALE_GENDERS

        if not (is_male or is_female):
            continue

        if age <= 18:
            group = "0-18"
        elif age <= 25:
            group = "19-25"
        elif age <= 35:
            group = "26-35"
        elif age <= 45:
            group = "36-45"
        elif age <= 55:
            group = "46-55"
        elif age <= 65:
            group = "56-65"
        else:
            group = "65+"

        if is_male:
            result[group]["male"] += 1
        else:
            result[group]["female"] += 1

    return result


@router.get(
    "/daily-breakdown",
    response_model=DailyBreakdownResponse,
    summary="Поступления по дням",
)
def get_daily_breakdown(
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_observer_or_higher),
    days: int = Query(30, description="Количество дней"),
):
    """
    Поступления по дням

    🔓 Доступно: admin, observer
    """
    start_date = datetime.now(timezone.utc) - timedelta(days=days)

    daily_data = (
        db.query(
            func.date(PassportData.created_at).label("date"),
            func.count(PassportData.id).label("count"),
        )
        .filter(_recognized_passport_clause())
        .filter(PassportData.created_at >= start_date)
        .group_by(func.date(PassportData.created_at))
        .order_by("date")
        .all()
    )

    return {
        "days": days,
        "data": [{"date": str(d), "count": c} for d, c in daily_data],
        "total": sum(c for _, c in daily_data),
        "average_per_day": round(sum(c for _, c in daily_data) / days, 2),
    }


@router.get(
    "/access-logs",
    response_model=AccessLogsResponse,
    summary="Логи доступа",
    description="Доступно только роли `admin`.",
)
def get_access_logs(
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_observer_or_higher),
    limit: int = Query(100, le=1000),
):
    """
    Логи доступа (только АДМИНИСТРАТОР)

    🔒 Доступно: только admin
    """
    user = token_data.get("user")
    if not user or user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Только администратор может просматривать логи доступа",
        )

    from app.models import AccessLog

    logs = db.query(AccessLog).order_by(AccessLog.created_at.desc()).limit(limit).all()

    return {
        "logs": [
            {
                "id": log.id,
                "user_id": log.user_id,
                "action": log.action,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]
    }


def calculate_age_from_birthdate(birth_date_str: str) -> Optional[int]:
    """
    Рассчитывает возраст из строки DD.MM.YYYY.
    Возвращает None если формат невалиден.
    """
    if not birth_date_str or not birth_date_str.strip():
        return None

    if not validate_date_format(birth_date_str):
        return None

    try:
        parts = birth_date_str.strip().split(".")
        birth_date = datetime(int(parts[2]), int(parts[1]), int(parts[0]))
        now = datetime.now()
        age = (now - birth_date).days // 365
        if age < 0 or age > 150:
            logger.warning(
                "Unrealistic age %d from birth_date '%s'", age, birth_date_str
            )
            return None
        return age
    except (ValueError, IndexError) as e:
        logger.warning("Failed to parse birth_date '%s': %s", birth_date_str, e)
        return None

    if not validate_date_format(birth_date_str):
        return None

    try:
        parts = birth_date_str.strip().split(".")
        birth_date = datetime(int(parts[2]), int(parts[1]), int(parts[0]))
        now = datetime.now(timezone.utc)
        age = (now - birth_date).days // 365
        if age < 0 or age > 150:
            logger.warning(
                "Unrealistic age %d from birth_date '%s'", age, birth_date_str
            )
            return None
        return age
    except (ValueError, IndexError) as e:
        logger.warning("Failed to parse birth_date '%s': %s", birth_date_str, e)
        return None


def calculate_average_age(query) -> float:
    """
    Считает средний возраст только по валидным датам рождения.
    Логирует пропущенные записи.
    """
    records = (
        query.filter(_has_value(PassportData.birth_date))
        .with_entities(PassportData.birth_date)
        .all()
    )

    ages = []
    skipped = 0
    for (birth_date,) in records:
        age = calculate_age_from_birthdate(birth_date)
        if age is not None:
            ages.append(age)
        else:
            skipped += 1

    if skipped > 0:
        logger.info(
            "calculate_average_age: %d valid, %d skipped (invalid dates)",
            len(ages),
            skipped,
        )

    return sum(ages) / len(ages) if ages else 0


@router.get("/billing/usage")
def get_usage(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    token_data: dict = Depends(decode_dashboard_token),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    records = (
        db.query(
            UsageRecord.action,
            func.count(UsageRecord.id).label("count"),
            func.avg(UsageRecord.confidence).label("avg_confidence"),
            func.sum(UsageRecord.processing_time_ms).label("total_time_ms"),
        )
        .filter(UsageRecord.created_at >= since)
        .group_by(UsageRecord.action)
        .all()
    )
    return [
        {
            "action": r.action,
            "count": r.count,
            "avg_confidence": round(float(r.avg_confidence), 3)
            if r.avg_confidence
            else 0,
            "total_time_ms": int(r.total_time_ms) if r.total_time_ms else 0,
        }
        for r in records
    ]


@router.get("/billing/api-keys/{key_id}/usage")
def get_api_key_usage(
    key_id: int,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    token_data: dict = Depends(decode_dashboard_token),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    key = db.query(APIKey).filter(APIKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")

    daily = (
        db.query(
            func.date(UsageRecord.created_at).label("date"),
            func.count(UsageRecord.id).label("count"),
        )
        .filter(UsageRecord.api_key_id == key_id, UsageRecord.created_at >= since)
        .group_by(func.date(UsageRecord.created_at))
        .order_by(func.date(UsageRecord.created_at))
        .all()
    )
    return {
        "key_id": key_id,
        "key_prefix": key.key_prefix,
        "name": key.name,
        "daily_usage": key.daily_usage,
        "rate_limit_per_minute": key.rate_limit_per_minute,
        "rate_limit_per_day": key.rate_limit_per_day,
        "daily_breakdown": [{"date": str(d.date), "count": d.count} for d in daily],
    }
