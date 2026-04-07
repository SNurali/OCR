"""Surya OCR — высокоточное распознавание документов.

Surya обеспечивает значительно лучшее качество OCR
по сравнению с Tesseract/EasyOCR, особенно для документов.
Поддерживает 90+ языков.
"""

import os
import logging
from typing import List, Optional
import numpy as np

logger = logging.getLogger(__name__)

# Принудительно CPU если нет GPU
os.environ.setdefault("TORCH_DEVICE", "cpu")


class SuryaOCR:
    """Обёртка над surya-ocr для ленивой инициализации и простого API."""

    def __init__(self):
        self._det_model = None
        self._det_processor = None
        self._rec_model = None
        self._rec_processor = None
        self._initialized = False
        self._available = None

    def _check_available(self) -> bool:
        """Проверяем, доступна ли библиотека surya."""
        if self._available is not None:
            return self._available
        try:
            import surya
            self._available = True
        except ImportError:
            logger.warning("surya-ocr не установлен. Используем fallback OCR.")
            self._available = False
        return self._available

    def _init_models(self):
        """Ленивая инициализация моделей при первом вызове."""
        if self._initialized:
            return
        if not self._check_available():
            return

        try:
            logger.info("Инициализация Surya OCR моделей...")
            from surya.model.detection.segformer import (
                load_model as load_det_model,
                load_processor as load_det_processor,
            )
            from surya.model.recognition.model import load_model as load_rec_model
            from surya.model.recognition.processor import (
                load_processor as load_rec_processor,
            )

            self._det_processor = load_det_processor()
            self._det_model = load_det_model()
            self._rec_model = load_rec_model()
            self._rec_processor = load_rec_processor()
            self._initialized = True
            logger.info("Surya OCR инициализирована успешно")
        except Exception as e:
            logger.error(f"Ошибка инициализации Surya OCR: {e}")
            self._available = False

    def recognize(self, image: np.ndarray, langs: Optional[List[str]] = None) -> str:
        """Распознавание текста на изображении.

        Args:
            image: numpy array (BGR или RGB)
            langs: список языков, по умолчанию ["en", "ru"]

        Returns:
            Распознанный текст (строки через \\n)
        """
        self._init_models()
        if not self._initialized:
            return ""

        if langs is None:
            langs = ["en", "ru"]

        try:
            from PIL import Image
            from surya.ocr import run_ocr

            # Конвертируем numpy (BGR) в PIL (RGB)
            if len(image.shape) == 3 and image.shape[2] == 3:
                import cv2
                rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            else:
                rgb_image = image

            pil_image = Image.fromarray(rgb_image.astype("uint8"), "RGB")

            predictions = run_ocr(
                [pil_image],
                [langs],
                self._det_model,
                self._det_processor,
                self._rec_model,
                self._rec_processor,
            )

            if not predictions:
                return ""

            lines = []
            for pred in predictions:
                for text_line in pred.text_lines:
                    text = text_line.text.strip()
                    if text:
                        lines.append(text)

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Ошибка Surya OCR: {e}")
            return ""

    def recognize_with_confidence(
        self, image: np.ndarray, langs: Optional[List[str]] = None
    ) -> tuple:
        """Распознавание текста с confidence score.

        Returns:
            (text: str, avg_confidence: float)
        """
        self._init_models()
        if not self._initialized:
            return "", 0.0

        if langs is None:
            langs = ["en", "ru"]

        try:
            from PIL import Image
            from surya.ocr import run_ocr
            import cv2

            if len(image.shape) == 3 and image.shape[2] == 3:
                rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            else:
                rgb_image = image

            pil_image = Image.fromarray(rgb_image.astype("uint8"), "RGB")

            predictions = run_ocr(
                [pil_image],
                [langs],
                self._det_model,
                self._det_processor,
                self._rec_model,
                self._rec_processor,
            )

            if not predictions:
                return "", 0.0

            lines = []
            confidences = []
            for pred in predictions:
                for text_line in pred.text_lines:
                    text = text_line.text.strip()
                    if text:
                        lines.append(text)
                        confidences.append(text_line.confidence)

            avg_confidence = (
                sum(confidences) / len(confidences) if confidences else 0.0
            )
            return "\n".join(lines), avg_confidence

        except Exception as e:
            logger.error(f"Ошибка Surya OCR: {e}")
            return "", 0.0

    @property
    def is_available(self) -> bool:
        return self._check_available()


# Глобальный экземпляр
surya_ocr = SuryaOCR()
