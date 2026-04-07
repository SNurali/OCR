import re

import numpy as np

from app.services.extractor import (
    extract_dates,
    extract_gender,
    extract_issued_by,
    extract_names,
    extract_nationality,
    extract_passport_number,
    extract_pinfl,
)
from app.services.name_lexicons import COMMON_FIRST_NAMES
from app.services.name_lexicons.patronymics import COMMON_PATRONYMICS
from app.services.mrz_parser import mrz_parser
from app.services.ocr_service import ocr_pipeline
from app.services.preprocessing import preprocess_image
from app.services.validator import validator


def _split_given_names(value: str) -> tuple[str, str]:
    parts = [part for part in value.split() if part]
    if not parts:
        return "", ""
    return parts[0], " ".join(parts[1:])


def _recover_name_from_raw(raw_text: str, mrz_fragment: str) -> str:
    """Если MRZ дал обрезанное имя, пробуем найти полное в сыром OCR тексте или словаре."""
    if not mrz_fragment or len(mrz_fragment) < 3:
        return mrz_fragment

    mrz_clean = mrz_fragment.upper().replace("<", " ").strip()
    if len(mrz_clean) < 3:
        return mrz_fragment

    # 1. Ищем полное имя в сыром OCR тексте (по префиксу)
    text_candidate = None
    for line in raw_text.split("\n"):
        tokens = re.split(r"[ <0-9]+", line.upper())
        tokens = [t for t in tokens if len(t) >= 3 and re.match(r"^[A-ZА-ЯЁ]+$", t)]
        for token in tokens:
            if token.startswith(mrz_clean) and len(token) > len(mrz_clean):
                # Если токен слишком длинный и содержит другие известные элементы (напр. филия+имя)
                # или просто значительно длиннее (> 4 символа при общей длине > 5), пропускаем
                if len(mrz_clean) > 5 and (len(token) - len(mrz_clean)) > 4:
                    if token not in COMMON_FIRST_NAMES:
                        continue

                if token in COMMON_FIRST_NAMES:
                    return token
                if text_candidate is None:
                    text_candidate = token

    # 2. Ищем в словаре имён: полное имя начинается с mrz_clean
    #    (для случаев NUR -> NURALI, когда OCR обрезал конец)
    if len(mrz_clean) >= 3:
        for name in sorted(COMMON_FIRST_NAMES, key=len):
            if name.startswith(mrz_clean) and len(name) > len(mrz_clean):
                return name

    # 3. Fallback: возвращаем лучший кандидат из текста (если нашли)
    if text_candidate is not None:
        return text_candidate

    return mrz_fragment


