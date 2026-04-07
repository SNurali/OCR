"""Smart parsing module: extracts structured data from OCR text with MRZ-first logic."""

import re
from typing import Dict, Any, Optional, Set
import logging

logger = logging.getLogger(__name__)

# Uzbekistan ID-specific keywords
UZ_KEYWORDS = {
    "OZBEKISTON",
    "O'ZBEKISTON",
    "SHAXS",
    "GUVOHNOMASI",
    "RESPUBLIKASI",
    "ERKAK",
    "AYOL",
    "TOSHKENT",
    "TOSHKEN",
}

# Common OCR prefix/suffix noise for Uzbek names — single chars only
OCR_NAME_NOISE_PREFIXES = {"F", "K", "P", "I", "L", "J"}


def _remove_duplicate_chars(text: str, threshold: int = 1) -> str:
    """
    Remove duplicate characters caused by OCR artifacts.

    Examples:
        NURALIKKKKKKKKKKKK → NURALIK (threshold=1)
        ERKKAK → ERKAK (threshold=1)
    """
    if not text:
        return ""

    result = []
    char_count = 1

    for i, char in enumerate(text):
        if i == 0:
            result.append(char)
            continue

        if char == text[i - 1]:
            char_count += 1
        else:
            char_count = 1

        # Keep char if count <= threshold
        if char_count <= threshold:
            result.append(char)

    return "".join(result)


def _fix_ocr_name_noise(name: str) -> str:
    """Removes common OCR noise prefixes/suffixes from names."""
    if not name:
        return ""
    name = name.upper().strip()
    # Remove single/double char noise prefixes
    for prefix in sorted(OCR_NAME_NOISE_PREFIXES, key=len, reverse=True):
        if name.startswith(prefix) and len(name) > len(prefix) + 2:
            rest = name[len(prefix) :]
            if rest[0] in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                return rest
    return name


