"""Validation engine: MRZ checksums, date formats, passport number validation, country codes."""

import re
from datetime import datetime
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

VALID_COUNTRY_CODES = {
    "UZB",
    "RUS",
    "KAZ",
    "KGZ",
    "TJK",
    "TKM",
    "USA",
    "GBR",
    "DEU",
    "FRA",
    "ITA",
    "ESP",
    "TUR",
    "CHN",
    "JPN",
    "KOR",
    "IND",
    "PAK",
    "AFG",
    "IRN",
    "ARE",
    "SAU",
    "EGY",
    "UKR",
    "BLR",
    "MDA",
    "AZE",
    "GEO",
    "ARM",
}


class ValidationEngine:
    """Comprehensive validation for passport OCR data."""

    def validate(self, data: Dict, mrz_data: Optional[Dict] = None) -> Dict:
        """Run all validation checks and return detailed results."""
        mrz_data = mrz_data or {}
        mrz_valid = bool(mrz_data.get("all_checks_valid") or mrz_data.get("valid"))

        checks = {
            "first_name": self._check_required(data.get("first_name")),
            "last_name": self._check_required(data.get("last_name")),
            "birth_date": self._validate_birth_date(data.get("birth_date", "")),
            "passport_number": self._validate_passport_number(
                data.get("passport_number", "")
            ),
            "pinfl": self._validate_pinfl(data.get("pinfl", "")),
            "gender": self._check_required(data.get("gender")),
            "nationality": self._validate_nationality(data.get("nationality", "")),
            "expiry_date": self._validate_expiry_date(
                data.get("expiry_date", ""), data.get("birth_date", "")
            ),
            "mrz_checksums": mrz_valid,
        }

        # Determine overall status
        critical = [
            checks["first_name"],
            checks["last_name"],
            checks["birth_date"],
            checks["passport_number"],
        ]
        all_critical_pass = all(critical)

        if mrz_valid and all_critical_pass:
            status = "valid"
        elif all_critical_pass:
            status = "valid"
        elif any(critical):
            status = "needs_review"
        else:
            status = "invalid"

        low_confidence_fields = [
            field
            for field, passed in checks.items()
            if not passed and field != "mrz_checksums"
        ]

        return {
            "status": status,
            "checks": checks,
            "mrz_valid": mrz_valid,
            "low_confidence_fields": low_confidence_fields,
            "all_critical_pass": all_critical_pass,
        }

    def _check_required(self, value: Optional[str]) -> bool:
        return bool(value and str(value).strip())

    def _validate_birth_date(self, date_str: str) -> bool:
        if not date_str:
            return False
        dt = self._parse_date(date_str)
        if dt is None:
            return False
        age = (datetime.now() - dt).days / 365.25
        return 0 < age < 150

    def _validate_expiry_date(self, expiry_str: str, birth_str: str) -> bool:
        if not expiry_str:
            return True  # Not always present
        dt = self._parse_date(expiry_str)
        if dt is None:
            return False
        if dt < datetime.now():
            return False
        if birth_str:
            birth_dt = self._parse_date(birth_str)
            if birth_dt and dt <= birth_dt:
                return False
        return True

    def _validate_passport_number(self, number: str) -> bool:
        if not number:
            return False
        cleaned = re.sub(r"\s", "", number)
        if re.match(r"^[A-Z]{2}\d{7}$", cleaned, re.IGNORECASE):
            return True
        if re.match(r"^\d{9}$", cleaned):
            return True
        return False

    def _validate_pinfl(self, pinfl: str) -> bool:
        if not pinfl:
            return False
        cleaned = re.sub(r"\D", "", pinfl)
        return len(cleaned) == 14

    def _validate_nationality(self, nationality: str) -> bool:
        if not nationality:
            return False
        nat_upper = nationality.upper().strip()
        if nat_upper in VALID_COUNTRY_CODES:
            return True
        if len(nat_upper) >= 3:
            return True
        return False

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None


validation_engine = ValidationEngine()
