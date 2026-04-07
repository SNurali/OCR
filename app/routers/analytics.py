from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from sqlalchemy import and_, extract, func, or_
from sqlalchemy.orm import Session

from app.auth import decode_dashboard_token, optional_oauth2_scheme
from app.database import get_db
from app.models import PassportData, DashboardUser
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
from app.services import analytics_service

router = APIRouter()

MALE_GENDERS = ["M", "MALE", "МУЖ", "ERKAK"]
FEMALE_GENDERS = ["F", "FEMALE", "ЖЕН", "AYOL"]


def _has_value(column):
    return and_(column.isnot(None), column != "")


def _recognized_passport_clause():
    return or_(
        PassportData.mrz_valid.is_(True),
        _has_value(PassportData.passport_number),
        _has_value(PassportData.birth_date),
        _has_value(PassportData.pinfl),
        _has_value(PassportData.issue_date),
        _has_value(PassportData.expiry_date),
        and_(_has_value(PassportData.gender), _has_value(PassportData.nationality)),
    )


def _recognized_passports_query(
    db: Session, filters: Optional["AnalyticsFilter"] = None
):
    query = db.query(PassportData).filter(_recognized_passport_clause())

    if filters:
        if filters.start_date:
            try:
                start = datetime.strptime(filters.start_date, "%Y-%m-%d")
                query = query.filter(PassportData.created_at >= start)
            except ValueError:
                pass

        if filters.end_date:
            try:
                # Add 1 day to include the whole end_date
                end = datetime.strptime(filters.end_date, "%Y-%m-%d") + timedelta(
                    days=1
                )
                query = query.filter(PassportData.created_at < end)
            except ValueError:
                pass

        if filters.citizenship == "local":
            query = query.filter(
                func.upper(PassportData.nationality).in_(["UZB", "O'ZBEKISTON"])
            )
        elif filters.citizenship == "foreign":
            query = query.filter(
                ~func.upper(PassportData.nationality).in_(["UZB", "O'ZBEKISTON"])
            )

        if filters.gender == "male":
            query = query.filter(func.upper(PassportData.gender).in_(MALE_GENDERS))
        elif filters.gender == "female":
            query = query.filter(func.upper(PassportData.gender).in_(FEMALE_GENDERS))

    return query


def _count_by_gender(query, genders: list[str]) -> int:
    return query.filter(func.upper(PassportData.gender).in_(genders)).count()


class AnalyticsFilter:
    def __init__(
        self,
        start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
        end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
        citizenship: Optional[str] = Query("all", description="all, local, foreign"),
        gender: Optional[str] = Query("all", description="all, male, female"),
    ):
        self.start_date = start_date
        self.end_date = end_date
        self.citizenship = citizenship
        self.gender = gender


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
        "только загрузки, где OCR распознал паспортные поля. `total_uploads` содержит "
        "все загруженные файлы."
    ),
)
def get_summary(
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_observer_or_higher),
    filters: "AnalyticsFilter" = Depends(),
):
    """
    Общая сводка по всем паспортам

    🔓 Доступно: admin, observer
    """
    # Total uploads should probably respect date filters but NOT citizenship/gender,
    # since unrecognized means no citizenship/gender found. We'll filter date only for totals.
    base_uploads_query = db.query(PassportData)
    if filters.start_date:
        try:
            start = datetime.strptime(filters.start_date, "%Y-%m-%d")
            base_uploads_query = base_uploads_query.filter(
                PassportData.created_at >= start
            )
        except ValueError:
            pass
    if filters.end_date:
        try:
            end = datetime.strptime(filters.end_date, "%Y-%m-%d") + timedelta(days=1)
            base_uploads_query = base_uploads_query.filter(
                PassportData.created_at < end
            )
        except ValueError:
            pass

    total_uploads = base_uploads_query.count()

    recognized_query = _recognized_passports_query(db, filters)
    total = recognized_query.count()
    male_count = _count_by_gender(
        _recognized_passports_query(db, filters), MALE_GENDERS
    )
    female_count = _count_by_gender(
        _recognized_passports_query(db, filters), FEMALE_GENDERS
    )
    avg_age = calculate_average_age(_recognized_passports_query(db, filters))

    # Calculate average confidence
    avg_conf = (
        db.query(func.avg(PassportData.confidence))
        .filter(PassportData.id.in_(recognized_query.with_entities(PassportData.id)))
        .scalar()
    )
    avg_conf = avg_conf if avg_conf else 0.0

    return {
        "total_passports": total,
        "total_uploads": total_uploads,
        "unrecognized_uploads": max(total_uploads - total, 0),
        "male_count": male_count,
        "female_count": female_count,
        "male_percent": round(male_count / total * 100, 2) if total else 0,
        "female_percent": round(female_count / total * 100, 2) if total else 0,
        "average_age": round(avg_age, 1) if avg_age else 0,
        "average_confidence": round(avg_conf, 4),
    }


