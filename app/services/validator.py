import re
from datetime import datetime
from typing import Dict, Optional


class DataValidator:
    """Валидация и нормализация данных из Qwen VLM."""

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
        return False

    def normalize_date(self, date_str: str) -> str:
        """Нормализация даты к формату DD.MM.YYYY."""
        if not date_str:
            return ""

        formats = ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y%m%d"]
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%d.%m.%Y")
            except ValueError:
                continue
        return date_str

    def calculate_confidence(self, data: Dict) -> float:
        """Расчёт общей уверенности на основе заполненности и валидности полей."""
        filled = 0
        valid = 0
        total = 0

        # Обязательные поля
        for field in ["first_name", "last_name", "birth_date", "passport_number", "gender", "nationality"]:
            total += 1
            if data.get(field):
                filled += 1
                # Проверим валидность
                if field == "birth_date":
                    if self.validate_birth_date(data[field]):
                        valid += 1
                    else:
                        valid += 0.5
                elif field == "passport_number":
                    if self.validate_passport_number(data[field]):
                        valid += 1
                    else:
                        valid += 0.5
                else:
                    valid += 1

        # PINFL (не всегда есть, но если есть — важный сигнал)
        if data.get("pinfl"):
            total += 1
            filled += 1
            if self.validate_pinfl(data["pinfl"]):
                valid += 1
            else:
                valid += 0.3

        if total == 0:
            return 0.0

        # Комбинация заполненности и валидности
        fill_ratio = filled / total
        validity_ratio = valid / total

        confidence = 0.4 * fill_ratio + 0.6 * validity_ratio
        return round(min(confidence, 1.0), 2)

    def validate(self, data: Dict) -> Dict:
        """Валидация всех полей, извлечённых Qwen VLM."""
        normalized = dict(data)

        # Нормализация дат
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

        all_valid = (
            checks["passport_number"]
            and checks["birth_date"]
            and checks["gender"]
            and checks["first_name"]
            and checks["last_name"]
        )

        return {
            "normalized_data": normalized,
            "checks": checks,
            "all_valid": all_valid,
            "overall_confidence": self.calculate_confidence(normalized),
        }


validator = DataValidator()
