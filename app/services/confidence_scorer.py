from typing import Dict, Optional


class ConfidenceScorer:
    """Multi-level confidence scoring."""

    FIELD_WEIGHTS = {
        "first_name": 0.12,
        "last_name": 0.12,
        "birth_date": 0.15,
        "gender": 0.05,
        "nationality": 0.08,
        "passport_number": 0.18,
        "expiry_date": 0.10,
        "pinfl": 0.20,
    }

    def score_fields(
        self,
        extracted: Dict,
        mrz_parsed: Optional[Dict],
        ocr_confidence: float,
    ) -> Dict[str, float]:
        field_scores = {}

        mrz_valid = mrz_parsed.get("valid", False) if mrz_parsed else False

        for field, weight in self.FIELD_WEIGHTS.items():
            value = extracted.get(field, "")
            score = self._score_field(
                field, value, mrz_parsed, mrz_valid, ocr_confidence
            )
            field_scores[field] = round(score, 3)

        return field_scores

    def _score_field(
        self,
        field: str,
        value: str,
        mrz_parsed: Optional[Dict],
        mrz_valid: bool,
        ocr_confidence: float,
    ) -> float:
        if not value:
            return 0.0

        if mrz_valid and mrz_parsed:
            mrz_mapping = {
                "first_name": "given_names",
                "last_name": "surname",
                "birth_date": "birth_date",
                "passport_number": "passport_number",
                "nationality": "nationality",
                "gender": "gender",
                "pinfl": "personal_number",
            }

            mrz_field = mrz_mapping.get(field)
            if mrz_field and mrz_parsed.get(mrz_field):
                mrz_value = mrz_parsed[mrz_field].replace("<", " ").strip().title()
                if mrz_value.upper() == value.upper():
                    return 0.98

        if field == "pinfl":
            return 1.0 if len(value) == 14 and value.isdigit() else 0.3

        if field == "passport_number":
            import re

            if re.match(r"^[A-Z]{2}\d{7}$", value, re.IGNORECASE):
                return 0.9
            if re.match(r"^\d{9}$", value):
                return 0.8
            return 0.5

        if field in ("birth_date", "expiry_date"):
            from app.services.validator import validator

            return 0.9 if validator.validate_date(value) else 0.3

        if field == "gender":
            return 0.9 if value.upper() in ("M", "F", "MALE", "FEMALE") else 0.3

        return 0.5 + ocr_confidence * 0.4

    def overall(
        self,
        extracted: Dict,
        mrz_valid: bool,
        ocr_confidence: float,
        field_scores: Dict[str, float],
    ) -> float:
        weighted_sum = 0.0
        total_weight = 0.0

        for field, weight in self.FIELD_WEIGHTS.items():
            score = field_scores.get(field, 0.0)
            weighted_sum += score * weight
            total_weight += weight

        base_score = weighted_sum / total_weight if total_weight > 0 else 0.0

        mrz_bonus = 0.15 if mrz_valid else 0.0
        ocr_bonus = ocr_confidence * 0.10

        final = min(base_score + mrz_bonus + ocr_bonus, 1.0)

        filled_ratio = sum(1 for v in extracted.values() if v) / max(len(extracted), 1)

        final = final * 0.8 + filled_ratio * 0.2

        return round(final, 3)


confidence_scorer = ConfidenceScorer()
