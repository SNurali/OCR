"""Test parser with real OCR output from Uzbekistan ID card - standalone version."""

import re
import sys
import os

# Load name lexicons directly
ca_path = os.path.join(
    os.path.dirname(__file__), "../app/services/name_lexicons/central_asia.py"
)
ca_mod = {}
exec(open(ca_path).read(), ca_mod)
CENTRAL_ASIA_FIRST_NAMES = ca_mod["FIRST_NAMES"]
CENTRAL_ASIA_SURNAMES = ca_mod["SURNAMES"]

pat_path = os.path.join(
    os.path.dirname(__file__), "../app/services/name_lexicons/patronymics.py"
)
pat_mod = {}
exec(open(pat_path).read(), pat_mod)
COMMON_PATRONYMICS = pat_mod["COMMON_PATRONYMICS"]

cis_path = os.path.join(
    os.path.dirname(__file__), "../app/services/name_lexicons/cis.py"
)
cis_mod = {}
exec(open(cis_path).read(), cis_mod)
CIS_FIRST_NAMES = cis_mod["FIRST_NAMES"]

eu_path = os.path.join(
    os.path.dirname(__file__), "../app/services/name_lexicons/europe_latam.py"
)
eu_mod = {}
exec(open(eu_path).read(), eu_mod)
EUROPE_LATAM_FIRST_NAMES = eu_mod["FIRST_NAMES"]

mena_path = os.path.join(
    os.path.dirname(__file__), "../app/services/name_lexicons/mena_asia.py"
)
mena_mod = {}
exec(open(mena_path).read(), mena_mod)
MENA_ASIA_FIRST_NAMES = mena_mod["FIRST_NAMES"]

COMMON_FIRST_NAMES = (
    CENTRAL_ASIA_FIRST_NAMES
    | CIS_FIRST_NAMES
    | EUROPE_LATAM_FIRST_NAMES
    | MENA_ASIA_FIRST_NAMES
)

# Try rapidfuzz
try:
    from rapidfuzz import fuzz

    HAS_FUZZ = True
except ImportError:
    HAS_FUZZ = False

# Inline the parser code with the lexicons
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
OCR_NAME_NOISE_PREFIXES = {"F", "K", "P", "I", "L", "J"}


def _fix_ocr_name_noise(name):
    if not name:
        return ""
    name = name.upper().strip()
    for prefix in sorted(OCR_NAME_NOISE_PREFIXES, key=len, reverse=True):
        if name.startswith(prefix) and len(name) > len(prefix) + 2:
            rest = name[len(prefix) :]
            if rest[0] in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                return rest
    return name


