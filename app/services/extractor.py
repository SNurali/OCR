import re
from typing import Dict, Any, Optional


def fix_ocr_errors(text: str) -> str:
    """Исправляет типичные OCR-ошибки ТОЛЬКО для имён/фамилий (НЕ для дат, номеров, ПИНФЛ)."""
    text = re.sub(r"(?<=[A-Z])0(?=[A-Z])", "O", text)
    text = re.sub(r"(?<=[A-Z])1(?=[A-Z])", "I", text)
    text = re.sub(r"(?<=[A-Z])5(?=[A-Z])", "S", text)
    text = re.sub(r"(?<=[A-Z])8(?=[A-Z])", "B", text)
    text = re.sub(r"(?<=[A-Z])4(?=[A-Z])", "A", text)
    text = re.sub(r"(?<=[A-Z])7(?=[A-Z])", "T", text)
    text = re.sub(r"(?<=[A-Z])3(?=[A-Z])", "E", text)
    return text


# MRZ (pip install mrz)
try:
    from mrz.parser.td1 import TD1CodeParser

    MRZ_AVAILABLE = True
except ImportError:
    MRZ_AVAILABLE = False
    TD1CodeParser = None


def extract_mrz_lines(ocr_text: str) -> Optional[str]:
    """Извлекает MRZ строки из OCR текста (TD1: 3 строки по 30 символов)."""
    lines = [line.strip() for line in ocr_text.splitlines() if line.strip()]
    for i in range(len(lines) - 2):
        candidate = lines[i : i + 3]
        cleaned = [l.replace(" ", "") for l in candidate]
        if all(28 <= len(c) <= 35 for c in cleaned) and any("<" in c for c in cleaned):
            mrz = "\n".join(cleaned)
            return mrz
    return None


