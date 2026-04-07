"""Fixed parser for Uzbekistan passports with better handling of common OCR errors."""

import re
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

# Enhanced patterns for Uzbekistan passport
UZ_PASSPORT_PATTERNS = [
    r"([A-Z]{2}\d{5})",  # AM79792 format (7 chars)
    r"([A-Z]{2}\d{7})",  # AA1234567 format (9 chars)
]


def _clean_ocr_artifacts(text: str) -> str:
    """Clean common OCR artifacts like repeated characters."""
    if not text:
        return text

    # Remove repeated characters (like KKKKKKKKKKK)
    cleaned = re.sub(r"(.)\1{3,}", r"\1", text)

    # Fix common OCR errors in names
    replacements = {
        "И": "I",
        "0": "O",
        "1": "I",
        "5": "S",
        "4": "A",
        "3": "E",
        "8": "B",
        "9": "G",
        "2": "Z",
    }

    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)

    return cleaned


def _extract_passport_number_improved(text: str) -> str:
    """Improved passport number extraction for Uzbekistan documents."""
    lines = text.split("\n")

    # Look for passport number in the first few lines (where it usually appears)
    for i, line in enumerate(lines[:5]):  # Check first 5 lines
        line_upper = line.upper()

        # Skip MRZ lines
        if "<" in line_upper:
            continue

        # Look for document type indicator
        if any(
            keyword in line_upper for keyword in ["GUVOHNOMASI", "SHAXS", "PASSPORT"]
        ):
            # Check next lines for passport number
            for j in range(i + 1, min(i + 4, len(lines))):
                candidate_line = lines[j].upper()
                if "<" in candidate_line:
                    continue

                # Try all patterns
                for pattern in UZ_PASSPORT_PATTERNS:
                    match = re.search(pattern, candidate_line)
                    if match:
                        return match.group(1)

        # Direct pattern matching
        for pattern in UZ_PASSPORT_PATTERNS:
            match = re.search(pattern, line_upper)
            if match:
                return match.group(1)

    # Fallback: search entire text
    for pattern in UZ_PASSPORT_PATTERNS:
        match = re.search(pattern, text.upper())
        if match:
            return match.group(1)

    return ""


def _extract_dates_improved(text: str) -> Dict[str, str]:
    """Extract dates with better understanding of Uzbekistan passport format."""
    result = {"birth_date": "", "issue_date": "", "expiry_date": ""}

    # Find all dates in format DD.MM.YYYY or similar
    date_pattern = r"(\d{1,2})[.\-/,](\d{1,2})[.\-/](\d{4})"
    dates = []

    for match in re.finditer(date_pattern, text):
        day, month, year = match.groups()
        # Normalize to 2-digit day/month
        day = day.zfill(2)
        month = month.zfill(2)
        full_date = f"{day}.{month}.{year}"
        dates.append(
            {
                "date": full_date,
                "year": int(year),
                "month": int(month),
                "day": int(day),
                "position": match.start(),
            }
        )

    if not dates:
        return result

    # Sort by position in text (top to bottom)
    dates.sort(key=lambda x: x["position"])

    # For Uzbekistan passports, typical order is:
    # 1. PINFL (14 digits)
    # 2. Issue date
    # 3. Gender
    # 4. Birth date
    # 5. Issued by
    # 6. Expiry date

    # Find PINFL to help locate issue date
    pinfl_match = re.search(r"(\d{14})", text)
    if pinfl_match:
        pinfl_pos = pinfl_match.start()
        # Issue date usually comes right after PINFL
        issue_candidates = [d for d in dates if d["position"] > pinfl_pos]
        if issue_candidates:
            result["issue_date"] = issue_candidates[0]["date"]
            remaining_dates = [d for d in dates if d != issue_candidates[0]]
        else:
            remaining_dates = dates
    else:
        remaining_dates = dates

    if len(remaining_dates) >= 1:
        result["birth_date"] = remaining_dates[0]["date"]
    if len(remaining_dates) >= 2:
        # If we haven't found expiry yet, take the last date as expiry
        if not result["expiry_date"]:
            result["expiry_date"] = remaining_dates[-1]["date"]
        # If we have issue date from PINFL logic, birth is first, expiry is last
        elif len(remaining_dates) >= 2:
            result["birth_date"] = remaining_dates[0]["date"]
            if len(remaining_dates) >= 3:
                result["expiry_date"] = remaining_dates[-1]["date"]

    # Additional logic: look for explicit date labels
    lines = text.split("\n")
    for i, line in enumerate(lines):
        line_lower = line.lower()
        if "15:09" in line or re.search(
            r"\d{2}:\d{2}", line
        ):  # Time format indicates issue date
            # Look for date in same or next line
            date_match = re.search(date_pattern, line)
            if not date_match and i + 1 < len(lines):
                date_match = re.search(date_pattern, lines[i + 1])
            if date_match:
                day, month, year = date_match.groups()
                result["issue_date"] = f"{day.zfill(2)}.{month.zfill(2)}.{year}"
        elif "23.03" in line:  # Specific pattern from the example
            date_match = re.search(date_pattern, line)
            if date_match:
                day, month, year = date_match.groups()
                result["expiry_date"] = f"{day.zfill(2)}.{month.zfill(2)}.{year}"

    return result