def normalize_name(name):
    if not name:
        return ""
    name = name.upper().strip()
    name = _fix_ocr_name_noise(name)
    name = name.replace("0", "O")
    name = name.replace("1", "I")
    name = name.replace("5", "S")
    name = name.replace("4", "A")
    name = name.replace("3", "E")
    name = name.replace("8", "B")
    name = name.replace("9", "G")
    name = name.replace("2", "Z")
    if name.startswith("M") and len(name) >= 4:
        alt = "N" + name[1:]
        if alt in COMMON_FIRST_NAMES and name not in COMMON_FIRST_NAMES:
            name = alt
    name = re.sub(r"[^A-Z\s]", "", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()


def _extract_first_name(text):
    for line in text.split("\n"):
        tokens = re.split(r"[ <0-9/]+", line.upper())
        for token in tokens:
            cleaned = re.sub(r"[^A-Z]", "", token)
            if len(cleaned) >= 3 and cleaned in COMMON_FIRST_NAMES:
                return normalize_name(cleaned)

    if HAS_FUZZ:
        for line in text.split("\n"):
            tokens = re.split(r"[ <0-9/]+", line.upper())
            for token in tokens:
                cleaned = re.sub(r"[^A-Z]", "", token)
                if len(cleaned) < 3:
                    continue
                for prefix in sorted(OCR_NAME_NOISE_PREFIXES, key=len, reverse=True):
                    if cleaned.startswith(prefix) and len(cleaned) > len(prefix) + 2:
                        stripped = cleaned[len(prefix) :]
                        if stripped in COMMON_FIRST_NAMES:
                            return normalize_name(stripped)
                        if (
                            stripped.startswith("M")
                            and not stripped.startswith("MU")
                            and not stripped.startswith("MA")
                        ):
                            alt = "N" + stripped[1:]
                            if alt in COMMON_FIRST_NAMES:
                                return normalize_name(alt)
                best_name = None
                best_score = 0
                for name in COMMON_FIRST_NAMES:
                    if abs(len(name) - len(cleaned)) > 3:
                        continue
                    score = fuzz.ratio(cleaned, name)
                    corrected = cleaned.replace("M", "N")
                    score2 = fuzz.ratio(corrected, name)
                    score = max(score, score2)
                    if score > best_score and score >= 70:
                        best_score = score
                        best_name = name
                if best_name:
                    return normalize_name(best_name)
    return ""


def _extract_last_name(text):
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
            if i + 1 < len(lines):
                next_tokens = re.split(r"[ <0-9/\"']+", lines[i + 1].upper())
                for nt in next_tokens:
                    nt_clean = re.sub(r"[^A-Z]", "", nt)
                    if nt_clean in COMMON_FIRST_NAMES:
                        return normalize_name(token_clean)
            if i > 0:
                prev_upper = lines[i - 1].upper()
                if any(
                    kw in prev_upper
                    for kw in ["GUVOHNOMASI", "SHAXS", "PASSPORT", "ID"]
                ):
                    return normalize_name(token_clean)

    if HAS_FUZZ:
        all_surnames = CENTRAL_ASIA_SURNAMES | COMMON_FIRST_NAMES
        for line in lines:
            tokens = re.split(r"[ <0-9/\"']+", line.upper())
            for token in tokens:
                token_clean = re.sub(r"[^A-Z]", "", token)
                if len(token_clean) < 5:
                    continue
                for prefix in sorted(OCR_NAME_NOISE_PREFIXES, key=len, reverse=True):
                    if (
                        token_clean.startswith(prefix)
                        and len(token_clean) > len(prefix) + 3
                    ):
                        stripped = token_clean[len(prefix) :]
                        if stripped in all_surnames:
                            return normalize_name(stripped)
                for surname in all_surnames:
                    if abs(len(surname) - len(token_clean)) > 3:
                        continue
                    if fuzz.ratio(token_clean, surname) >= 75:
                        return normalize_name(surname)

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


def _extract_patronymic(text):
    for line in text.split("\n"):
        tokens = re.split(r"[ <0-9/\"']+", line.upper())
        for token in tokens:
            if token in COMMON_PATRONYMICS:
                return normalize_name(token)
            for p in sorted(COMMON_PATRONYMICS, key=len, reverse=True):
                if p in token:
                    return normalize_name(p)

    if HAS_FUZZ:
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
    return ""


def _extract_gender(text):
    if re.search(r"\bERKAK\b", text, re.IGNORECASE):
        return "ERKAK"
    if re.search(r"\bAYOL\b", text, re.IGNORECASE):
        return "AYOL"
    if HAS_FUZZ:
        for line in text.split("\n"):
            tokens = re.split(r"[ <0-9/\"']+", line.upper())
            tokens = [t for t in tokens if 4 <= len(t) <= 8]
            for token in tokens:
                if fuzz.ratio(token, "ERKAK") >= 70:
                    return "ERKAK"
                if fuzz.ratio(token, "AYOL") >= 70:
                    return "AYOL"
    return ""


def _extract_nationality(text):
    if re.search(r"O['']?ZBEKISTON", text, re.IGNORECASE):
        return "O'ZBEKISTON"
    return ""


def _extract_passport_number(text):
    match = re.search(r"([A-Z]{2}\d{7})", text)
    if match:
        return match.group(1).upper()
    lines = text.split("\n")
    candidates_7 = []
    for line in lines:
        if "<" in line:
            continue
        matches = re.findall(r"([A-Z]{2}\d{5})", line)
        for m in matches:
            candidates_7.append(m)
    if candidates_7:
        for i, line in enumerate(lines):
            if "<" in line:
                continue
            for c in candidates_7:
                if c in line:
                    context = "\n".join(lines[max(0, i - 3) : i + 3])
                    if any(
                        kw in context
                        for kw in ["GUVOHNOMASI", "SHAXS", "TOSHKEN", "ERKAK"]
                    ):
                        return c
        return candidates_7[0]
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


def _extract_pinfl(text):
    lines = text.split("\n")
    for line in lines:
        if "<" in line:
            continue
        numbers = re.findall(r"\d{14}", line)
        for num in numbers:
            return num
    numbers = re.findall(r"\d{14,}", text)
    for num in numbers:
        return num[:14]
    return ""


def _extract_pinfl(text):
    numbers = re.findall(r"\d{14,}", text)
    for num in numbers:
        candidate = num[:14]
        return candidate
    return ""


def _extract_pinfl(text):
    numbers = re.findall(r"\d{14,}", text)
    for num in numbers:
        candidate = num[:14]
        if candidate[0] in "123":
            return candidate
        if candidate[0] == "9":
            return "3" + candidate[1:]
    all_nums = re.findall(r"[A-Za-z]*(\d{14})[A-Za-z]*", text)
    for num in all_nums:
        if num[0] in "123":
            return num
        if num[0] == "9":
            return "3" + num[1:]
    return ""


def _extract_issued_by(text):
    if re.search(r"TOSHKEN", text, re.IGNORECASE):
        return "TOSHKENT"
    match = re.search(r"(IIV\s*\d+)", text, re.IGNORECASE)
    if match:
        issuer = match.group(1).upper()
        tosh = "TOSHKENT" if re.search(r"TOSHKEN", text, re.IGNORECASE) else ""
        return f"{tosh} {issuer}".strip() if tosh else issuer
    return ""


def _parse_date_safe(ds):
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


def _classify_dates(dates):
    result = {"birth_date": "", "issue_date": "", "expiry_date": ""}
    if not dates:
        return result
    from datetime import datetime

    parsed = []
    for d in dates:
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


def extract_from_text(ocr_text, mrz_data=None):
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

    if mrz_valid:
        result["first_name"] = normalize_name(
            mrz_data.get("given_names", "").split()[0]
            if mrz_data.get("given_names")
            else ""
        )
        result["last_name"] = normalize_name(mrz_data.get("surname", ""))
        result["birth_date"] = _parse_date_safe(mrz_data.get("birth_date", "")) or ""
        result["gender"] = mrz_data.get("gender", "")
        result["nationality"] = mrz_data.get("nationality", "")
        result["passport_number"] = mrz_data.get("passport_number", "").replace("<", "")
        result["pinfl"] = mrz_data.get("personal_number", "")
        given_parts = mrz_data.get("given_names", "").split()
        if len(given_parts) > 1:
            result["middle_name"] = normalize_name(" ".join(given_parts[1:]))

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

    all_dates = re.findall(r"(\d{2}[.\-/,]\d{2}[.\-/]\d{4})", ocr_text)
    all_dates = [d.replace(",", ".") for d in all_dates]
    classified = _classify_dates(all_dates)
    if not result["issue_date"]:
        result["issue_date"] = classified.get("issue_date", "")
    if not result["expiry_date"]:
        result["expiry_date"] = classified.get("expiry_date", "")
    if not result["issued_by"]:
        result["issued_by"] = _extract_issued_by(ocr_text)

    if result["passport_number"] and len(result["passport_number"]) >= 2:
        result["passport_series"] = result["passport_number"][:2]

    return result


RAW_OCR_TEXT = """OZBEKISTON RESPUBLIKASI
SHAXS GUVOHNOMASI
5
FSULAYMAMOV
KmURALI
AMIRJONOVIC
71Daln n
15,09.1996
ERKAK
Пlata neNi
24.03.2022
0 ZHEKISTON
{ala demplry
23,03.2032
4DII91583
AN79792
91509860230078
TOSHKEN
IIV 26283
IUUZBAD11 915 837315 0986 0230078 <
8 6 0 915 5 М3 203237XXXUZB <<<<<<<< 0
S U LAY MAN 0V< <NU RALI<<<<<<<<<<< <"""


def test_parser():
    result = extract_from_text(RAW_OCR_TEXT)

    print("=" * 60)
    print("PARSER RESULTS")
    print("=" * 60)

    expected = {
        "last_name": "SULAYMANOV",
        "first_name": "NURALI",
        "middle_name": "AMIRJONOVICH",
        "birth_date": "15.09.1996",
        "gender": "ERKAK",
        "nationality": "O'ZBEKISTON",
        "passport_number": "AN79792",
        "passport_series": "AN",
        "issue_date": "24.03.2022",
        "expiry_date": "23.03.2032",
        "issued_by": "TOSHKENT",
        "pinfl": "91509860230078",
    }

    passed = 0
    failed = 0
    for field, exp_val in expected.items():
        actual = result.get(field, "")
        status = "PASS" if actual == exp_val else "FAIL"
        if actual != exp_val:
            failed += 1
        else:
            passed += 1
        print(f"{status} {field:20s} expected={exp_val:25s} actual={actual}")

    print("=" * 60)
    print(f"Passed: {passed}/{len(expected)}")
    print(f"Failed: {failed}/{len(expected)}")

    print("\n" + "=" * 60)
    print("NORMALIZE_NAME TESTS")
    print("=" * 60)
    tests = [
        ("FSULAYMAMOV", "SULAYMAMOV"),
        ("KmURALI", "MURALI"),
        ("AMIRJONOVIC", "AMIRJONOVIC"),
    ]
    for inp, expected_norm in tests:
        result_norm = normalize_name(inp)
        status = "PASS" if result_norm == expected_norm else "FAIL"
        print(
            f"{status} normalize_name('{inp}') = '{result_norm}' (expected: '{expected_norm}')"
        )


if __name__ == "__main__":
    test_parser()