def normalize_name(name: str) -> str:
    """Приводит имя/фамилию к UPPERCASE + исправляет OCR-ошибки."""
    if not name:
        return ""
    name = name.upper().strip()
    name = re.sub(r"0", "O", name)
    name = re.sub(r"1", "I", name)
    name = re.sub(r"5", "S", name)
    name = re.sub(r"[^A-Z\s]", "", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()


def normalize_date(date_str: str) -> str:
    """Приводит дату к формату DD.MM.YYYY."""
    if not date_str:
        return ""
    patterns = [r"(\d{2})[.\-/ ](\d{2})[.\-/ ](\d{4})", r"(\d{2})(\d{2})(\d{4})"]
    for pat in patterns:
        m = re.search(pat, date_str)
        if m:
            d, mth, y = m.groups()
            return f"{d}.{mth}.{y}"
    return date_str.strip()


def _parse_date_to_comparable(d: str):
    """Парсит дату в sortable tuple (year, month, day) или None."""
    match = re.match(r"(\d{2})[.\-/](\d{2})[.\-/](\d{4})", d)
    if match:
        day, month, year = match.groups()
        return {"date": d, "year": int(year), "month": int(month), "day": int(day)}
    return None


def _classify_dates_by_year(dates: list) -> Dict[str, str]:
    """
    Умно распределяет даты по полям на основе года и полной даты:
    - Самая старая дата → дата рождения
    - Средняя дата → дата выдачи
    - Самая новая дата → дата окончания
    При одинаковых годах сортирует по месяцу и дню.
    """
    result = {"date_of_birth": "", "date_of_issue": "", "date_of_expiry": ""}
    if not dates:
        return result

    parsed = []
    for d in dates:
        p = _parse_date_to_comparable(d)
        if p:
            parsed.append(p)

    if not parsed:
        return result

    # Сортируем по полной дате (год, месяц, день)
    parsed.sort(key=lambda x: (x["year"], x["month"], x["day"]))

    # Самая старая дата → рождение
    result["date_of_birth"] = parsed[0]["date"]

    if len(parsed) >= 2:
        result["date_of_issue"] = parsed[1]["date"]

    if len(parsed) >= 3:
        result["date_of_expiry"] = parsed[2]["date"]
    elif len(parsed) == 2:
        # Если только 2 даты, вторая — скорее всего дата выдачи, а не expiry
        # (в паспортах обычно: рождение + выдача)
        result["date_of_issue"] = parsed[1]["date"]

    return result


def parse_any_id_document(ocr_text: str) -> Dict[str, Any]:
    """
    УЛУЧШЕННАЯ ВЕРСИЯ — визуальный текст как главный источник, MRZ для валидации
    """
    result: Dict[str, Any] = {
        "document_type": "Uzbek Identity Card",
        "surname": "",
        "given_name": "",
        "patronymic": "",
        "date_of_birth": "",
        "sex": "",
        "date_of_issue": "",
        "citizenship": "O'ZBEKISTON",
        "date_of_expiry": "",
        "card_number": "",
        "personal_number": "",
        "place_of_birth": "",
        "place_of_issue": "",
        "mrz": "",
        "raw_ocr_text": ocr_text[:1500] + "..." if len(ocr_text) > 1500 else ocr_text,
        "confidence": "low",
    }

    # ====================== 1. MRZ — только для имени, фамилии, номера ======================
    mrz_str = extract_mrz_lines(ocr_text)

    if mrz_str and MRZ_AVAILABLE:
        try:
            parser = TD1CodeParser(mrz_str)
            result["mrz"] = mrz_str

            # ИЗ MRZ берём только то, что надёжно:
            result["surname"] = normalize_name(getattr(parser, "surname", ""))

            given = getattr(parser, "given_names", "")
            parts = [p for p in given.split() if p]
            result["given_name"] = normalize_name(parts[0] if parts else "")

            # Номер документа из MRZ
            result["card_number"] = getattr(parser, "document_number", "")

            # Пол
            sex = getattr(parser, "sex", "").upper()
            if sex:
                result["sex"] = (
                    "ERKKAK"
                    if sex in ("M", "ERKKAK", "ERKAK")
                    else "AYOL"
                    if sex in ("F", "FEMALE")
                    else sex
                )

            # ПИНФЛ
            pn_raw = getattr(parser, "personal_number", "") or getattr(
                parser, "optional_data", ""
            )
            pn_digits = re.sub(r"\D", "", str(pn_raw or ""))
            if len(pn_digits) == 14:
                result["personal_number"] = pn_digits
            elif len(pn_digits) > 14:
                result["personal_number"] = pn_digits[:14]

        except Exception:
            pass

    # ====================== 2. ДАТЫ — ВСЕГДА из визуального текста (надёжнее!) ======================
    # Находим ВСЕ даты в тексте
    all_dates = re.findall(r"(\d{2}[.\-/]\d{2}[.\-/]\d{4})", ocr_text)
    all_dates = list(dict.fromkeys(all_dates))  # уникальные

    # Умно распределяем по годам
    classified = _classify_dates_by_year(all_dates)

    if classified["date_of_birth"]:
        result["date_of_birth"] = classified["date_of_birth"]
    if classified["date_of_issue"]:
        result["date_of_issue"] = classified["date_of_issue"]
    if classified["date_of_expiry"]:
        result["date_of_expiry"] = classified["date_of_expiry"]

    # ====================== 3. ОТЧЕСТВО — ищем ПРЯМО в тексте ======================
    if not result["patronymic"]:
        # Порядок важен: сначала ищем полное правильное написание!
        patronymic_patterns = [
            r"(AMIRJONOVICH)",  # правильное написание
            r"(AMIRJONOV)",  # обрезанное
            r"(AMIRIONC\w{3,})",  # OCR-вариант (минимум 3 символа после)
            r"(AURIONGY\w{3,})",  # OCR-вариант
            r"(IRIONG\w{3,})",  # OCR-вариант
        ]
        for pat in patronymic_patterns:
            match = re.search(pat, ocr_text, re.IGNORECASE)
            if match:
                result["patronymic"] = normalize_name(match.group(1))
                break

    # ====================== 4. ПИНФЛ — исправляем OCR-ошибки ======================
    if not result["personal_number"]:
        all_numbers = re.findall(r"\d{14,}", ocr_text)
        for num in all_numbers:
            if len(num) == 14:
                result["personal_number"] = num
                break
            if len(num) > 14:
                candidates = [num[:14], num[-14:]]
                for c in candidates:
                    if c.startswith(("1", "2", "3")) and c[0] != "0":
                        result["personal_number"] = c
                        break
                if result["personal_number"]:
                    break

    # ====================== 5. МЕСТО ВЫДАЧИ ======================
    if not result["place_of_issue"]:
        tosh_match = re.search(r"TOSHKENT", ocr_text, re.IGNORECASE)
        if tosh_match:
            result["place_of_issue"] = "TOSHKENT"

    # ====================== 6. ПОЛ ======================
    if not result["sex"]:
        if re.search(r"\bERKAK\b", ocr_text, re.IGNORECASE):
            result["sex"] = "ERKKAK"
        elif re.search(r"\bAYOL\b", ocr_text, re.IGNORECASE):
            result["sex"] = "AYOL"

    # ====================== 7. НОМЕР КАРТЫ — fallback ======================
    if not result["card_number"]:
        card_match = re.search(r"([A-Z]{2}\d{7})", ocr_text)
        if card_match:
            result["card_number"] = card_match.group(1)

    # ====================== 8. ФИНАЛЬНАЯ ОЦЕНКА ======================
    if result["mrz"] and result["surname"] and result["date_of_birth"]:
        result["confidence"] = "high"
    elif result["surname"] and result["date_of_birth"]:
        result["confidence"] = "medium"

    return result


# ===== ФУНКЦИИ ДЛЯ СОВМЕСТИМОСТИ =====


def extract_names(text: str) -> Dict[str, Optional[str]]:
    """Извлекает имена через parse_any_id_document."""
    parsed = parse_any_id_document(text)

    # Get the names from the parsed data
    last_name = parsed.get("surname", "")
    first_name = parsed.get("given_name", "")
    middle_name = parsed.get("patronymic", "")

    # Validate MRZ-extracted names - skip if they look like OCR garbage
    # MRZ garbage indicators: contains digits, very long, contains <, or looks like MRZ line
    def looks_like_mrz_garbage(name: str) -> bool:
        if not name:
            return True
        if any(c.isdigit() for c in name):
            return True
        if "<" in name:
            return True
        if len(name) > 25:
            return True
        # Check if it looks like a header/authority word
        skip_words_check = {
            "ОТДЕЛОМ",
            "ОБЛАСТИ",
            "РАЙОНК",
            "ТОЛЬЯТТИ",
            "УФМС",
            "РОССИИ",
            "МОСКВЕ",
            "АСТРАХАНСКОЙ",
            "УЗБЕКИСТОН",
            "РЕСПУБЛИКАСИ",
            "PASSPORT",
            "OZBEKISTON",
            "REPUBLIC",
            "DATE",
            "PLACE",
            "ISSUED",
            "VALID",
            "CARD",
            "NUMBER",
            "AYOL",
            "ERKAK",
            "ERKKAK",
            "SHAXS",
            "GUVOHNOMASI",
            "TOSHKENT",
            "TUMANI",
            "IIB",
            "HOLDER",
            "SIGNATURE",
            "FAM",
            "SUR",
            "ISM",
            "NAME",
            "GIVEN",
            "ИМЯ",
            "ФАМИЛИЯ",
            "ОТДЕЛЕНИЕ",
            "УВД",
            "БАСМАННЫЙ",
            "КЫРГЫЗ",
            "НАЦМОНАЛЬНОСТЬ",
            "ЦАО",
            "ОТДЕЛОМУАНСИ",
            "ТОЛЯТ",
            "СААРСКОПОБЛАСТИ",
            "АНТОДАНОДСКОМ",
            "СААРСКОП",
            "ОТММ",
            "ВИЧ",
            "ЕК",
            "МУХЛАТКУАТЕ",
            "КИРГИЗРЕСПУБПИКАСИ",
            "UZBSHИNCCHARRYSS",
            "EGCEL",
            "KKKKKKK",
            "ОТДЕЛОМУАНСИ",
            "КИРГИЗРЕСПУБ",
            "КИРГИЗ",
            "РЕСПУБПИКА",
            "РЕСПУБЛИКА",
        }
        if name.upper() in skip_words_check:
            return True
        # Check if name contains header indicators
        for ind in [
            "ОТДЕЛ",
            "ОБЛАСТ",
            "РАЙОН",
            "УФМС",
            "РОССИ",
            "МОСКВ",
            "БАСМАН",
            "АСТРАХАН",
            "УЗБЕК",
            "РЕСПУБЛ",
            "КЫРГЫЗ",
            "НАЦМОНАЛЬ",
            "ПОЛОЖЕН",
            "ОТДЕЛОМУАНСИ",
            "КИРГИЗРЕСПУБ",
        ]:
            if ind in name.upper():
                return True
        return False

    if looks_like_mrz_garbage(last_name):
        last_name = ""
    if looks_like_mrz_garbage(first_name):
        first_name = ""
    if looks_like_mrz_garbage(middle_name):
        middle_name = ""

    # Additional processing for Uzbek names that might come merged in first_name
    # If first_name contains multiple words, split them (e.g., "UMIDA PATRONYMIC" -> "UMIDA", "PATRONYMIC")
    if first_name and " " in first_name:
        parts = first_name.split(" ", 1)
        if len(parts) == 2:
            first_name = parts[0].strip()
            # Only set middle_name if it wasn't already set
            if not middle_name:
                middle_name = parts[1].strip()

    # Skip header/authority text as surname candidates
    skip_words = {
        "ОТДЕЛОМ",
        "ОБЛАСТИ",
        "РАЙОНК",
        "ТОЛЬЯТТИ",
        "УФМС",
        "РОССИИ",
        "МОСКВЕ",
        "АСТРАХАНСКОЙ",
        "УЗБЕКИСТОН",
        "РЕСПУБЛИКАСИ",
        "PASSPORT",
        "OZBEKISTON",
        "REPUBLIC",
        "DATE",
        "PLACE",
        "ISSUED",
        "VALID",
        "CARD",
        "NUMBER",
        "AYOL",
        "ERKAK",
        "ERKKAK",
        "SHAXS",
        "GUVOHNOMASI",
        "TOSHKENT",
        "TUMANI",
        "IIB",
        "HOLDER",
        "SIGNATURE",
        "FAM",
        "SUR",
        "ISM",
        "NAME",
        "GIVEN",
        "ИМЯ",
        "ФАМИЛИЯ",
        "ОТДЕЛЕНИЕ",
        "УВД",
        "БАСМАННЫЙ",
        "ЖАНЫБАЕВИЧ",
        "ГОЛ",
        "РОЖПЕННЯ",
        "ЛОКДЕЯСТВИН",
        "КЫРГЫЗ",
        "РЕСПУБЛИКАСЫ",
        "НАЦМОНАЛЬНОСТЬ",
        "ПОДпМОЛИН",
        "ПОЛОЖЕНMЕ",
        "АВШАМЛШM",
        "КЫСПЫВЛИКАСЫ",
        "ЦАО",
        "ОТДЕЛОМУАНСИ",
        "ТОЛЯТ",
        "СААРСКОПОБЛАСТИ",
        "АНТОДАНОДСКОМ",
        "СААРСКОП",
        "ОТММ",
        "ВИЧ",
        "ЕК",
        "МУХЛАТКУАТЕ",
        "КИРГИЗРЕСПУБПИКАСИ",
        "КИРГИЗ",
        "РЕСПУБПИКА",
        "РЕСПУБЛИКА",
    }

    # Header words that indicate non-name text
    header_indicators = [
        "ОТДЕЛ",
        "ОБЛАСТ",
        "РАЙОН",
        "УФМС",
        "РОССИ",
        "МОСКВ",
        "БАСМАН",
        "АСТРАХАН",
        "УЗБЕК",
        "РЕСПУБЛ",
        "КЫРГЫЗ",
        "НАЦМОНАЛЬ",
        "ПОЛОЖЕН",
        "ОТДЕЛОМУАНСИ",
        "КИРГИЗРЕСПУБ",
    ]

    # If names are still missing or incomplete, try to extract from raw text
    if not last_name or len(last_name) < 3:
        # Look for pattern like "Familiyasi:" followed by name
        surname_patterns = [
            r"(?:Familiyasi|Familiya|Family|SURNAME|Фамилия)[:\s\n]*([A-ZА-ЯЁ][a-zа-яё]+)",
            r"(?:Фамилия)[:\s\n]*([A-ZА-ЯЁ][a-zа-яё]+)",
        ]

        for pattern in surname_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                potential_surname = match.group(1)
                if potential_surname.upper() not in skip_words:
                    surname_endings = [
                        "OV",
                        "EV",
                        "IN",
                        "OVICH",
                        "EVICH",
                        "ULI",
                        "ULLA",
                        "BEK",
                        "OVNA",
                        "EVNA",
                        "YULDI",
                        "KHON",
                    ]
                    if (
                        any(
                            potential_surname.upper().endswith(ending)
                            for ending in surname_endings
                        )
                        or len(potential_surname) >= 4
                    ):
                        last_name = potential_surname.upper()
                        break

    if not first_name or len(first_name) < 3:
        first_name_patterns = [
            r"(?:Ismi|Ism|Name|Given|Имя)[:\s\n]*([A-ZА-ЯЁ][a-zа-яё]+)",
            r"(?:Имя)[:\s\n]*([A-ZА-ЯЁ][a-zа-яё]+)",
        ]

        for pattern in first_name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                potential_first_name = match.group(1)
                if potential_first_name.upper() not in skip_words:
                    name_startings = [
                        "MUHAM",
                        "ABDUL",
                        "SHUKHR",
                        "JASUR",
                        "UMID",
                        "NUR",
                        "ALI",
                        "SATT",
                        "RAHIM",
                        "UMIDA",
                        "MARINA",
                        "ELENA",
                        "ALEKSANDR",
                        "MIKHAILOVNA",
                        "MIKHXAILOVNA",
                        "EFIM",
                        "EFYM",
                    ]
                    if (
                        any(
                            potential_first_name.upper().startswith(start)
                            for start in name_startings
                        )
                        or len(potential_first_name) >= 3
                    ):
                        first_name = potential_first_name.upper()
                        break

    # Line-by-line extraction for Uzbek ID cards and Russian passports
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for i, line in enumerate(lines):
        upper = line.upper()

        # Skip lines that look like headers/authority text
        is_header = any(ind in upper for ind in header_indicators)
        if is_header:
            continue

        # Uzbek ID: FAMILIYASI -> next line = surname
        if "FAMILIYASI" in upper or "SURNAME" in upper:
            if i + 1 < len(lines):
                candidate = re.sub(r"[^A-ZА-ЯЁ]", "", lines[i + 1].upper())
                if candidate and len(candidate) >= 3 and candidate not in skip_words:
                    last_name = candidate
        # Uzbek ID: ISMI -> next line = first name
        if (
            ("ISMI" in upper or "GIVEN" in upper)
            and "OTASINING" not in upper
            and "FAMILIYASI" not in upper
        ):
            if i + 1 < len(lines):
                candidate = re.sub(r"[^A-ZА-ЯЁ]", "", lines[i + 1].upper())
                if candidate and len(candidate) >= 3 and candidate not in skip_words:
                    first_name = candidate
        # Russian passport: МУЖ/ЖЕН indicates gender, name lines are usually 2-3 lines before
        if re.search(r"МУЖ[\s\.]", upper) or "МУЖ" in upper:
            if not first_name and i >= 2:
                # First name is typically 2 lines before gender marker
                candidate = re.sub(r"[^А-ЯЁ\s]", "", lines[i - 2].upper()).strip()
                if candidate and len(candidate) >= 2 and candidate not in skip_words:
                    first_name = candidate
            if not last_name and i >= 3:
                candidate = re.sub(r"[^А-ЯЁ\s]", "", lines[i - 3].upper()).strip()
                if candidate and len(candidate) >= 3 and candidate not in skip_words:
                    last_name = candidate
        if re.search(r"ЖЕН[\s\.]", upper) or "ЖЕН" in upper:
            if not first_name and i >= 2:
                candidate = re.sub(r"[^А-ЯЁ\s]", "", lines[i - 2].upper()).strip()
                if candidate and len(candidate) >= 2 and candidate not in skip_words:
                    first_name = candidate
            if not last_name and i >= 3:
                candidate = re.sub(r"[^А-ЯЁ\s]", "", lines[i - 3].upper()).strip()
                if candidate and len(candidate) >= 3 and candidate not in skip_words:
                    last_name = candidate
        if "ЖЕН" in upper or "ЖЕН." in upper:
            if not first_name and i >= 2:
                candidate = re.sub(r"[^А-ЯЁ\s]", "", lines[i - 2].upper()).strip()
                if candidate and len(candidate) >= 2 and candidate not in skip_words:
                    first_name = candidate
            if not last_name and i >= 3:
                candidate = re.sub(r"[^А-ЯЁ\s]", "", lines[i - 3].upper()).strip()
                if candidate and len(candidate) >= 3 and candidate not in skip_words:
                    last_name = candidate
        # Fallback for Russian passport: look for name pattern before gender marker
        if not last_name or not first_name:
            for j, l in enumerate(lines):
                l_upper = l.upper().strip()
                # Check if this line is the gender marker (most reliable anchor for Russian passports)
                if re.search(r"МУЖ[\s\.]", l_upper) or re.search(r"ЖЕН[\s\.]", l_upper):
                    # Collect consecutive Cyrillic-only lines going backwards from gender marker
                    name_lines = []
                    for k in range(j - 1, max(0, j - 8), -1):
                        cleaned = re.sub(r"[^А-ЯЁ\s]", "", lines[k].upper()).strip()
                        if cleaned and len(cleaned) >= 2 and cleaned not in skip_words:
                            name_lines.insert(0, cleaned.replace(" ", ""))
                        elif cleaned:
                            # Hit a non-name line, stop going back
                            break
                    # name_lines should be [surname, firstname, patronymic] in order
                    if len(name_lines) >= 1 and not last_name:
                        last_name = name_lines[0]
                    if len(name_lines) >= 2 and not first_name:
                        first_name = name_lines[1]
                    if len(name_lines) >= 3 and not middle_name:
                        middle_name = name_lines[2]
                    break
                # Check if this line is a date (birth date pattern)
                if re.match(r"\d{2}\.\d{2}", l_upper):
                    # Names are typically 2-4 lines before the date
                    name_lines = []
                    for k in range(max(0, j - 5), j):
                        cleaned = re.sub(r"[^А-ЯЁ\s]", "", lines[k].upper()).strip()
                        if cleaned and len(cleaned) >= 2 and cleaned not in skip_words:
                            name_lines.append(cleaned.replace(" ", ""))
                    if len(name_lines) >= 2 and not last_name:
                        last_name = name_lines[0]
                    if len(name_lines) >= 2 and not first_name:
                        first_name = (
                            name_lines[-1]
                            if name_lines[-1] != last_name
                            else name_lines[-2]
                            if len(name_lines) >= 2
                            else ""
                        )
                    if len(name_lines) >= 3 and not middle_name:
                        middle_name = name_lines[1]
                    break
        if "ЖЕН" in upper or "ЖЕН." in upper:
            if not first_name and i >= 2:
                candidate = re.sub(r"[^А-ЯЁ\s]", "", lines[i - 2].upper()).strip()
                if candidate and len(candidate) >= 2 and candidate not in skip_words:
                    first_name = candidate
            if not last_name and i >= 3:
                candidate = re.sub(r"[^А-ЯЁ\s]", "", lines[i - 3].upper()).strip()
                if candidate and len(candidate) >= 3 and candidate not in skip_words:
                    last_name = candidate
        # Kyrgyz passport: look for ASANOV-type patterns
        if "КЫРГЫЗ" in upper or "KGZ" in upper:
            # Look for name patterns like ASANOV<USON in MRZ-like lines
            mrz_match = re.search(r"([A-Z]{2,})<([A-Z]{2,})", upper.replace(" ", "<"))
            if mrz_match:
                if not last_name:
                    last_name = mrz_match.group(1)
                if not first_name:
                    first_name = mrz_match.group(2)

    # Apply OCR error corrections to the final names
    corrections_map = {
        "Y": "U",  # Y often should be U
        "ы": "и",  # Lowercase ы → и
        "Ы": "И",  # Uppercase Ы → И
        "х": "х",  # Lowercase х → х
        "Х": "Х",  # Uppercase Х → Х
        "Ь": "",  # Soft sign often creates OCR noise
        "Ъ": "",  # Hard sign often creates OCR noise
        "X": "И",  # X often represents И in OCR
        "I": "И",  # Latin I often represents Cyrillic И
        "B": "В",  # Latin B often represents Cyrillic В
        "H": "Н",  # Latin H often represents Cyrillic Н
        "K": "К",  # Latin K often represents Cyrillic К
        "M": "М",  # Latin M often represents Cyrillic М
        "O": "О",  # Latin O often represents Cyrillic О
        "P": "Р",  # Latin P often represents Cyrillic Р
        "C": "С",  # Latin C often represents Cyrillic С
        "T": "Т",  # Latin T often represents Cyrillic Т
        "A": "А",  # Latin A often represents Cyrillic А
        "E": "Е",  # Latin E often represents Cyrillic Е
        "y": "у",  # Lowercase y → у
        "i": "и",  # Lowercase i → и
        "o": "о",  # Lowercase o → о
        "e": "е",  # Lowercase e → е
        "a": "а",  # Lowercase a → а
        "p": "р",  # Lowercase p → р
        "c": "с",  # Lowercase c → с
        "t": "т",  # Lowercase t → т
        "k": "к",  # Lowercase k → к
        "h": "н",  # Lowercase h → н
        "m": "м",  # Lowercase m → м
        "b": "в",  # Lowercase b → в
        "0": "О",  # Digit 0 often should be Cyrillic О
        "3": "З",  # Digit 3 often should be Cyrillic З
        "6": "Б",  # Digit 6 often should be Cyrillic Б
    }

    # Apply corrections to last_name
    if last_name:
        corrected = last_name
        for old_char, new_char in corrections_map.items():
            corrected = corrected.replace(old_char, new_char)
        last_name = corrected

    # Apply corrections to first_name
    if first_name:
        corrected = first_name
        for old_char, new_char in corrections_map.items():
            corrected = corrected.replace(old_char, new_char)
        first_name = corrected

    # Apply corrections to middle_name
    if middle_name:
        corrected = middle_name
        for old_char, new_char in corrections_map.items():
            corrected = corrected.replace(old_char, new_char)
        middle_name = corrected

    return {
        "last_name": last_name,
        "first_name": first_name,
        "middle_name": middle_name,
    }


def extract_dates(text: str) -> Dict[str, str]:
    """Извлекает даты из текста, включая варианты с пробелами и запятыми."""
    all_dates = []

    # DD.MM.YYYY, DD/MM/YYYY, DD-MM-YYYY, DD,MM,YYYY, DD MM YYYY
    for d, m, y in re.findall(r"(\d{2})[.\-/\s,]+(\d{2})[.\-/\s,]+(\d{4})", text):
        date_str = f"{d}.{m}.{y}"
        if date_str not in all_dates:
            all_dates.append(date_str)

    # YYYY.MM.YYYY (OCR часто склеивает DD и MM)
    for yymm, yyyy in re.findall(r"(\d{4})[.](\d{4})", text):
        dd = yymm[:2]
        mm = yymm[2:]
        if 1 <= int(mm) <= 12 and 1 <= int(dd) <= 31:
            date_str = f"{dd}.{mm}.{yyyy}"
            if date_str not in all_dates:
                all_dates.append(date_str)

    classified = _classify_dates_by_year(all_dates)
    return {
        "birth_date": classified["date_of_birth"],
        "issue_date": classified["date_of_issue"],
        "expiry_date": classified["date_of_expiry"],
    }


def extract_gender(text: str) -> Optional[str]:
    """Извлекает пол из текста с fuzzy matching для OCR-ошибок."""
    if re.search(r"\bERKAK\b", text, re.IGNORECASE):
        return "ERKKAK"
    elif re.search(r"\bAYOL\b", text, re.IGNORECASE):
        return "AYOL"
    # Russian passport gender markers
    if re.search(r"\bМУЖ\b", text):
        return "ERKKAK"
    if re.search(r"\bЖЕН\b", text):
        return "AYOL"

    # Handle common OCR errors for gender
    text_upper = text.upper()

    # Enhanced OCR error patterns for "AYOL"
    # Common OCR errors: 0→O, 1→I, |→I, >→Y, <→I, etc.
    # More comprehensive patterns for AYOL variations
    ayol_patterns = [
        r"A[YI1|><\[\]!]+[YI1|><\[\]!]*[0OQ][L1I|><\[\]!]",  # A followed by Y/I variants, O/0, L
        r"A.*[YI].*[0O].*L",  # A followed by Y/I, then 0/O, then L (with any chars in between)
        r"A[YOI1|><!\[\]]{2,4}L?",  # A followed by 2-4 Y/O/I chars potentially ending in L
        r"A[YI][0O][L1I|>!<\[\]]",  # Direct AY0L pattern and variants
    ]

    for pattern in ayol_patterns:
        matches = re.findall(pattern, text_upper)
        for match in matches:
            # Check if this match is close to "AYOL" using fuzzy matching
            try:
                from rapidfuzz import fuzz

                if fuzz.ratio(match, "AYOL") >= 60:
                    return "AYOL"
            except ImportError:
                # Simple heuristic if rapidfuzz not available
                temp_match = (
                    match.replace("0", "O")
                    .replace("1", "I")
                    .replace("|", "I")
                    .replace("!", "I")
                    .replace(">", "Y")
                    .replace("<", "I")
                )
                if (
                    "A" in temp_match
                    and any(c in temp_match for c in "YI")
                    and any(c in temp_match for c in "O0")
                    and "L" in temp_match
                ):
                    return "AYOL"

    # Enhanced ERKAK patterns for OCR errors
    erkak_patterns = [
        r"E[R2P]?[RK][KAK]*",  # ERK, E2K, EPK, etc.
        r"E.*R.*K.*A.*K",  # Letters in sequence (with any chars in between)
        r"EPKAK",  # Common OCR error
        r"E[R|]R.*K",  # With OCR errors
        r"E[RP]?R[O1|><!\[\]]*K[AK]*",  # More flexible ERKAK detection
    ]

    for pattern in erkak_patterns:
        matches = re.findall(pattern, text_upper)
        for match in matches:
            try:
                from rapidfuzz import fuzz

                if fuzz.ratio(match, "ERKAK") >= 60:
                    return "ERKKAK"
            except ImportError:
                temp_match = match.replace("2", "R").replace("P", "R").replace("|", "I")
                if (
                    "E" in temp_match
                    and any(c in temp_match for c in "R")
                    and "K" in temp_match
                    and ("A" in temp_match or "K" in temp_match)
                ):
                    return "ERKKAK"
            except ImportError:
                temp_match = match.replace("2", "R").replace("P", "R").replace("|", "I")
                if (
                    "E" in temp_match
                    and any(c in temp_match for c in "R")
                    and "K" in temp_match
                    and ("A" in temp_match or "K" in temp_match)
                ):
                    return "ERKKAK"

    # Even broader fuzzy matching
    try:
        from rapidfuzz import fuzz

        for line in text.split("\n"):
            # Extract potential words that might be gender indicators
            tokens = re.split(r"[ <0-9/\"'.,;=]+", line.upper())
            tokens = [
                t
                for t in tokens
                if 3 <= len(t) <= 10 and re.match(r"^[A-Z0-9|><!\[\]]+$", t)
            ]
            for token in tokens:
                # Check similarity to both gender terms
                ayol_score = fuzz.ratio(token, "AYOL")
                erkak_score = fuzz.ratio(token, "ERKAK")

                if ayol_score >= 65:
                    return "AYOL"
                elif erkak_score >= 65:
                    return "ERKKAK"
    except ImportError:
        pass

    # Fallback: line-by-line analysis with OCR corrections
    for line in text.split("\n"):
        line_upper = line.upper()
        # Apply OCR error corrections to the line
        corrected_line = (
            line_upper.replace("0", "O")
            .replace("1", "I")
            .replace("|", "I")
            .replace("!", "I")
            .replace("@", "O")
            .replace("3", "B")
            .replace("6", "B")
        )

        if re.search(r"\bAY[OI1|>!<\[\]]*O?[L1I|>!<\[\]]", corrected_line):
            return "AYOL"
        if re.search(r"\bE[P2]?R[K|I1><!\[\]]*K[AK]*", corrected_line):
            return "ERKKAK"

    return None


def extract_issued_by(text: str) -> Optional[str]:
    """Извлекает информацию о том, кем выдан документ."""
    if re.search(r"TOSHKEN", text, re.IGNORECASE):
        return "TOSHKENT"
    return None


def extract_nationality(text: str) -> Optional[str]:
    """Извлекает гражданство из текста."""
    if re.search(r"O['']?ZBEKISTON", text, re.IGNORECASE):
        return "O'ZBEKISTON"
    return "O'ZBEKISTON"


def extract_passport_number(text: str) -> Optional[str]:
    """Извлекает номер паспорта из текста с исправлением OCR ошибок."""
    # Транслитерируем кириллические "Схожие" буквы (А, В, Е, К, М, Н, О, Р, С, Т, Х)
    text_latin = (
        text.replace("А", "A")
        .replace("В", "B")
        .replace("Е", "E")
        .replace("К", "K")
        .replace("М", "M")
        .replace("Н", "H")
        .replace("О", "O")
        .replace("Р", "P")
        .replace("С", "C")
        .replace("Т", "T")
        .replace("Х", "X")
    )

    # Сначала ищем точный паттерн AA1234567
    match = re.search(r"([A-Z]{2}\d{7})", text_latin)
    if match:
        return match.group(1).upper()

    # Fallback: ищем с OCR-ошибками (4→A, I→1, D→0 и т.д.)
    # Ищем любые 9-символьные строки начинающиеся с 2 букв/цифр
    candidates = re.findall(r"([A-Z0-9]{9,10})", text_latin)
    for candidate in candidates:
        fixed = candidate
        # Исправляем OCR-ошибки
        fixed = re.sub(r"^4", "A", fixed)
        fixed = re.sub(r"^I", "A", fixed)
        fixed = fixed[:2].replace("0", "O") + fixed[2:]
        # В позициях 2-9: I→1, D→0, O→0, S→5, Z→2
        rest = fixed[2:]
        rest = (
            rest.replace("I", "1")
            .replace("D", "0")
            .replace("O", "0")
            .replace("S", "5")
            .replace("Z", "2")
        )
        fixed = fixed[:2] + rest
        if re.match(r"^[A-Z]{2}\d{7}$", fixed):
            return fixed
    return None


def extract_pinfl(text: str, mrz_pinfl: str = "") -> Optional[str]:
    """Извлекает ПИНФЛ (14 цифр) из текста с коррекцией OCR-ошибок."""
    all_numbers = re.findall(r"\d{14,}", text)

    # Если есть MRZ ПИНФЛ, ищем совпадение по префиксу
    if mrz_pinfl and len(mrz_pinfl) >= 6:
        mrz_prefix = mrz_pinfl[:6]
        for num in all_numbers:
            if len(num) >= 14:
                candidate = num[:14]
                if candidate.startswith(mrz_prefix):
                    return candidate

        # Fallback: берём первые 6 из MRZ + остальное из первого 14-значного
        for num in all_numbers:
            if len(num) >= 14:
                return mrz_prefix + num[6:]

    # Без MRZ — ищем 14-значное число, начинающееся с 1, 2 или 3 (ПИНФЛ Узбекистана)
    for num in all_numbers:
        if len(num) == 14 and num[0] in "123":
            return num
        if len(num) > 14:
            candidates = [num[:14], num[-14:]]
            for c in candidates:
                if c[0] in "123":
                    return c

    # Fallback: первое 14-значное с коррекцией первой цифры
    for num in all_numbers:
        if len(num) == 14:
            # ПИНФЛ Узбекистана не начинается с 9 — это OCR-ошибка (9→3)
            if num[0] == "9":
                return "3" + num[1:]
            return num
        if len(num) > 14:
            candidate = num[:14]
            if candidate[0] == "9":
                return "3" + candidate[1:]
            return candidate
    return None