@router.get(
    "/gender-report",
    response_model=GenderReportResponse,
    summary="Отчет по полу",
)
def get_gender_report(
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_observer_or_higher),
    filters: "AnalyticsFilter" = Depends(),
):
    """
    Отчет по полу: кто больше - мужчин или женщин

    🔓 Доступно: admin, observer
    """
    base_query = _recognized_passports_query(db, filters)
    total = base_query.count()
    male_count = _count_by_gender(
        _recognized_passports_query(db, filters), MALE_GENDERS
    )
    female_count = _count_by_gender(
        _recognized_passports_query(db, filters), FEMALE_GENDERS
    )

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
    filters: "AnalyticsFilter" = Depends(),
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
        _recognized_passports_query(db, filters)
        .filter(_has_value(PassportData.birth_date))
        .with_entities(PassportData.birth_date)
        .all()
    )

    for (birth_date,) in records:
        age = calculate_age_from_birthdate(birth_date)
        if age is None:
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

    total = sum(age_groups.values())

    return {
        "total": total,
        "groups": age_groups,
        "percentages": {
            k: round(v / total * 100, 2) if total else 0 for k, v in age_groups.items()
        },
        "average_age": calculate_average_age(_recognized_passports_query(db, filters)),
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
    filters: "AnalyticsFilter" = Depends(),
):
    """
    Отчет по гражданству/национальности

    🔓 Доступно: admin, observer
    """
    base_query = _recognized_passports_query(db, filters).filter(
        _has_value(PassportData.nationality)
    )

    results = (
        db.query(PassportData.nationality, func.count(PassportData.id).label("count"))
        .filter(PassportData.id.in_(base_query.with_entities(PassportData.id)))
        .group_by(PassportData.nationality)
        .order_by(func.count(PassportData.id).desc())
        .limit(limit)
        .all()
    )

    total = base_query.count()

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
    filters: "AnalyticsFilter" = Depends(),
):
    """
    Отчет по времени: поступления за период

    🔓 Доступно: admin, observer
    """
    now = datetime.utcnow()

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
        _recognized_passports_query(db, filters)
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
    filters: "AnalyticsFilter" = Depends(),
):
    """
    Статистика по месяцам за год

    🔓 Доступно: admin, observer
    """
    if not year:
        year = datetime.utcnow().year

    base_query = _recognized_passports_query(db, filters).filter(
        extract("year", PassportData.created_at) == year
    )

    monthly_data = (
        db.query(
            extract("month", PassportData.created_at).label("month"),
            func.count(PassportData.id).label("count"),
        )
        .filter(PassportData.id.in_(base_query.with_entities(PassportData.id)))
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
    filters: "AnalyticsFilter" = Depends(),
):
    """
    Статистика по годам

    🔓 Доступно: admin, observer
    """
    base_query = _recognized_passports_query(db, filters)

    yearly_data = (
        db.query(
            extract("year", PassportData.created_at).label("year"),
            func.count(PassportData.id).label("count"),
        )
        .filter(PassportData.id.in_(base_query.with_entities(PassportData.id)))
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
    filters: "AnalyticsFilter" = Depends(),
):
    """
    Соотношение пола по возрастным группам

    🔓 Доступно: admin, observer
    """
    records = (
        _recognized_passports_query(db, filters)
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
    filters: "AnalyticsFilter" = Depends(),
):
    """
    Поступления по дням

    🔓 Доступно: admin, observer
    """
    start_date = datetime.utcnow() - timedelta(days=days)

    base_query = _recognized_passports_query(db, filters).filter(
        PassportData.created_at >= start_date
    )

    daily_data = (
        db.query(
            func.date(PassportData.created_at).label("date"),
            func.count(PassportData.id).label("count"),
        )
        .filter(PassportData.id.in_(base_query.with_entities(PassportData.id)))
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


@router.get(
    "/full-analytics",
    summary="Полная аналитика одним запросом",
    description="Возвращает все метрики: по гражданству, полу, возрасту, уверенности, временным рядам.",
)
def get_full_analytics(
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_observer_or_higher),
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    citizenship: Optional[str] = Query(None, description="UZ, RU, KZ и т.д."),
    gender: Optional[str] = Query(None, description="M, F"),
    age_group: Optional[str] = Query(None, description="18-25, 26-35 и т.д."),
    min_confidence: Optional[float] = Query(None, ge=0, le=100),
    is_foreigner: Optional[bool] = Query(
        None, description="true=иностранцы, false=местные"
    ),
    time_group_by: str = Query("month", description="day, week, month, year"),
):
    """
    Полная аналитика одним запросом с фильтрами

    🔓 Доступно: admin, observer
    """
    sd = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
    ed = (
        (datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1))
        if end_date
        else None
    )

    return analytics_service.get_full_analytics(
        db=db,
        start_date=sd,
        end_date=ed,
        citizenship=citizenship if citizenship and citizenship != "all" else None,
        gender=gender if gender and gender != "all" else None,
        age_group=age_group if age_group and age_group != "all" else None,
        min_confidence=min_confidence,
        is_foreigner=is_foreigner,
        time_group_by=time_group_by,
    )


