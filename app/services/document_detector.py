import re
from typing import Dict, Optional


class DocumentTypeDetector:
    """Определение типа документа по OCR тексту и MRZ."""

    UZBEK_PASSPORT_INDICATORS = [
        "O'ZBEKISTON",
        "UZBEKISTAN",
        "REPUBLIKASI",
        "РЕСПУБЛИКАСИ",
        "ПАСПОРТ",
        "PASSPORT",
        "FUQAROLIK",
        "ГРАЖДАНСТВО",
    ]

    ID_CARD_INDICATORS = [
        "ID-CARD",
        "ID KARTA",
        "ШАХС ГУВОҲНОМАСИ",
        "ЛИЧНОЕ УДОСТОВЕРЕНИЕ",
        "TD1",
    ]

    FOREIGN_PASSPORT_INDICATORS = [
        "PASSPORT",
        "UNITED STATES",
        "REPUBLIC OF",
        "ПАСПОРТ ГРАЖДАНИНА",
    ]

    def detect(self, ocr_text: str, mrz_data: Optional[Dict] = None) -> str:
        """Определение типа документа."""
        text_upper = ocr_text.upper()

        if mrz_data and mrz_data.get("valid"):
            doc_type = mrz_data.get("type", "")
            issuing = mrz_data.get("issuing_country", "")

            if doc_type == "TD1":
                return "id_card"
            if issuing == "UZB":
                if doc_type == "TD3":
                    return "passport"

        uz_count = sum(1 for ind in self.UZBEK_PASSPORT_INDICATORS if ind in text_upper)
        id_count = sum(1 for ind in self.ID_CARD_INDICATORS if ind in text_upper)
        foreign_count = sum(
            1 for ind in self.FOREIGN_PASSPORT_INDICATORS if ind in text_upper
        )

        if id_count > uz_count and id_count > foreign_count:
            return "id_card"
        if uz_count > foreign_count:
            return "passport"
        if foreign_count > 0:
            return "foreign_passport"

        return "passport"


detector = DocumentTypeDetector()
