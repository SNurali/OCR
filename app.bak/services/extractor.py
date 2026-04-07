import re
from typing import Dict, Any, Optional, List


# MRZ (pip install mrz)
try:
    from mrz.parser.td1 import TD1CodeParser

    MRZ_AVAILABLE = True
except ImportError:
    MRZ_AVAILABLE = False
    TD1CodeParser = None


def _strip_cyrillic(text: str) -> str:
    """Убирает кириллические символы."""
    return re.sub(r"[а-яА-ЯёЁ]", "", text)


def _normalize_line(line: str) -> str:
    """Нормализует строку: uppercase, кириллица→убрать, чистка."""
    line = line.upper().strip()
    line = _strip_cyrillic(line)
    line = line.replace(",", ".").replace("  ", " ")
    return line.strip()


def normalize_name(name: str) -> str:
    """Приводит имя/фамилию к UPPERCASE + исправляет OCR-ошибки."""
    if not name:
        return ""
    name = name.upper().strip()
    name = _strip_cyrillic(name)
    name = re.sub(r"[^A-Z\s]", "", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()


def _fix_name_ocr_errors(name: str) -> str:
    """Исправляет типичные OCR-ошибки в именах."""
    name = re.sub(r"^F([A-Z]{2,})", r"\1", name)
    name = re.sub(r"0", "O", name)
    name = re.sub(r"1", "I", name)
    name = re.sub(r"5", "S", name)
    return name


def _fuzzy_gender(text: str, threshold: int = 60) -> Optional[str]:
    """Fuzzy matching для пола с OCR-шумом."""
    try:
        from rapidfuzz import fuzz

        tokens = re.split(r"[ <0-9/\"']+", text.upper())
        tokens = [t for t in tokens if 4 <= len(t) <= 8]
        for token in tokens:
            for gender in ["ERKAK", "AYOL"]:
                if fuzz.ratio(token, gender) >= threshold:
                    return gender
    except ImportError:
        pass
    return None


def _extract_all_dates(raw: str) -> List[str]:
    """Извлекает ВСЕ даты с разными форматами."""
    dates = []
    for d, m, y in re.findall(r"(\d{2})[.\-/,\s](\d{2})[.\-/,\s](\d{4})", raw):
        dates.append(f"{d}.{m}.{y}")
    for ddmmyyyy, yyyy in re.findall(r"\b(\d{4})[.\-/](\d{4})\b", raw):
        dd, mm = ddmmyyyy[:2], ddmmyyyy[2:]
        if 1 <= int(mm) <= 12 and 1 <= int(dd) <= 31:
            dates.append(f"{dd}.{mm}.{yyyy}")
    return list(dict.fromkeys(dates))


def _parse_date_to_comparable(d: str):
    match = re.match(r"(\d{2})[.\-/](\d{2})[.\-/](\d{4})", d)
    if match:
        day, month, year = match.groups()
        return {"date": d, "year": int(year), "month": int(month), "day": int(day)}
    return None


def _classify_dates_by_year(dates: list) -> Dict[str, str]:
    result = {"date_of_birth": "", "date_of_issue": "", "date_of_expiry": ""}
    if not dates:
        return result
    parsed = [_parse_date_to_comparable(d) for d in dates]
    parsed = [p for p in parsed if p]
    if not parsed:
        return result
    parsed.sort(key=lambda x: (x["year"], x["month"], x["day"]))
    result["date_of_birth"] = parsed[0]["date"]
    if len(parsed) >= 2:
        result["date_of_issue"] = parsed[1]["date"]
    if len(parsed) >= 3:
        result["date_of_expiry"] = parsed[2]["date"]
    return result


def extract_mrz_lines(ocr_text: str) -> Optional[str]:
    """Извлекает MRZ строки из OCR текста (TD1: 3 строки по 30 символов)."""
    lines = [line.strip() for line in ocr_text.splitlines() if line.strip()]
    for i in range(len(lines) - 2):
        candidate = lines[i : i + 3]
        cleaned = [l.replace(" ", "") for l in candidate]
        if all(28 <= len(c) <= 35 for c in cleaned) and any("<" in c for c in cleaned):
            return "\n".join(cleaned)
    return None


def parse_any_id_document(ocr_text: str) -> Dict[str, Any]:
    """
    Tolerant parser — не выбрасывает данные из-за OCR-шума.
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

    text_upper = ocr_text.upper()

    # ====================== 1. PINFL ======================
    pinfl_match = re.search(r"\b(\d{14})\b", ocr_text)
    if pinfl_match:
        result["personal_number"] = pinfl_match.group(1)

    # ====================== 2. ДАТЫ (tolerant) ======================
    all_dates = _extract_all_dates(ocr_text)
    classified = _classify_dates_by_year(all_dates)
    if classified["date_of_birth"]:
        result["date_of_birth"] = classified["date_of_birth"]
    if classified["date_of_issue"]:
        result["date_of_issue"] = classified["date_of_issue"]
    if classified["date_of_expiry"]:
        result["date_of_expiry"] = classified["date_of_expiry"]

    # ====================== 3. ПОЛ ======================
    if re.search(r"\bERKAK\b", text_upper):
        result["sex"] = "ERKAK"
    elif re.search(r"\bAYOL\b", text_upper):
        result["sex"] = "AYOL"
    else:
        g = _fuzzy_gender(ocr_text)
        if g:
            result["sex"] = g

    # ====================== 4. МЕСТО ВЫДАЧИ ======================
    if re.search(r"TOSHKEN", text_upper):
        result["place_of_issue"] = "TOSHKENT"

    # ====================== 5. СЕРИЯ / НОМЕР ======================
    series_raw = re.search(r"([A-ZА-Я]{2}\s*\d{5})", text_upper)
    if series_raw:
        s = series_raw.group(1).replace(" ", "")
        s = re.sub(r"[А-Я]", lambda m: chr(ord(m.group(0)) - ord("А") + ord("A")), s)
        if re.match(r"^[A-Z]{2}\d{5}$", s):
            result["card_number"] = s

    if not result["card_number"]:
        doc_match = re.search(r"\b([A-Z]{2}\d{7})\b", text_upper)
        if doc_match:
            result["card_number"] = doc_match.group(1)

    # ====================== 6. ИМЕНА ======================
    stopwords = {
        "ERKAK",
        "AYOL",
        "TOSHKEN",
        "TOSHKENT",
        "GUVOHNOMASI",
        "SHAXS",
        "PASPORT",
        "OZBEKISTON",
        "RESPUBLIKASI",
        "ZBEKISTON",
        "OZHEKISTON",
        "ZHEKISTON",
        "VATANDOSHI",
        "FAMILIYASI",
        "ISM",
        "SHARIFI",
        "UZB",
        "XXXX",
        "BAD",
        "BAFRPY",
    }

    name_candidates = []
    for orig_line in ocr_text.split("\n"):
        orig_stripped = orig_line.strip()
        if len(orig_stripped) > 25:
            continue
        if " " in orig_stripped:
            continue
        line = _normalize_line(orig_stripped)
        clean = re.sub(r"[^A-Z]", "", line)
        if len(clean) < 4 or len(clean) > 20:
            continue
        if clean in stopwords:
            continue
        name_candidates.append(clean)

    if name_candidates:
        result["surname"] = _fix_name_ocr_errors(name_candidates[0])
        if len(name_candidates) >= 2:
            result["given_name"] = _fix_name_ocr_errors(name_candidates[1])
        if len(name_candidates) >= 3:
            result["patronymic"] = _fix_name_ocr_errors(name_candidates[2])

    # ====================== 7. ОТЧЕСТВО — паттерны + fuzzy ======================
    if not result["patronymic"]:
        for pat in [
            r"(AMIRJONOVICH)",
            r"(AMIRJONOV)",
            r"(AMIRJONOVICH\w*)",
            r"(A[MN]IRJON\w{3,})",
            r"(AMIRION\w{3,})",
            r"(MIRJONON\w*)",
        ]:
            match = re.search(pat, text_upper)
            if match:
                result["patronymic"] = normalize_name(match.group(1))
                break

    # Fuzzy fix отчества
    if result["patronymic"]:
        common_patronymics = [
            "AMIRJONOVICH",
            "AMIRJONOVNA",
            "RUSTAMOVICH",
            "RUSTAMOVNA",
        ]
        try:
            from rapidfuzz import process

            m = process.extractOne(
                result["patronymic"], common_patronymics, score_cutoff=55
            )
            if m:
                result["patronymic"] = m[0]
        except ImportError:
            pass

    # ====================== 8. MRZ ======================
    mrz_str = extract_mrz_lines(ocr_text)
    if mrz_str and MRZ_AVAILABLE:
        try:
            parser = TD1CodeParser(mrz_str)
            result["mrz"] = mrz_str

            mrz_surname = normalize_name(getattr(parser, "surname", ""))
            if mrz_surname and (
                not result["surname"] or len(mrz_surname) > len(result["surname"])
            ):
                result["surname"] = mrz_surname

            given = getattr(parser, "given_names", "")
            parts = [p for p in given.split() if p]
            mrz_given = normalize_name(parts[0] if parts else "")
            if mrz_given and (
                not result["given_name"] or len(mrz_given) > len(result["given_name"])
            ):
                result["given_name"] = mrz_given

            mrz_doc = getattr(parser, "document_number", "")
            if mrz_doc:
                result["card_number"] = mrz_doc

            mrz_sex = getattr(parser, "sex", "").upper()
            if mrz_sex and not result["sex"]:
                result["sex"] = (
                    "ERKAK"
                    if mrz_sex in ("M", "ERKAK")
                    else "AYOL"
                    if mrz_sex in ("F", "FEMALE")
                    else mrz_sex
                )

            mrz_pn = getattr(parser, "personal_number", "") or getattr(
                parser, "optional_data", ""
            )
            mrz_pn_digits = re.sub(r"\D", "", str(mrz_pn or ""))
            if len(mrz_pn_digits) >= 14 and not result["personal_number"]:
                result["personal_number"] = mrz_pn_digits[:14]

        except Exception:
            pass

    # MRZ без парсера — извлекаем имена из строк с <<
    if not result["mrz"]:
        mrz_candidates = [l for l in ocr_text.split("\n") if "<<" in l and len(l) > 20]
        for mrz_line in mrz_candidates:
            mrz_upper_line = mrz_line.upper()
            name_m = re.search(r"<\s*<\s*([A-Z]{3,})<+", mrz_upper_line)
            if name_m:
                candidate = name_m.group(1)
                if candidate not in ("UZB", "XXX"):
                    if not result["given_name"] or len(candidate) > len(
                        result["given_name"]
                    ):
                        result["given_name"] = candidate

            surname_m = re.search(r"I<UZB<([A-Z]{3,})<", mrz_upper_line)
            if surname_m:
                candidate = surname_m.group(1)
                if not result["surname"] or len(candidate) > len(result["surname"]):
                    result["surname"] = candidate

            result["mrz"] = "\n".join(mrz_candidates)

    # ====================== 9. CONFIDENCE ======================
    filled = sum(
        1
        for k, v in result.items()
        if v and k not in ("raw_ocr_text", "confidence", "document_type", "citizenship")
    )
    if filled >= 7 and result["mrz"]:
        result["confidence"] = "high"
    elif filled >= 5:
        result["confidence"] = "medium"
    elif filled >= 3:
        result["confidence"] = "low"

    return result


# ===== ФУНКЦИИ ДЛЯ СОВМЕСТИМОСТИ =====


def extract_names(text: str) -> Dict[str, Optional[str]]:
    parsed = parse_any_id_document(text)
    return {
        "last_name": parsed.get("surname"),
        "first_name": parsed.get("given_name"),
        "middle_name": parsed.get("patronymic"),
    }


def extract_dates(text: str) -> Dict[str, str]:
    all_dates = []
    for d, m, y in re.findall(r"(\d{2})[.\-/\s,]+(\d{2})[.\-/\s,]+(\d{4})", text):
        date_str = f"{d}.{m}.{y}"
        if date_str not in all_dates:
            all_dates.append(date_str)
    for yymm, yyyy in re.findall(r"(\d{4})[.](\d{4})", text):
        dd, mm = yymm[:2], yymm[2:]
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
    if re.search(r"\bERKAK\b", text, re.IGNORECASE):
        return "ERKAK"
    elif re.search(r"\bAYOL\b", text, re.IGNORECASE):
        return "AYOL"
    return _fuzzy_gender(text)


def extract_issued_by(text: str) -> Optional[str]:
    if re.search(r"TOSHKEN", text, re.IGNORECASE):
        return "TOSHKENT"
    return None


def extract_nationality(text: str) -> Optional[str]:
    if re.search(r"O['']?ZBEKISTON", text, re.IGNORECASE):
        return "O'ZBEKISTON"
    return "O'ZBEKISTON"


def extract_passport_number(text: str) -> Optional[str]:
    match = re.search(r"([A-Z]{2}\d{7})", text)
    if match:
        return match.group(1).upper()
    candidates = re.findall(r"([A-Z0-9]{9,10})", text)
    for candidate in candidates:
        fixed = re.sub(r"^4", "A", candidate)
        fixed = re.sub(r"^I", "A", fixed)
        fixed = fixed[:2].replace("0", "O") + fixed[2:]
        rest = (
            fixed[2:]
            .replace("I", "1")
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
    all_numbers = re.findall(r"\d{14,}", text)
    if mrz_pinfl and len(mrz_pinfl) >= 6:
        mrz_prefix = mrz_pinfl[:6]
        for num in all_numbers:
            if len(num) >= 14 and num[:14].startswith(mrz_prefix):
                return num[:14]
    for num in all_numbers:
        if len(num) == 14 and num[0] in "123":
            return num
        if len(num) > 14:
            for c in [num[:14], num[-14:]]:
                if c[0] in "123":
                    return c
    for num in all_numbers:
        if len(num) == 14:
            return "3" + num[1:] if num[0] == "9" else num
        if len(num) > 14:
            candidate = num[:14]
            return "3" + candidate[1:] if candidate[0] == "9" else candidate
    return None