@router.get("/by-user", summary="Статистика по пользователям")
def get_by_user(
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_observer_or_higher),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    sd = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
    ed = (
        datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        if end_date
        else None
    )
    return analytics_service.get_by_user(db, start_date=sd, end_date=ed)


@router.get("/accuracy-detail", summary="Детальная точность по полям")
def get_accuracy_detail(
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_observer_or_higher),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    citizenship: Optional[str] = Query(None),
    is_foreigner: Optional[bool] = Query(None),
):
    sd = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
    ed = (
        datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        if end_date
        else None
    )
    return analytics_service.get_accuracy_detail(
        db,
        start_date=sd,
        end_date=ed,
        citizenship=citizenship,
        is_foreigner=is_foreigner,
    )


@router.get("/records", summary="Список записей с пагинацией")
def get_records(
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_observer_or_higher),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    citizenship: Optional[str] = Query(None),
    gender: Optional[str] = Query(None),
    is_foreigner: Optional[bool] = Query(None),
    recognition_status: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="Поиск по ФИО или номеру паспорта"),
):
    sd = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
    ed = (
        datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        if end_date
        else None
    )

    result = analytics_service.get_passport_records(
        db,
        page=page,
        per_page=per_page,
        start_date=sd,
        end_date=ed,
        citizenship=citizenship,
        gender=gender,
        is_foreigner=is_foreigner,
        recognition_status=recognition_status,
    )

    if search:
        s = search.lower()
        result["items"] = [
            r
            for r in result["items"]
            if s in (r.get("last_name") or "").lower()
            or s in (r.get("first_name") or "").lower()
            or s in (r.get("passport_number") or "").lower()
            or s in (r.get("pinfl") or "").lower()
        ]
        result["total"] = len(result["items"])

    return result


@router.get("/records/{record_id}", summary="Детальная карточка записи")
def get_record_detail(
    record_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_observer_or_higher),
):
    detail = analytics_service.get_passport_detail(db, record_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    return detail


@router.get("/compare-periods", summary="Сравнение двух периодов")
def compare_periods(
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_observer_or_higher),
    start_1: str = Query(..., description="YYYY-MM-DD"),
    end_1: str = Query(..., description="YYYY-MM-DD"),
    start_2: str = Query(..., description="YYYY-MM-DD"),
    end_2: str = Query(..., description="YYYY-MM-DD"),
):
    return analytics_service.compare_periods(
        db,
        datetime.strptime(start_1, "%Y-%m-%d"),
        datetime.strptime(end_1, "%Y-%m-%d") + timedelta(days=1),
        datetime.strptime(start_2, "%Y-%m-%d"),
        datetime.strptime(end_2, "%Y-%m-%d") + timedelta(days=1),
    )


@router.get("/export/csv", summary="Экспорт в CSV")
def export_csv(
    db: Session = Depends(get_db),
    token_data: dict = Depends(require_observer_or_higher),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    citizenship: Optional[str] = Query(None),
    gender: Optional[str] = Query(None),
    is_foreigner: Optional[bool] = Query(None),
):
    sd = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
    ed = (
        datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        if end_date
        else None
    )

    csv_content = analytics_service.export_to_csv(
        db,
        start_date=sd,
        end_date=ed,
        citizenship=citizenship,
        gender=gender,
        is_foreigner=is_foreigner,
    )

    from fastapi.responses import Response

    return Response(
        content=csv_content.encode("utf-8"),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ocr_export.csv"},
    )


def calculate_age_from_birthdate(birth_date_str: str) -> Optional[int]:
    if not birth_date_str:
        return None
    try:
        birth_date = datetime.strptime(birth_date_str, "%d.%m.%Y")
        return (datetime.utcnow() - birth_date).days // 365
    except:
        return None


def calculate_average_age(query) -> float:
    records = (
        query.filter(_has_value(PassportData.birth_date))
        .with_entities(PassportData.birth_date)
        .all()
    )

    ages = []
    for (birth_date,) in records:
        age = calculate_age_from_birthdate(birth_date)
        if age:
            ages.append(age)

    return sum(ages) / len(ages) if ages else 0
