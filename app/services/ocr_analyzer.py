import logging
from typing import Dict, Any

from app.services.vlm_extractor import vlm_extractor
from app.services.validator import validator

logger = logging.getLogger(__name__)


def analyze_passport_image(image_bytes: bytes) -> Dict[str, Any]:
    """
    Анализ изображения паспорта через Qwen VLM (Vision-Language Model).

    Args:
        image_bytes: сырые байты изображения (JPEG, PNG и т.д.)

    Returns:
        dict с полями:
            - extracted: извлечённые поля (first_name, last_name, ...)
            - validation: результат валидации (checks, all_valid, overall_confidence)
            - raw_response: сырой ответ от VLM (для отладки)
    """
    # 1. Извлечение данных через Qwen VLM
    extracted = vlm_extractor.extract(image_bytes)

    # 2. Валидация
    validation = validator.validate(extracted)

    # 3. Логируем результат
    filled_fields = sum(1 for v in extracted.values() if v)
    total_fields = len(extracted)
    all_valid = validation.get("all_valid", False)
    confidence = validation.get("overall_confidence", 0)

    logger.info(
        f"Qwen VLM analysis: {filled_fields}/{total_fields} fields filled, "
        f"all_valid={all_valid}, confidence={confidence:.2f}"
    )

    return {
        "extracted": validation.get("normalized_data", extracted),
        "validation": validation,
        "raw_response": extracted,
    }
