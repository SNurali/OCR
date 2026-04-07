"""
OCR движок для распознавания текста на паспортах.
"""
import pytesseract
import cv2
import numpy as np
import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class OCRResult:
    """Результат OCR."""
    text: str
    confidence: float
    bbox: Optional[Tuple[int, int, int, int]] = None


class PassportOCREngine:
    """OCR движок специализированный для паспортов."""
    
    def __init__(self):
        # Настройки Tesseract для паспортов
        self.tesseract_config = '--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789<.,/ '
        self.tesseract_config_mrz = '--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<'
    
    def recognize_full(self, image: np.ndarray) -> str:
        """
        Распознавание всего текста на изображении.
        
        Args:
            image: Предобработанное изображение
            
        Returns:
            Распознанный текст
        """
        text = pytesseract.image_to_string(
            image,
            lang='eng+rus',  # Английский + русский для лучшего распознавания
            config=self.tesseract_config
        )
        return text.strip()
    
    def recognize_mrz(self, mrz_image: np.ndarray) -> List[str]:
        """
        Распознавание MRZ (Machine Readable Zone).
        
        Args:
            mrz_image: Изображение региона MRZ
            
        Returns:
            Список строк MRZ
        """
        # Предобработка для MRZ
        _, binary = cv2.threshold(mrz_image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Увеличение для лучшего распознавания
        height, width = binary.shape
        scale = 2
        binary = cv2.resize(binary, (width * scale, height * scale), interpolation=cv2.INTER_CUBIC)
        
        text = pytesseract.image_to_string(
            binary,
            lang='eng',
            config=self.tesseract_config_mrz
        )
        
        # Очистка и разбор строк
        lines = []
        for line in text.strip().split('\n'):
            line = line.strip().upper()
            # Фильтруем только валидные символы MRZ
            line = re.sub(r'[^A-Z0-9<]', '', line)
            if len(line) >= 30:  # MRZ строки длинные
                lines.append(line)
        
        return lines[:2]  # Возвращаем максимум 2 строки MRZ
    
    def recognize_field(self, image: np.ndarray, field_name: str) -> OCRResult:
        """
        Распознавание конкретного поля с оценкой уверенности.
        
        Args:
            image: Изображение поля
            field_name: Название поля для логирования
            
        Returns:
            OCRResult с текстом и уверенностью
        """
        data = pytesseract.image_to_data(
            image,
            lang='eng',
            config=self.tesseract_config,
            output_type=pytesseract.Output.DICT
        )
        
        # Собираем текст и считаем среднюю уверенность
        texts = []
        confidences = []
        
        for i, text in enumerate(data['text']):
            conf = int(data['conf'][i])
            if conf > 30 and text.strip():  # Фильтруем низкую уверенность
                texts.append(text)
                confidences.append(conf)
        
        full_text = ' '.join(texts)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        return OCRResult(
            text=full_text,
            confidence=avg_confidence
        )
    
    def extract_all_text_with_boxes(self, image: np.ndarray) -> List[OCRResult]:
        """
        Извлечение всего текста с координатами bounding boxes.
        
        Args:
            image: Входное изображение
            
        Returns:
            Список OCRResult с координатами
        """
        data = pytesseract.image_to_data(
            image,
            lang='eng+rus',
            config=self.tesseract_config,
            output_type=pytesseract.Output.DICT
        )
        
        results = []
        n_boxes = len(data['text'])
        
        for i in range(n_boxes):
            conf = int(data['conf'][i])
            text = data['text'][i].strip()
            
            if conf > 30 and text:
                x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                results.append(OCRResult(
                    text=text,
                    confidence=conf,
                    bbox=(x, y, w, h)
                ))
        
        return results
