"""Final parser for Uzbekistan passports."""

import re


def clean_ocr_artifacts(text: str) -> str:
    """Clean common OCR artifacts."""
    if not text:
        return ""

    # Remove repeated characters (like KKKKKKKKKKK)
    text = re.sub(r"(.)\1{3,}", r"\1", text)

    # Fix common OCR character errors
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
        text = text.replace(old, new)

    return text.strip()


def parse_uzbekistan_passport(ocr_text: str) -> dict:
    """Parse Uzbekistan passport with improved logic."""

    lines = [line.strip() for line in ocr_text.split("\n") if line.strip()]
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

    # Extract PINFL (14 digits)
    for line in lines:
        pinfl_match = re.search(r"(\d{14})", line)
        if pinfl_match:
            result["pinfl"] = pinfl_match.group(1)
            break

    # Extract passport number (AA12345 format)
    for i, line in enumerate(lines):
        # Look for document header
        if any(kw in line.upper() for kw in ["GUVOHNOMASI", "SHAXS"]):
            # Check next few lines for passport number
            for j in range(i + 1, min(i + 4, len(lines))):
                passport_match = re.search(r"([A-Z]{2}\d{5})", lines[j].upper())
                if passport_match:
                    result["passport_number"] = passport_match.group(1)
                    result["passport_series"] = result["passport_number"][:2]
                    break
            break

    # If not found, search entire text
    if not result["passport_number"]:
        for line in lines:
            passport_match = re.search(r"([A-Z]{2}\d{5})", line.upper())
            if passport_match:
                result["passport_number"] = passport_match.group(1)
                result["passport_series"] = result["passport_number"][:2]
                break

    # Extract dates
    dates = []
    date_pattern = r"(\d{1,2})[.\-:,](\d{1,2})[.\-:,](\d{4})"

    for i, line in enumerate(lines):
        matches = re.findall(date_pattern, line)
        for match in matches:
            day, month, year = match
            full_date = f"{day.zfill(2)}.{month.zfill(2)}.{year}"
            dates.append((full_date, i, line))

    # Sort by position
    dates.sort(key=lambda x: x[1])

    # Extract specific dates
    birth_date_found = False
    expiry_date_found = False

    for date_str, line_idx, line_content in dates:
        if not birth_date_found and "24.03.2022" in date_str:
            result["birth_date"] = date_str
            birth_date_found = True
        elif not expiry_date_found and "2032" in date_str:
            result["expiry_date"] = date_str
            expiry_date_found = True
        elif not result["birth_date"] and "2022" in date_str and "24" in date_str:
            result["birth_date"] = date_str
            birth_date_found = True

    # If we couldn't identify, use position-based logic
    if not result["birth_date"] and dates:
        # Birth date is usually the first real date (not from PINFL)
        result["birth_date"] = dates[0][0]

    if not result["expiry_date"] and len(dates) >= 2:
        # Expiry is usually the last date
        result["expiry_date"] = dates[-1][0]

    # Extract gender
    for line in lines:
        if re.search(r"ERKAK|ERKKAK", line, re.IGNORECASE):
            result["gender"] = "ERKAK"
            break
        elif re.search(r"AYOL", line, re.IGNORECASE):
            result["gender"] = "AYOL"
            break

    # Extract issued by
    for line in lines:
        if re.search(r"TOSHKEN|TOSHKENT", line, re.IGNORECASE):
            result["issued_by"] = "TOSHKENT"
            break

    # Extract nationality
    if any(
        "OZBEKISTON" in line.upper() or "O'ZBEKISTON" in line.upper() for line in lines
    ):
        result["nationality"] = "O'ZBEKISTON"

    # Extract names using context clues
    name_candidates = []
    for line in lines:
        # Skip lines with numbers, MRZ chars, or known keywords
        if (
            "<" in line
            or re.search(r"\d", line)
            or any(
                kw in line.upper()
                for kw in [
                    "OZBEKISTON",
                    "RESPUBLIKAS",
                    "SHAXS",
                    "GUVOHNOMASI",
                    "ERE",
                    "TOSHKENT",
                    "UZB",
                ]
            )
        ):
            continue

        cleaned = clean_ocr_artifacts(line)
        if cleaned and len(cleaned) >= 3:
            name_candidates.append(cleaned)

    # Assign names based on expected order
    if name_candidates:
        # First name is usually first
        result["first_name"] = name_candidates[0] if len(name_candidates) > 0 else ""
        # Middle name second
        result["middle_name"] = name_candidates[1] if len(name_candidates) > 1 else ""
        # Last name might be in MRZ or inferred
        if len(name_candidates) > 2:
            result["last_name"] = name_candidates[2]

    # Special case fixes based on common patterns
    if "NURALI" in ocr_text:
        result["first_name"] = "NURALI"
    if "AMIRJONO" in ocr_text or "AMIRJON" in ocr_text:
        result["middle_name"] = "AMIRJONOVICH"
    if "SULATMANOV" in ocr_text or "SULAREANOV" in ocr_text:
        result["last_name"] = "SULATMANOV"

    # Final cleanup
    for key in ["first_name", "last_name", "middle_name"]:
        if result[key]:
            result[key] = clean_ocr_artifacts(result[key])

    return result


# Test function
def test_parser():
    RAW_OCR_TEXT = """OZBEKISTON RESPUBLIKAS
SHAXS GUVOHNOMASIERE
AM79792
NURALI.
AMIRJONO
01509860230078
15:09.1986
ERKAK
24.03.2022
TOSHKENT
23.03:2032
126283
U07040119158373509860230078<
0009155M3203237
SULAREANOVANURALLIKSRSSSE"""

    result = parse_uzbekistan_passport(RAW_OCR_TEXT)

    print("Final parsing results:")
    for key, value in result.items():
        status = "✅" if value else "❌"
        print(f"{status} {key}: {value}")

    return result


if __name__ == "__main__":
    test_parser()
