import re
from datetime import datetime
from typing import Dict, Optional


class DataValidator:
    """Валидация и нормализация извлечённых данных."""

    def validate_pinfl(self, pinfl: str) -> bool:
        """ПИНФЛ = строго 14 цифр."""
        if not pinfl:
            return False
        cleaned = re.sub(r"\D", "", pinfl)
        return len(cleaned) == 14

    def validate_date(self, date_str: str) -> bool:
        """Валидация даты."""
        if not date_str:
            return False

        formats = ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y"]
        for fmt in formats:
            try:
                datetime.strptime(date_str, fmt)
                return True
            except ValueError:
                continue
        return False

    def validate_birth_date(self, date_str: str) -> bool:
        """Логическая проверка даты рождения."""
        if not self.validate_date(date_str):
            return False

        formats = ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y"]
        for fmt in formats:
            try:
                birth_date = datetime.strptime(date_str, fmt)
                now = datetime.now()
                age = (now - birth_date).days / 365.25

                return 0 < age < 150
            except ValueError:
                continue
        return False

    def validate_expiry_date(
        self, expiry_str: str, birth_str: Optional[str] = None
    ) -> bool:
        """Валидация даты окончания документа."""
        if not self.validate_date(expiry_str):
            return False

        formats = ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y"]
        for fmt in formats:
            try:
                expiry = datetime.strptime(expiry_str, fmt)
                if expiry < datetime.now():
                    return False

                if birth_str and self.validate_date(birth_str):
                    for bfmt in formats:
                        try:
                            birth = datetime.strptime(birth_str, bfmt)
                            if expiry <= birth:
                                return False
                        except ValueError:
                            continue
                return True
            except ValueError:
                continue
        return False

    def validate_passport_number(self, number: str) -> bool:
        """Валидация номера паспорта."""
        if not number:
            return False

        cleaned = re.sub(r"\s", "", number)

        if re.match(r"^[A-Z]{2}\d{7}$", cleaned, re.IGNORECASE):
            return True
        if re.match(r"^\d{9}$", cleaned):
            return True
        if re.match(r"^\d{2}\d{2}\d{6}$", cleaned):
            return True

        return False

    def normalize_date(self, date_str: str) -> str:
        """Нормализация даты к формату DD.MM.YYYY."""
        if not date_str:
            return ""

        formats = [
            ("%Y-%m-%d", None),
            ("%d.%m.%Y", None),
            ("%d/%m/%Y", None),
            ("%d-%m-%Y", None),
            ("%Y%m%d", None),
        ]

        for fmt, _ in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%d.%m.%Y")
            except ValueError:
                continue

        return date_str

    def calculate_confidence(
        self, data: Dict, mrz_valid: bool, ocr_confidence: float
    ) -> float:
        """Расчёт общей уверенности распознавания."""
        score = 0.0
        max_score = 0.0

        fields = [
            "first_name",
            "last_name",
            "birth_date",
            "passport_number",
            "nationality",
            "gender",
        ]

        for field in fields:
            max_score += 1.0
            if data.get(field):
                score += 0.7

        if mrz_valid:
            score += 2.0
        max_score += 2.0

        score += ocr_confidence * 1.0
        max_score += 1.0

        if self.validate_pinfl(data.get("pinfl", "")):
            score += 0.5
        max_score += 0.5

        final_score = score / max_score
        return round(min(final_score, 1.0), 2)

    def validate(
        self,
        data: Dict,
        mrz_data: Optional[Dict] = None,
        ocr_confidence: float = 0.0,
    ) -> Dict:
        mrz_data = mrz_data or {}
        normalized = dict(data)

        for field in ("birth_date", "issue_date", "expiry_date"):
            normalized[field] = self.normalize_date(str(normalized.get(field) or ""))

        checks = {
            "first_name": bool(normalized.get("first_name")),
            "last_name": bool(normalized.get("last_name")),
            "middle_name": bool(normalized.get("middle_name")),
            "birth_date": self.validate_birth_date(normalized["birth_date"])
            if normalized.get("birth_date")
            else False,
            "issue_date": self.validate_date(normalized["issue_date"])
            if normalized.get("issue_date")
            else False,
            "expiry_date": self.validate_expiry_date(
                normalized["expiry_date"],
                normalized.get("birth_date"),
            )
            if normalized.get("expiry_date")
            else False,
            "passport_number": self.validate_passport_number(
                normalized.get("passport_number", "")
            ),
            "pinfl": self.validate_pinfl(normalized.get("pinfl", ""))
            if normalized.get("pinfl")
            else False,
            "gender": bool(normalized.get("gender")),
            "nationality": bool(normalized.get("nationality")),
            "issued_by": bool(normalized.get("issued_by")),
        }

        mrz_valid = bool(mrz_data.get("all_checks_valid") or mrz_data.get("valid"))
        all_valid = (
            checks["passport_number"]
            and checks["birth_date"]
            and (mrz_valid or checks["expiry_date"] or checks["pinfl"])
        )

        return {
            "normalized_data": normalized,
            "checks": checks,
            "mrz_valid": mrz_valid,
            "all_valid": all_valid,
            "overall_confidence": self.calculate_confidence(
                normalized,
                mrz_valid,
                ocr_confidence,
            ),
        }


validator = DataValidator()
