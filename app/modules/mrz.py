"""MRZ extraction and parsing module.

MRZ-first logic: MRZ data is the source of truth when valid.
"""

import re
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class MRZParser:
    """Parses Machine Readable Zone (MRZ) for passports and ID cards."""

    CHECK_DIGITS = {str(i): i for i in range(10)}
    CHECK_DIGITS.update({chr(i): i - 55 for i in range(65, 91)})
    CHECK_DIGITS["<"] = 0

    WEIGHTS = [7, 3, 1]

    def __init__(self):
        self.mrz_pattern_td3 = re.compile(
            r"^[A-Z<]{2}[A-Z0-9<]{9}\d[A-Z0-9<]{14}\d{7}[MF<]\d{7}[A-Z0-9<]{14}\d{7}\d$"
        )
        self.mrz_pattern_td1 = re.compile(
            r"^[A-Z<]{2}[A-Z0-9<]{9}\d{7}[A-Z0-9<]{15}\d$"
        )

    def validate_check_digit(self, data: str, check_digit: str) -> bool:
        if not data or not check_digit:
            return False
        total = 0
        for i, char in enumerate(data):
            value = self.CHECK_DIGITS.get(char.upper(), 0)
            weight = self.WEIGHTS[i % 3]
            total += value * weight
        calculated = total % 10
        expected = int(check_digit) if check_digit.isdigit() else 0
        return calculated == expected

    def parse_td3(self, line1: str, line2: str) -> Dict:
        """Parse TD3 format (passport, 2 lines of 44 chars)."""
        line1 = line1.strip().upper()
        line2 = line2.strip().upper()

        if len(line1) < 44 or len(line2) < 44:
            return {"valid": False, "error": "Invalid line length"}

        surname_raw = line1[5:44]
        if "<<" in surname_raw:
            parts = surname_raw.split("<<", 1)
            surname = parts[0].replace("<", " ").strip()
            given_names = parts[1].replace("<", " ").strip() if len(parts) > 1 else ""
        elif "<" in surname_raw:
            parts = surname_raw.split("<", 1)
            surname = parts[0].strip()
            given_names = parts[1].replace("<", " ").strip()
        else:
            surname = surname_raw.replace("<", " ").strip()
            given_names = ""

        birth_raw = line2[13:19]
        expiry_raw = line2[21:27]

        passport_check = self.validate_check_digit(line2[0:9], line2[9])
        birth_check = self.validate_check_digit(birth_raw, line2[19])
        expiry_check = self.validate_check_digit(expiry_raw, line2[26])
        composite_check = self.validate_check_digit(
            line2[0:10] + line2[13:20] + line2[21:43], line2[28]
        )

        all_valid = all([passport_check, birth_check, expiry_check, composite_check])

        return {
            "valid": all_valid,
            "type": "TD3",
            "document_type": line1[0:2],
            "issuing_country": line1[2:5],
            "surname": surname,
            "given_names": given_names,
            "passport_number": line2[0:9].replace("<", ""),
            "nationality": line2[10:13],
            "birth_date": self._format_date(birth_raw),
            "gender": "M" if line2[20] == "M" else ("F" if line2[20] == "F" else ""),
            "expiry_date": self._format_date(expiry_raw),
            "personal_number": line2[28:42].replace("<", ""),
            "line1": line1,
            "line2": line2,
            "passport_check_valid": passport_check,
            "birth_check_valid": birth_check,
            "expiry_check_valid": expiry_check,
            "composite_check_valid": composite_check,
            "all_checks_valid": all_valid,
        }

    def parse_td1(self, line1: str, line2: str, line3: str) -> Dict:
        """Parse TD1 format (ID card, 3 lines of 30 chars)."""
        line1 = line1.strip().upper()
        line2 = line2.strip().upper()
        line3 = line3.strip().upper()

        if len(line1) < 30 or len(line2) < 30 or len(line3) < 30:
            return {"valid": False, "error": "Invalid line length"}

        birth_raw = line2[0:6]
        expiry_raw = line2[8:14]

        passport_check = self.validate_check_digit(line1[5:14], line1[14])
        birth_check = self.validate_check_digit(birth_raw, line2[6])
        expiry_check = self.validate_check_digit(expiry_raw, line2[14])

        personal_from_line1 = line1[15:30].replace("<", "")
        personal_number = (
            personal_from_line1
            if personal_from_line1
            else line2[18:29].replace("<", "")
        )

        surname = ""
        given_names = ""
        if "<<" in line3:
            parts = line3.split("<<", 1)
            surname = parts[0].replace("<", " ").strip()
            given_names = parts[1].replace("<", " ").strip() if len(parts) > 1 else ""

        composite_data = line1[5:30] + line2[0:7] + line2[8:15] + line2[18:29]
        composite_check = self.validate_check_digit(composite_data, line2[29])

        all_valid = all([passport_check, birth_check, expiry_check, composite_check])

        nationality = line2[15:18]
        if nationality in {"XXX", "<<<", ""}:
            fallback = line2[18:21]
            if re.match(r"^[A-Z]{3}$", fallback):
                nationality = fallback

        return {
            "valid": all_valid,
            "type": "TD1",
            "document_type": line1[0:2],
            "issuing_country": line1[2:5],
            "passport_number": line1[5:14].replace("<", ""),
            "nationality": nationality,
            "birth_date": self._format_date(birth_raw),
            "gender": "M" if line2[7] == "M" else ("F" if line2[7] == "F" else ""),
            "expiry_date": self._format_date(expiry_raw),
            "surname": surname,
            "given_names": given_names,
            "personal_number": personal_number,
            "line1": line1,
            "line2": line2,
            "line3": line3,
            "passport_check_valid": passport_check,
            "birth_check_valid": birth_check,
            "expiry_check_valid": expiry_check,
            "composite_check_valid": composite_check,
            "all_checks_valid": all_valid,
        }

    def _format_date(self, date_str: str) -> str:
        if len(date_str) != 6 or not date_str.isdigit():
            return date_str
        year = int(date_str[0:2])
        month = date_str[2:4]
        day = date_str[4:6]
        full_year = 2000 + year if year < 50 else 1900 + year

        from datetime import datetime

        try:
            datetime(full_year, int(month), int(day))
        except ValueError:
            return ""
        return f"{full_year}-{month}-{day}"

    def _clean_mrz_line(self, line: str) -> str:
        line = (
            line.replace("М", "M")
            .replace("О", "O")
            .replace("С", "C")
            .replace("А", "A")
            .replace("В", "B")
            .replace("Е", "E")
            .replace("Н", "H")
            .replace("К", "K")
            .replace("Р", "P")
            .replace("Т", "T")
            .replace("Х", "X")
        )
        raw = re.sub(r"[^A-Z0-9< ]", "", line.upper())
        cleaned = re.sub(r"4", "<", raw)
        spaceless = cleaned.replace(" ", "")

        if 28 <= len(spaceless) <= 32:
            return spaceless[:30]
        elif 42 <= len(spaceless) <= 46:
            return spaceless[:44]
        return raw.replace(" ", "<")

    def _is_valid_mrz_line(self, line: str) -> bool:
        """Check if a line looks like a real MRZ line."""
        if len(line) < 28:
            return False
        mrz_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<")
        if not all(c in mrz_chars for c in line):
            return False
        filler_ratio = line.count("<") / len(line)
        # TD1 line 1 starts with I/P and has few fillers - that's normal
        if line[0] in ("I", "P", "A", "C", "V") and len(line) >= 28:
            return True
        if filler_ratio < 0.15:
            return False
        if re.match(r"^[<]{10,}", line):
            return False
        return True

    def extract_from_text(self, full_text: str) -> Tuple[List[str], Optional[Dict]]:
        """Extract MRZ lines from full OCR text."""
        lines = full_text.split("\n")
        mrz_lines = []

        for line in lines:
            cleaned = self._clean_mrz_line(line)
            if self._is_valid_mrz_line(cleaned):
                mrz_lines.append(cleaned)

        # TD1: try all combinations of 3 lines ~30 chars
        if len(mrz_lines) >= 3:
            td30 = [l for l in mrz_lines if 28 <= len(l) <= 32]
            if len(td30) >= 3:
                from itertools import combinations

                best_parsed = None
                best_score = -1
                for combo in combinations(td30, 3):
                    parsed = self.parse_td1(combo[0], combo[1], combo[2])
                    checks = sum(
                        [
                            parsed.get("passport_check_valid", False),
                            parsed.get("birth_check_valid", False),
                            parsed.get("expiry_check_valid", False),
                            parsed.get("composite_check_valid", False),
                        ]
                    )
                    has_name = (
                        1 if parsed.get("surname") and len(parsed["surname"]) > 2 else 0
                    )
                    score = checks * 10 + has_name * 5
                    if parsed.get("all_checks_valid"):
                        score += 100
                    if score > best_score:
                        best_score = score
                        best_parsed = (list(combo), parsed)
                if best_parsed and best_score > 0:
                    return best_parsed[0], best_parsed[1]

        # TD3: 2 lines of ~44 chars
        if len(mrz_lines) >= 2:
            td44 = [l for l in mrz_lines if len(l) >= 42]
            if len(td44) >= 2:
                parsed = self.parse_td3(td44[-2], td44[-1])
                if parsed.get("valid"):
                    return [td44[-2], td44[-1]], parsed

        # Fallback: try any 3 lines for TD1
        if len(mrz_lines) >= 3:
            from itertools import combinations

            best_parsed = None
            best_score = -1
            for combo in combinations(mrz_lines, 3):
                parsed = self.parse_td1(combo[0], combo[1], combo[2])
                checks = sum(
                    [
                        parsed.get("passport_check_valid", False),
                        parsed.get("birth_check_valid", False),
                    ]
                )
                has_name = (
                    1 if parsed.get("surname") and len(parsed["surname"]) > 2 else 0
                )
                score = checks * 10 + has_name * 5
                if parsed.get("all_checks_valid"):
                    score += 100
                if score > best_score:
                    best_score = score
                    best_parsed = (list(combo), parsed)
            if best_parsed and best_score > 0:
                return best_parsed[0], best_parsed[1]

        if mrz_lines:
            return mrz_lines, self._parse_partial(mrz_lines)

        return [], None

    def _detect_and_parse(self, lines: list) -> Dict:
        cleaned = [l.strip().upper() for l in lines if l.strip()]
        if not cleaned:
            return {"valid": False, "error": "No MRZ lines found"}
        if len(cleaned) >= 2 and len(cleaned[0]) >= 44:
            return self.parse_td3(cleaned[0], cleaned[1])
        elif len(cleaned) >= 3 and len(cleaned[0]) >= 28:
            return self.parse_td1(cleaned[0], cleaned[1], cleaned[2])
        return {"valid": False, "error": "Cannot determine MRZ format"}

    def _parse_partial(self, mrz_lines: list) -> Dict:
        result = {"valid": False, "surname": "", "given_names": "", "partial": True}
        for line in mrz_lines:
            if "<<" not in line and "<<" not in line.replace("0", "O"):
                continue
            cleaned = re.sub(r"0", "O", line)
            cleaned = re.sub(r"[46]", "<", cleaned)
            parts = cleaned.split("<<", 1)
            surname = parts[0].replace("<", " ").strip()
            given = parts[1].replace("<", " ").strip() if len(parts) > 1 else ""
            if surname and len(surname) >= 2:
                result["surname"] = surname
            if given and len(given) >= 2:
                result["given_names"] = given
            if result["surname"] or result["given_names"]:
                return result
        return result


mrz_parser = MRZParser()