def _find_patronymic_in_raw(raw_text: str) -> str:
    """Ищем отчество в сыром OCR тексте по суффиксу -OVICH/-EVICH или в словаре.
    Если отчество обрезано или склеено с мусором (SHAMIRJONOVICH),
    используем рейтинговую систему для выбора лучшего словарного слова.
    """
    candidates = []

    for line in raw_text.split("\n"):
        tokens = re.split(r"[ <0-9/\"']+", line.upper())
        tokens = [t for t in tokens if len(t) >= 5 and re.match(r"^[A-ZА-ЯЁ]+$", t)]
        for token in tokens:
            # 1. Exact match (highest priority)
            if token in COMMON_PATRONYMICS:
                candidates.append((token, 100))
                continue

            # 2. Token contains known patronymic as substring (noise at edges, e.g. "SHAMIRJONOVICH")
            best_sub = None
            for patronymic in sorted(COMMON_PATRONYMICS, key=len, reverse=True):
                if patronymic in token:
                    best_sub = patronymic
                    break

            if best_sub:
                candidates.append((best_sub, 90))
                continue

            # 3. Token is prefix of known patronymic (truncated by OCR)
            best_prefix = None
            for patronymic in sorted(COMMON_PATRONYMICS, key=len, reverse=True):
                if patronymic.startswith(token) and len(patronymic) > len(token):
                    best_prefix = patronymic
                    break

            if best_prefix:
                candidates.append((best_prefix, 80))
                continue

            # 4. Unknown but ends with patronymic suffix (fallback)
            if any(token.endswith(s) for s in ("OVICH", "EVICH", "OVIC", "EVIC")):
                candidates.append((token, 50))
                continue

            # 5. Fuzzy match via rapidfuzz — для OCR-ошибок типа AMIRIONC → AMIRJONOVICH
            if len(token) >= 6:
                try:
                    from rapidfuzz import fuzz

                    best_fuzzy = None
                    best_score = 0
                    for patronymic in COMMON_PATRONYMICS:
                        score = fuzz.ratio(token, patronymic)
                        if score > best_score and score >= 60:
                            best_score = score
                            best_fuzzy = patronymic
                    if best_fuzzy:
                        candidates.append((best_fuzzy, 60 + best_score // 10))
                except ImportError:
                    pass

    if candidates:
        # Sort by score descending and return the best
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    return ""


def _mrz_pinfl(mrz_data: dict) -> str:
    """Возвращает ПИНФЛ из MRZ только если ровно 14 цифр."""
    personal_number = str(mrz_data.get("personal_number") or "")
    digits_only = re.sub(r"\D", "", personal_number)
    return digits_only if len(digits_only) == 14 else ""


def _mrz_pinfl_raw(mrz_data: dict) -> str:
    """Возвращает сырой ПИНФЛ из MRZ (даже если не 14 цифр) для коррекции."""
    personal_number = str(mrz_data.get("personal_number") or "")
    digits_only = re.sub(r"\D", "", personal_number)
    if 10 <= len(digits_only) <= 14:
        return digits_only
    return ""


def extract_document_data(raw_text: str, mrz_data: dict | None = None) -> dict:
    mrz_data = mrz_data or {}

    names = extract_names(raw_text)
    dates = extract_dates(raw_text)
    mrz_first_name, mrz_middle_name = _split_given_names(
        str(mrz_data.get("given_names") or "")
    )

    # MRZ - приоритетный источник для имени и фамилии (даже при частичном парсинге)
    mrz_surname = str(mrz_data.get("surname") or "")
    mrz_valid = mrz_data.get("all_checks_valid") or mrz_data.get("valid")
    mrz_partial = mrz_data.get("partial", False)

    # Логирование для отладки
    import logging

    logger = logging.getLogger(__name__)
    logger.info(f"MRZ data: {mrz_data}")
    logger.info(
        f"MRZ valid: {mrz_valid}, partial: {mrz_partial}, surname: {mrz_surname}, first_name: {mrz_first_name}"
    )
    logger.info(f"Extracted names: {names}")

    # Определяем, какие данные использовать для имени
    # Приоритет: MRZ (если валидный или есть данные) > извлечение из текста
    use_mrz = (mrz_valid or mrz_partial) and mrz_first_name and len(mrz_first_name) >= 3
    if use_mrz:
        first_name = _recover_name_from_raw(raw_text, mrz_first_name)
        logger.info(f"Using MRZ first_name: {first_name}")
    else:
        first_name = names.get("first_name") or mrz_first_name
        # Fallback: ищем имя NURALI по словарю если MRZ не дал
        if not first_name:
            for line in raw_text.split("\n"):
                tokens = re.split(r"[ <0-9/]+", line.upper())
                tokens = [
                    t for t in tokens if len(t) >= 3 and re.match(r"^[A-ZА-ЯЁ]+$", t)
                ]
                for token in tokens:
                    if token in COMMON_FIRST_NAMES:
                        first_name = token
                        break
                if first_name:
                    break
        logger.info(f"Using extracted first_name: {first_name}")

    # Для фамилии тоже приоритет MRZ
    # Но проверяем что MRZ surname выглядит как имя (только буквы)
    mrz_surname_valid = bool(
        mrz_surname and re.match(r"^[A-Z\s]+$", mrz_surname, re.IGNORECASE)
    )
    use_mrz_surname = (
        (mrz_valid or mrz_partial) and mrz_surname_valid and len(mrz_surname) >= 3
    )
    if use_mrz_surname:
        last_name = _recover_name_from_raw(raw_text, mrz_surname)
        # Убираем пробелы из фамилии (OCR часто разбивает SULAYMANOV → SULA YMANOV)
        if last_name and " " in last_name:
            last_name_no_spaces = last_name.replace(" ", "")
            if len(last_name_no_spaces) >= 5:
                last_name = last_name_no_spaces
        logger.info(f"Using MRZ last_name: {last_name}")
    else:
        last_name = names.get("last_name") or mrz_surname
        logger.info(f"Using extracted last_name: {last_name}")

    # Отчество: сначала ищем по патронимному суффиксу в сыром тексте,
    # потом пробуем восстановить из MRZ, потом берём из extract_names
    raw_patronymic = _find_patronymic_in_raw(raw_text)
    if raw_patronymic:
        middle_name = raw_patronymic
    else:
        mrz_middle_raw = str(mrz_data.get("given_names") or "")
        _, mrz_middle_from_given = _split_given_names(mrz_middle_raw)

        extracted_middle = names.get("middle_name")
        # Если MRZ дал отчество, пробуем восстановить, иначе берем extraction
        if mrz_middle_from_given:
            middle_name = _recover_name_from_raw(raw_text, mrz_middle_from_given)
        else:
            middle_name = extracted_middle if extracted_middle else ""

    # Извлекаем даты с улучшенной функцией
    extracted_dates = extract_dates(raw_text)

    # Корректируем birth_date по MRZ если есть
    mrz_birth = str(mrz_data.get("birth_date") or "")
    if mrz_birth and len(mrz_birth) >= 8:  # YYYY-MM-DD
        try:
            from datetime import datetime

            mrz_birth_dt = datetime.strptime(mrz_birth, "%Y-%m-%d")
            mrz_birth_str = mrz_birth_dt.strftime("%d.%m.%Y")
            visual_birth = extracted_dates.get("birth_date", "")
            # Если визуальная дата отличается от MRZ — берём MRZ
            if visual_birth and mrz_birth_str != visual_birth:
                # Проверяем что MRZ дата логична (возраст 0-150 лет)
                from app.services.validator import validator

                if validator.validate_birth_date(mrz_birth_str):
                    extracted_dates["birth_date"] = mrz_birth_str
        except (ValueError, TypeError):
            pass

    # Используем извлеченные даты
    issue_date = extracted_dates.get("issue_date")
    expiry_date = extracted_dates.get("expiry_date") or str(
        mrz_data.get("expiry_date") or ""
    )

    # Исправляем OCR-ошибки в expiry_date: если issue + 10 лет близко к expiry,
    # но день/месяец отличаются на 1 — берём issue + 10 лет - 1 день
    if issue_date and expiry_date:
        try:
            from datetime import datetime, timedelta

            issue_dt = datetime.strptime(issue_date, "%d.%m.%Y")
            expiry_dt = datetime.strptime(expiry_date, "%d.%m.%Y")
            expected_expiry = issue_dt + timedelta(days=3652)  # ~10 лет
            if abs((expiry_dt - expected_expiry).days) <= 31:
                # Близко к 10 годам — корректируем
                corrected = issue_dt.replace(year=issue_dt.year + 10) - timedelta(
                    days=1
                )
                expiry_date = corrected.strftime("%d.%m.%Y")
        except (ValueError, TypeError):
            pass

    # Если дата выдачи в формате DD.MM.YY (2-значный год), попробуем восстановить 4-значный год
    # используя контекст даты рождения и MRZ данных
    if issue_date and len(issue_date) == 8 and issue_date[6:].isdigit():  # DD.MM.YY
        day_month = issue_date[:5]
        year_2digit = issue_date[6:]
        year_int = int(year_2digit)

        # Используем дату рождения для логического определения года выдачи
        birth_date = extracted_dates.get("birth_date") or str(
            mrz_data.get("birth_date") or ""
        )
        if birth_date and len(birth_date) >= 10:  # формат DD.MM.YYYY
            try:
                birth_parts = birth_date.split(".")
                if len(birth_parts) == 3:
                    birth_year = int(birth_parts[2])
                    # Паспорт обычно выдается после достижения 16 лет
                    min_issue_year = birth_year + 16

                    # Определяем полный год
                    if year_int <= 30:  # предполагаем 20XX
                        full_year = 2000 + year_int
                    else:  # предполагаем 19XX
                        full_year = 1900 + year_int

                    # Проверяем, что год выдачи логически возможен
                    if min_issue_year <= full_year <= 2026:  # текущий год
                        issue_date = f"{day_month}{full_year}"
            except (ValueError, IndexError):
                pass  # Если не удалось обработать, оставляем как есть

    # Если срок действия в формате DD.MM.YY, также попробуем восстановить 4-значный год
    if expiry_date and len(expiry_date) == 8 and expiry_date[6:].isdigit():  # DD.MM.YY
        day_month = expiry_date[:5]
        year_2digit = expiry_date[6:]
        year_int = int(year_2digit)

        # Срок действия обычно в будущем
        from datetime import datetime

        current_year = datetime.now().year

        # Определяем полный год
        if year_int <= 30:  # предполагаем 20XX
            full_year = 2000 + year_int
        else:  # предполагаем 19XX
            full_year = 1900 + year_int

        # Если год в прошлом, но близок к текущему году, возможно, это ошибка OCR
        # и на самом деле это будущий год
        if full_year < current_year:
            # Попробуем интерпретировать как будущий год
            if year_int <= 30:
                full_year = 2000 + year_int
            else:
                full_year = 2000 + year_int  # Если год больше 30, это, вероятно, ошибка

        expiry_date = f"{day_month}{full_year}"

    def _parse_date_safe(ds: str):
        if not ds:
            return None
        try:
            from datetime import datetime

            for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
                try:
                    return datetime.strptime(ds, fmt)
                except ValueError:
                    continue
        except Exception:
            pass
        return None

    issue_dt = _parse_date_safe(issue_date) if issue_date else None
    expiry_dt = _parse_date_safe(expiry_date) if expiry_date else None

    if issue_dt and expiry_dt and expiry_dt <= issue_dt:
        expiry_date = ""

    extracted = {
        "first_name": first_name,
        "last_name": last_name,
        "middle_name": middle_name,
        "birth_date": extracted_dates.get("birth_date")
        or str(mrz_data.get("birth_date") or ""),
        "gender": extract_gender(raw_text) or str(mrz_data.get("gender") or ""),
        "nationality": extract_nationality(raw_text)
        or str(mrz_data.get("nationality") or ""),
        "passport_number": str(mrz_data.get("passport_number") or "")
        or extract_passport_number(raw_text)
        or "",
        "issue_date": issue_date or "",
        "expiry_date": expiry_date or "",
        "issued_by": extract_issued_by(raw_text) or "",
        "pinfl": _mrz_pinfl(mrz_data)
        or extract_pinfl(raw_text, _mrz_pinfl_raw(mrz_data))
        or "",
    }

    extracted["passport_series"] = (
        extracted["passport_number"][:2]
        if len(extracted["passport_number"]) >= 2
        else ""
    )

    return extracted


def analyze_passport_image(image: np.ndarray) -> dict:
    preprocessed = preprocess_image(image)
    ocr_result = ocr_pipeline.ocr_full(preprocessed["full"])

    mrz_text = ocr_result.get("mrz") or ocr_result.get("text") or ""
    mrz_lines, mrz_parsed = mrz_parser.extract_from_text(mrz_text)
    mrz_parsed = mrz_parsed or {}
    mrz_valid = bool(mrz_parsed.get("all_checks_valid") or mrz_parsed.get("valid"))

    extracted = extract_document_data(ocr_result.get("text") or "", mrz_parsed)
    validation = validator.validate(
        extracted,
        mrz_parsed,
    )

    return {
        "preprocessed": preprocessed,
        "ocr_result": ocr_result,
        "mrz_text": mrz_text,
        "mrz_lines": mrz_lines,
        "mrz_parsed": mrz_parsed,
        "mrz_valid": mrz_valid,
        "raw_text": ocr_result.get("text", ""),
        "extracted": validation.pop("normalized_data", extracted),
        "validation": validation,
    }