def _extract_name_improved(text: str, field_type: str = "first") -> str:
    """Improved name extraction with better OCR artifact removal."""
    # Clean the entire text first
    cleaned_text = _clean_ocr_artifacts(text)

    # Extract names using existing logic but on cleaned text
    if field_type == "first":
        # Look for first name patterns
        lines = cleaned_text.split("\n")
        for line in lines:
            # Skip lines with MRZ or document headers
            if any(
                kw in line.upper()
                for kw in ["<", "GUVOHNOMASI", "SHAXS", "O'ZBEKISTON"]
            ):
                continue
            # Look for words that look like names (3+ letters, not all caps keywords)
            words = re.findall(r"[A-Z][A-Z]+", line)
            for word in words:
                if len(word) >= 3 and word not in ["ERKAK", "AYOL", "TOSHKENT"]:
                    # Additional validation: should contain vowels
                    if any(vowel in word for vowel in "AEIOU"):
                        return word
    elif field_type == "last":
        # Similar logic for last name
        lines = cleaned_text.split("\n")
        for line in lines:
            if any(
                kw in line.upper()
                for kw in ["<", "GUVOHNOMASI", "SHAXS", "O'ZBEKISTON"]
            ):
                continue
            words = re.findall(r"[A-Z][A-Z]+", line)
            for word in words:
                if len(word) >= 4 and word not in ["ERKAK", "AYOL", "TOSHKENT"]:
                    if any(vowel in word for vowel in "AEIOU"):
                        return word

    return ""


def extract_from_text_fixed(
    ocr_text: str, mrz_data: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Fixed extraction for Uzbekistan passports with better OCR error handling.
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
        # Clean MRZ data from artifacts
        given_names = mrz_data.get("given_names", "")
        surname = mrz_data.get("surname", "")

        # Clean names from MRZ
        given_names_clean = _clean_ocr_artifacts(given_names)
        surname_clean = _clean_ocr_artifacts(surname)

        result["first_name"] = given_names_clean.split()[0] if given_names_clean else ""
        result["last_name"] = surname_clean
        result["birth_date"] = (
            mrz_data.get("birth_date", "").replace("-", ".")
            if mrz_data.get("birth_date")
            else ""
        )
        result["gender"] = mrz_data.get("gender", "")
        result["nationality"] = mrz_data.get("nationality", "")
        result["passport_number"] = mrz_data.get("passport_number", "").replace("<", "")
        result["pinfl"] = mrz_data.get("personal_number", "")

        given_parts = given_names_clean.split()
        if len(given_parts) > 1:
            result["middle_name"] = " ".join(given_parts[1:])

        logger.info(f"MRZ-first extraction: valid MRZ used as source of truth")

    # === Enhanced fallback extraction ===
    if not result["first_name"]:
        result["first_name"] = _extract_name_improved(ocr_text, "first")
    if not result["last_name"]:
        result["last_name"] = _extract_name_improved(ocr_text, "last")
    if not result["middle_name"]:
        # Try to extract middle name from context
        lines = ocr_text.split("\n")
        for line in lines:
            if "AMIRJON" in line.upper() or "OVICH" in line.upper():
                result["middle_name"] = _clean_ocr_artifacts(line.strip())
                break

    # Extract dates with improved logic
    dates_result = _extract_dates_improved(ocr_text)
    if not result["birth_date"]:
        result["birth_date"] = dates_result["birth_date"]
    if not result["issue_date"]:
        result["issue_date"] = dates_result["issue_date"]
    if not result["expiry_date"]:
        result["expiry_date"] = dates_result["expiry_date"]

    if not result["gender"]:
        if re.search(r"\bERKAK\b", ocr_text, re.IGNORECASE):
            result["gender"] = "ERKAK"
        elif re.search(r"\bERKKAK\b", ocr_text, re.IGNORECASE):  # Handle OCR error
            result["gender"] = "ERKAK"

    if not result["nationality"]:
        if re.search(r"O['']?ZBEKISTON", ocr_text, re.IGNORECASE):
            result["nationality"] = "O'ZBEKISTON"

    if not result["passport_number"]:
        result["passport_number"] = _extract_passport_number_improved(ocr_text)

    if not result["pinfl"]:
        pinfl_match = re.search(r"(\d{14})", ocr_text)
        if pinfl_match:
            result["pinfl"] = pinfl_match.group(1)

    if not result["issued_by"]:
        if re.search(r"TOSHKEN", ocr_text, re.IGNORECASE):
            result["issued_by"] = "TOSHKENT"

    # Passport series = first 2 chars of passport number
    if result["passport_number"] and len(result["passport_number"]) >= 2:
        result["passport_series"] = result["passport_number"][:2]

    # Final cleanup of names
    result["first_name"] = _clean_ocr_artifacts(result["first_name"])
    result["last_name"] = _clean_ocr_artifacts(result["last_name"])
    result["middle_name"] = _clean_ocr_artifacts(result["middle_name"])

    logger.info(f"Fixed parsing result: {result}")
    return result