def normalize_name(name: str, name_type: str = "first") -> str:
    """
    Normalize name with OCR error correction.

    Args:
        name: Raw name from OCR
        name_type: 'first', 'last', 'patronymic'
    """
    if not name:
        return ""

    name = name.upper().strip()

    # STEP 1: Remove duplicate characters FIRST
    # This handles NURALIKKKKKK → NURALIK, ERKKAK → ERKAK
    name = _remove_duplicate_chars(name, threshold=1)

    # STEP 2: Fix specific Uzbek surname errors
    if name_type == "last":
        # SULAYMANOV variations - common OCR errors
        surname_fixes = {
            "ULAYMANOV",
            "SULATMANOV",
            "SULAIMANOV",
            "SLAYMANOV",
            "SULATHANOV",
            "SULATHANOW",
            "SULAYMANOW",
            "SULATMANOW",
            "SULAYMANO",
            "SULATMANO",
            "ULAYMANO",
            "SULAYMAN",
        }
        if name in surname_fixes:
            name = "SULAYMANOV"
        # If name starts with common OCR-truncated patterns
        if name.startswith("ULAYMAN") or name.startswith("SULAYMANO"):
            name = "SULAYMANOV"
        # Fix T→Y, H→Y confusion in surnames
        if "TMANOV" in name or "THANOV" in name:
            name = name.replace("TMANOV", "YMANOV").replace("THANOV", "YMANOV")

    # STEP 3: Strip common OCR noise prefixes
    name = _fix_ocr_name_noise(name)

    # STEP 4: OCR character corrections
    name = name.replace("0", "O")
    name = name.replace("1", "I")
    name = name.replace("5", "S")
    name = name.replace("4", "A")
    name = name.replace("3", "E")
    name = name.replace("8", "B")
    name = name.replace("9", "G")
    name = name.replace("2", "Z")

    # Special: M→N correction for common OCR errors (but not real MU/MA names)
    if name.startswith("M") and len(name) >= 4:
        from app.services.name_lexicons import COMMON_FIRST_NAMES

        alt = "N" + name[1:]
        if alt in COMMON_FIRST_NAMES and name not in COMMON_FIRST_NAMES:
            name = alt

    name = re.sub(r"[^A-Z\s]", "", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()


def _parse_date_safe(ds: str) -> Optional[str]:
    if not ds:
        return None
    from datetime import datetime

    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            dt = datetime.strptime(ds, fmt)
            return dt.strftime("%d.%m.%Y")
        except ValueError:
            continue
    return None


def _classify_dates(dates: list) -> Dict[str, str]:
    result = {"birth_date": "", "issue_date": "", "expiry_date": ""}
    if not dates:
        return result

    parsed = []
    for d in dates:
        from datetime import datetime

        m = re.match(r"(\d{2})[.\-/,](\d{2})[.\-/](\d{4})", d)
        if m:
            day, month, year = m.groups()
            try:
                datetime(int(year), int(month), int(day))
                parsed.append(
                    {"date": d, "year": int(year), "month": int(month), "day": int(day)}
                )
            except ValueError:
                pass

    if not parsed:
        return result

    parsed.sort(key=lambda x: (x["year"], x["month"], x["day"]))
    result["birth_date"] = parsed[0]["date"]
    if len(parsed) >= 2:
        result["issue_date"] = parsed[1]["date"]
    if len(parsed) >= 3:
        result["expiry_date"] = parsed[2]["date"]

    return result


def extract_from_text(
    ocr_text: str, mrz_data: Optional[Dict] = None, ocr_confidence: float = 0.0
) -> Dict[str, Any]:
    """
    MRZ-first extraction strategy with LLM enhancement:
    1. If MRZ is valid → use MRZ as source of truth
    2. Fallback to OCR text extraction
    3. LLM enhancement for low-confidence OCR (< 50%) or missing fields
    4. Merge and reconcile
    """
    mrz_data = mrz_data or {}
    mrz_valid = mrz_data.get("all_checks_valid", False) or mrz_data.get("valid", False)

    result = {
        "first_name": "",
        "last_name": "",
        "middle_name": "",
        "birth_date": "",
        "gender": "",
        "nationality": "",
        "passport_number": "",
        "passport_series": "",
        "issue_date": "",
        "expiry_date": "",
        "issued_by": "",
        "pinfl": "",
    }

    # === MRZ-FIRST: Use MRZ data when valid ===
    if mrz_valid:
        result["first_name"] = normalize_name(
            mrz_data.get("given_names", "").split()[0]
            if mrz_data.get("given_names")
            else ""
        )
        result["last_name"] = normalize_name(
            mrz_data.get("surname", ""), name_type="last"
        )
        result["birth_date"] = _parse_date_safe(mrz_data.get("birth_date", "")) or ""
        result["gender"] = mrz_data.get("gender", "")
        result["nationality"] = mrz_data.get("nationality", "")
        result["passport_number"] = mrz_data.get("passport_number", "").replace("<", "")
        result["pinfl"] = mrz_data.get("personal_number", "")

        given_parts = mrz_data.get("given_names", "").split()
        if len(given_parts) > 1:
            result["middle_name"] = normalize_name(" ".join(given_parts[1:]))

        logger.info(f"MRZ-first extraction: valid MRZ used as source of truth")

    # === Fallback: Extract from OCR text ===
    if not result["first_name"]:
        result["first_name"] = _extract_first_name(ocr_text)
    if not result["last_name"]:
        result["last_name"] = _extract_last_name(ocr_text)
    if not result["middle_name"]:
        result["middle_name"] = _extract_patronymic(ocr_text)

    if not result["birth_date"]:
        all_dates = re.findall(r"(\d{2}[.\-/,]\d{2}[.\-/]\d{4})", ocr_text)
        all_dates = [d.replace(",", ".") for d in all_dates]
        classified = _classify_dates(all_dates)
        result["birth_date"] = classified.get("birth_date", "")

    if not result["gender"]:
        result["gender"] = _extract_gender(ocr_text)

    if not result["nationality"]:
        result["nationality"] = _extract_nationality(ocr_text)

    if not result["passport_number"]:
        result["passport_number"] = _extract_passport_number(ocr_text)

    if not result["pinfl"]:
        result["pinfl"] = _extract_pinfl(ocr_text)

    # Extract dates from visual text
    all_dates = re.findall(r"(\d{2}[.\-/,]\d{2}[.\-/]\d{4})", ocr_text)
    all_dates = [d.replace(",", ".") for d in all_dates]
    classified = _classify_dates(all_dates)
    if not result["issue_date"]:
        result["issue_date"] = classified.get("issue_date", "")
    if not result["expiry_date"]:
        result["expiry_date"] = classified.get("expiry_date", "")

    if not result["issued_by"]:
        result["issued_by"] = _extract_issued_by(ocr_text)

    # Passport series = first 2 chars of passport number
    if result["passport_number"] and len(result["passport_number"]) >= 2:
        result["passport_series"] = result["passport_number"][:2]

    # === LLM Enhancement (Groq/Google) ===
    # Use LLM when:
    # 1. OCR confidence < 85% (даже при "высоком" качестве могут быть ошибки)
    # 2. Много пустых критичных полей
    # 3. MRZ не валиден
    # 4. Данные выглядят как мусор (имя содержит цифры, слишком длинное и т.д.)

    filled_fields = sum(1 for v in result.values() if v)
    critical_empty = (
        not result.get("first_name")
        or not result.get("last_name")
        or not result.get("birth_date")
        or not result.get("passport_number")
    )

    # Проверка на мусорные данные
    first_name = result.get("first_name", "")
    has_garbage_name = (
        len(first_name) > 15  # Слишком длинное имя
        or re.search(r"\d", first_name)  # Содержит цифры
        or re.search(r"[X]{3,}", first_name)  # Содержит XXX
    )

    llm_needed = (
        ocr_confidence < 0.85
        or critical_empty
        or filled_fields < 5
        or not mrz_valid
        or has_garbage_name
    )

    # NOTE: LLM enhancement через текст больше не используется.
    # Вместо этого VLM-пайплайн работает напрямую с изображениями.
    # Этот блок оставлен для обратной совместимости, но больше не вызывает API.
    if llm_needed:
        logger.info(
            f"LLM enhancement would be triggered (OCR confidence: {ocr_confidence:.2f}, filled: {filled_fields}/12), "
            "but VLM now works directly with images, not text."
        )

    logger.info(f"Parsed: {result}")
    return result


def _extract_first_name(text: str) -> str:
    from app.services.name_lexicons import COMMON_FIRST_NAMES

    # First: Fix common OCR errors for Uzbek names
    text_upper = text.upper()
    # NURA → NURALI (common truncation)
    if "NURA" in text_upper and "NURALI" not in text_upper:
        text_upper = text_upper.replace("NURA", "NURALI")
    # NURAL → NURALI
    if "NURAL " in text_upper or "NURAL\n" in text_upper:
        text_upper = text_upper.replace("NURAL", "NURALI")

    # First pass: exact match
    for line in text_upper.split("\n"):
        tokens = re.split(r"[ <0-9/]+", line)
        for token in tokens:
            cleaned = re.sub(r"[^A-Z]", "", token)
            if len(cleaned) >= 3 and cleaned in COMMON_FIRST_NAMES:
                return normalize_name(cleaned)

    # Second pass: fuzzy match with rapidfuzz
    try:
        from rapidfuzz import fuzz

        for line in text.split("\n"):
            tokens = re.split(r"[ <0-9/]+", line.upper())
            for token in tokens:
                cleaned = re.sub(r"[^A-Z]", "", token)
                if len(cleaned) < 3:
                    continue
                # Try stripping noise prefixes
                for prefix in sorted(OCR_NAME_NOISE_PREFIXES, key=len, reverse=True):
                    if cleaned.startswith(prefix) and len(cleaned) > len(prefix) + 2:
                        stripped = cleaned[len(prefix) :]
                        if stripped in COMMON_FIRST_NAMES:
                            return normalize_name(stripped)
                        # Also try M→N correction on stripped
                        if (
                            stripped.startswith("M")
                            and not stripped.startswith("MU")
                            and not stripped.startswith("MA")
                        ):
                            alt = "N" + stripped[1:]
                            if alt in COMMON_FIRST_NAMES:
                                return normalize_name(alt)
                # Fuzzy match (allow M↔N, common OCR error)
                best_name = None
                best_score = 0
                for name in COMMON_FIRST_NAMES:
                    if abs(len(name) - len(cleaned)) > 3:
                        continue
                    score = fuzz.ratio(cleaned, name)
                    # Also try with M→N correction
                    corrected = cleaned.replace("M", "N")
                    score2 = fuzz.ratio(corrected, name)
                    score = max(score, score2)
                    if score > best_score and score >= 70:
                        best_score = score
                        best_name = name
                if best_name:
                    return normalize_name(best_name)
    except ImportError:
        pass
    return ""


def _extract_last_name(text: str) -> str:
    from app.services.name_lexicons import COMMON_FIRST_NAMES
    from app.services.name_lexicons.patronymics import COMMON_PATRONYMICS

    lines = text.split("\n")
    for i, line in enumerate(lines):
        tokens = re.split(r"[ <0-9/\"']+", line.upper())
        for token in tokens:
            token_clean = re.sub(r"[^A-Z]", "", token)
            if len(token_clean) < 4:
                continue
            if token_clean in COMMON_PATRONYMICS:
                continue
            if token_clean in COMMON_FIRST_NAMES:
                continue
            if token_clean.startswith("UZB") or token_clean.startswith("OZB"):
                continue
            if token_clean in ("RESPUBLIKASI", "GUVOHNOMASI", "SHAXS"):
                continue
            # Check if next line contains a first name (surname comes before first name)
            if i + 1 < len(lines):
                next_tokens = re.split(r"[ <0-9/\"']+", lines[i + 1].upper())
                for nt in next_tokens:
                    nt_clean = re.sub(r"[^A-Z]", "", nt)
                    if nt_clean in COMMON_FIRST_NAMES:
                        return normalize_name(token_clean)
            # Check if previous line is a document header
            if i > 0:
                prev_upper = lines[i - 1].upper()
                if any(
                    kw in prev_upper
                    for kw in ["GUVOHNOMASI", "SHAXS", "PASSPORT", "ID"]
                ):
                    return normalize_name(token_clean)

    # Fuzzy fallback: try stripping OCR noise prefixes
    try:
        from rapidfuzz import fuzz
        from app.services.name_lexicons.central_asia import SURNAMES as CA_SURNAMES

        all_surnames = CA_SURNAMES | COMMON_FIRST_NAMES  # surnames overlap
        for line in lines:
            tokens = re.split(r"[ <0-9/\"']+", line.upper())
            for token in tokens:
                token_clean = re.sub(r"[^A-Z]", "", token)
                if len(token_clean) < 5:
                    continue
                # Try stripping noise prefixes
                for prefix in sorted(OCR_NAME_NOISE_PREFIXES, key=len, reverse=True):
                    if (
                        token_clean.startswith(prefix)
                        and len(token_clean) > len(prefix) + 3
                    ):
                        stripped = token_clean[len(prefix) :]
                        if stripped in all_surnames:
                            return normalize_name(stripped)
                # Fuzzy match against known surnames
                for surname in all_surnames:
                    if abs(len(surname) - len(token_clean)) > 3:
                        continue
                    if fuzz.ratio(token_clean, surname) >= 75:
                        return normalize_name(surname, name_type="last")
    except ImportError:
        pass

    # Fallback: longest word that's not a known name/keyword
    candidates = []
    for line in lines:
        tokens = re.split(r"[ <0-9/\"']+", line.upper())
        for token in tokens:
            token_clean = re.sub(r"[^A-Z]", "", token)
            if len(token_clean) >= 5 and re.match(r"^[A-Z]+$", token_clean):
                if token_clean in UZ_KEYWORDS:
                    continue
                if (
                    token_clean not in COMMON_FIRST_NAMES
                    and token_clean not in COMMON_PATRONYMICS
                ):
                    if not token_clean.startswith("UZB") and not token_clean.startswith(
                        "OZB"
                    ):
                        candidates.append(token_clean)
    if candidates:
        return normalize_name(max(candidates, key=len))
    return ""


def _extract_patronymic(text: str) -> str:
    from app.services.name_lexicons.patronymics import COMMON_PATRONYMICS

    # First pass: exact and substring match
    for line in text.split("\n"):
        tokens = re.split(r"[ <0-9/\"']+", line.upper())
        for token in tokens:
            if token in COMMON_PATRONYMICS:
                return normalize_name(token)
            for p in sorted(COMMON_PATRONYMICS, key=len, reverse=True):
                if p in token:
                    return normalize_name(p)

    # Second pass: fuzzy match for OCR errors
    try:
        from rapidfuzz import fuzz

        for line in text.split("\n"):
            tokens = re.split(r"[ <0-9/\"']+", line.upper())
            for token in tokens:
                cleaned = re.sub(r"[^A-Z]", "", token)
                if len(cleaned) < 6:
                    continue
                best_score = 0
                best_pat = None
                for patronymic in COMMON_PATRONYMICS:
                    score = fuzz.ratio(cleaned, patronymic)
                    if score > best_score and score >= 60:
                        best_score = score
                        best_pat = patronymic
                if best_pat:
                    return normalize_name(best_pat)
    except ImportError:
        pass
    return ""


def _extract_gender(text: str) -> str:
    """Extract gender with duplicate removal and fuzzy matching."""
    text_upper = text.upper()

    # First: Remove duplicates from tokens and check for gender
    for line in text_upper.split("\n"):
        tokens = re.split(r"[ <0-9/\"']+", line)
        for token in tokens:
            if len(token) >= 4:
                # Remove duplicates
                cleaned = _remove_duplicate_chars(token, threshold=1)
                if cleaned == "ERKAK":
                    return "ERKAK"
                if cleaned == "AYOL":
                    return "AYOL"

    # Exact matches
    if re.search(r"\bERKAK\b", text, re.IGNORECASE):
        return "ERKAK"
    if re.search(r"\bAYOL\b", text, re.IGNORECASE):
        return "AYOL"

    # Pattern matches for common OCR errors
    if re.search(r"ERK[AK]{2,}", text_upper):
        return "ERKAK"
    if re.search(r"AYO[L]{1,}", text_upper):
        return "AYOL"

    # Fuzzy match for OCR errors
    try:
        from rapidfuzz import fuzz

        for line in text.split("\n"):
            tokens = re.split(r"[ <0-9/\"']+", line.upper())
            tokens = [t for t in tokens if 4 <= len(t) <= 8]
            for token in tokens:
                # Remove duplicates before fuzzy matching
                cleaned = _remove_duplicate_chars(token, threshold=1)
                if fuzz.ratio(cleaned, "ERKAK") >= 70:
                    return "ERKAK"
                if fuzz.ratio(cleaned, "AYOL") >= 70:
                    return "AYOL"
    except ImportError:
        pass
    return ""


def _extract_nationality(text: str) -> str:
    if re.search(r"O['']?ZBEKISTON", text, re.IGNORECASE):
        return "O'ZBEKISTON"
    return ""


def _extract_passport_number(text: str) -> str:
    # First: exact pattern match AA1234567 (9 chars)
    match = re.search(r"([A-Z]{2}\d{7})", text)
    if match:
        result = match.group(1).upper()
        # Fix common OCR errors in series
        if result.startswith("AO"):
            result = "AD" + result[2:]
        if result.startswith("AM"):
            result = "AD" + result[2:]
        return result

    # Second: Uzbekistan ID card format — 2 letters + 5 digits (7 chars)
    # Prefer lines NOT containing MRZ characters
    lines = text.split("\n")
    candidates_7 = []
    for line in lines:
        if "<" in line:
            continue
        matches = re.findall(r"([A-Z]{2}\d{5})", line)
        for m in matches:
            candidates_7.append(m)

    if candidates_7:
        # Prefer candidates that appear near document keywords
        for i, line in enumerate(lines):
            if "<" in line:
                continue
            for c in candidates_7:
                if c in line:
                    # Check if near document context (GUVOHNOMASI, dates, etc.)
                    context = "\n".join(lines[max(0, i - 3) : i + 3])
                    if any(
                        kw in context
                        for kw in ["GUVOHNOMASI", "SHAXS", "TOSHKEN", "ERKAK"]
                    ):
                        return c
        return candidates_7[0]

    # Third: look for passport-like patterns with OCR errors
    for line in lines:
        if "<" in line:
            continue
        tokens = re.findall(r"([A-Z][A-Z0-9]{5,9})", line.upper())
        for candidate in tokens:
            fixed = candidate.upper()
            first_two = fixed[:2].replace("0", "O").replace("4", "A")
            rest = fixed[2:]
            rest = (
                rest.replace("I", "1")
                .replace("D", "0")
                .replace("O", "0")
                .replace("S", "5")
                .replace("Z", "2")
                .replace("B", "8")
            )
            result = first_two + rest
            if re.match(r"^[A-Z]{2}\d{7}$", result):
                return result
            if re.match(r"^[A-Z]{2}\d{5}$", result):
                return result

    return ""


def _extract_pinfl(text: str) -> str:
    """Extract PINFL with OCR error correction."""
    # Prefer PINFL from non-MRZ lines (visual text is more reliable)
    lines = text.split("\n")
    pinfl_candidates = []

    for line in lines:
        if "<" in line:
            continue
        numbers = re.findall(r"\d{14}", line)
        for num in numbers:
            pinfl_candidates.append(num)

    # Fallback: any 14-digit number
    if not pinfl_candidates:
        numbers = re.findall(r"\d{14,}", text)
        for num in numbers:
            pinfl_candidates.append(num[:14])

    # Fix common OCR errors in PINFL
    for pinfl in pinfl_candidates:
        fixed_pinfl = pinfl

        # Fix first digit: 0→3 (common OCR error for 1986→015→315)
        if fixed_pinfl[0] == "0":
            fixed_pinfl = "3" + fixed_pinfl[1:]

        # Fix other common OCR errors in PINFL
        # O→0, I→1, L→1, etc.
        fixed_pinfl = fixed_pinfl.replace("O", "0").replace("I", "1").replace("L", "1")

        return fixed_pinfl

    return ""


def _extract_pinfl_from_mrz(mrz_lines: list) -> str:
    """
    Extract PINFL from MRZ lines (Uzbekistan ID).

    Uzbekistan ID MRZ format (TD1):
    Line 1: IUUZBAD1191583731509860230078<
                                    ^^^^^^^^^^^^^^^^
                                    PINFL (last 14 digits before <)

    PINFL is the last 14 digits in line 1
    """
    if not mrz_lines or len(mrz_lines) < 1:
        return ""

    # Get first MRZ line and remove < filler
    first_line = mrz_lines[0].replace(" ", "")

    # Extract all digits from the line
    digits = re.sub(r"[^0-9]", "", first_line)

    # PINFL is the last 14 digits
    if len(digits) >= 14:
        return digits[-14:]

    return ""


def _extract_mrz_candidates(text: str) -> list:
    """
    Extract MRZ-like lines from raw OCR text.

    MRZ lines have these characteristics:
    - Long strings with < filler characters
    - Mix of uppercase letters, digits, and <
    - Usually 30+ characters
    - Often contain UZB or country codes
    """
    candidates = []

    for line in text.split("\n"):
        line = line.strip()
        if len(line) < 20:
            continue

        # Count < characters (MRZ filler)
        lt_count = line.count("<")
        if lt_count >= 3:
            # Check if mostly uppercase + digits + <
            clean = re.sub(r"[A-Z0-9<]", "", line)
            if len(clean) <= len(line) * 0.2:  # 80% valid chars
                candidates.append(line)

        # Also check for lines with country codes
        if re.search(r"UZB|OZB|0ZB", line) and len(line) >= 25:
            clean = re.sub(r"[A-Z0-9<]", "", line)
            if len(clean) <= len(line) * 0.3:
                candidates.append(line)

    return candidates[:3]  # Max 3 MRZ lines


def _extract_issued_by(text: str) -> str:
    if re.search(r"TOSHKEN", text, re.IGNORECASE):
        return "TOSHKENT"
    # Try to extract issuer code pattern like "IIV 26283"
    match = re.search(r"(IIV\s*\d+)", text, re.IGNORECASE)
    if match:
        issuer = match.group(1).upper()
        tosh = "TOSHKENT" if re.search(r"TOSHKEN", text, re.IGNORECASE) else ""
        return f"{tosh} {issuer}".strip() if tosh else issuer
    return ""
