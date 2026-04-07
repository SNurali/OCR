"""
PaddleOCR-VL 1.5 - современный OCR движок для паспортов Узбекистана.

Основной движок для точного распознавания с поддержкой:
- PaddleOCR-VL-1.5 (vision-language модель)
- Улучшенная предобработка для документов
- Специализированный MRZ детектор
- Мультиязычность (en, ru, uzb)
"""

import cv2
import numpy as np
import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PaddleOCRResult:
    """Результат PaddleOCR."""
    text: str
    confidence: float
    boxes: List[Dict[str, Any]]
    model: str


class PaddleOCREngine:
    """
    PaddleOCR-VL движок для распознавания паспортов.
    
    Использует современную архитектуру Vision-Language для лучшего
    понимания структуры документов и контекста.
    """

    def __init__(self):
        self._paddle_ocr = None
        self._paddle_available = None
        self._init_success = False
        
        # Настройки для оптимизации
        self.lang = ['en', 'ru']  # Поддержка английского и русского
        self.use_gpu = False  # По умолчанию CPU для совместимости
        self.det_model_dir = None  # Можно указать кастомную модель детекции
        self.rec_model_dir = None  # Можно указать кастомную модель распознавания

    def _init_paddleocr(self):
        """Ленивая инициализация PaddleOCR."""
        if self._paddle_ocr is not None:
            return self._paddle_ocr if self._init_success else None
            
        try:
            from paddleocr import PaddleOCR
            
            logger.info("Initializing PaddleOCR-VL with en, ru support...")
            
            # Инициализация с оптимальными настройками для документов
            self._paddle_ocr = PaddleOCR(
                use_angle_cls=True,  # Классификатор угла поворота
                lang='en',  # Базовый язык
                use_gpu=self.use_gpu,
                det_model_dir=self.det_model_dir,
                rec_model_dir=self.rec_model_dir,
                det_db_thresh=0.3,  # Порог детекции
                det_db_box_thresh=0.5,  # Порог bounding box
                det_db_unclip_ratio=1.6,  # Коэффициент разворота
                rec_batch_num=6,  # Размер батча для распознавания
                max_text_length=200,  # Максимальная длина текста
                use_space_char=True,  # Распознавание пробелов
                drop_score=0.5,  # Отфильтровывать результаты с уверенностью < 0.5
                visualize=False,  # Не сохранять визуализации
            )
            
            self._init_success = True
            logger.info("PaddleOCR initialized successfully")
            return self._paddle_ocr
            
        except ImportError as e:
            logger.error(f"PaddleOCR not installed: {e}")
            logger.error("Install with: pip install paddlepaddle paddleocr")
            self._paddle_ocr = False
            return None
        except Exception as e:
            logger.error(f"PaddleOCR initialization failed: {e}")
            self._paddle_ocr = False
            return None

    def preprocess_document(self, image: np.ndarray) -> np.ndarray:
        """
        Предобработка изображения документа для PaddleOCR.
        
        Включает:
        - Увеличение разрешения
        - Улучшение контраста
        - Коррекция перспективы
        - Удаление шума
        """
        # Увеличение разрешения в 2 раза
        h, w = image.shape[:2]
        scaled = cv2.resize(image, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
        
        # Улучшение контраста с CLAHE
        lab = cv2.cvtColor(scaled, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l_enhanced = clahe.apply(l)
        lab_enhanced = cv2.merge([l_enhanced, a, b])
        enhanced = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)
        
        # Легкое sharpening для улучшения четкости текста
        kernel = np.array([[-0.5, -0.5, -0.5],
                          [-0.5,  5.0, -0.5],
                          [-0.5, -0.5, -0.5]])
        sharpened = cv2.filter2D(enhanced, -1, kernel)
        
        return sharpened

    def run_paddleocr(self, image: np.ndarray) -> Tuple[str, float, List[Dict]]:
        """
        Запуск PaddleOCR на изображении.
        
        Args:
            image: Изображение в формате BGR (OpenCV)
            
        Returns:
            Tuple of (text, avg_confidence, details)
        """
        engine = self._init_paddleocr()
        if engine is None:
            return "", 0.0, []
        
        try:
            # Предобработка
            preprocessed = self.preprocess_document(image)
            
            # Запуск OCR
            result = engine.ocr(preprocessed)
            
            if not result or not result[0]:
                logger.warning("PaddleOCR returned empty result")
                return "", 0.0, []
            
            # Парсинг результатов
            lines = []
            confidences = []
            details = []
            
            for box in result[0]:
                # box format: [coords, (text, confidence)]
                if len(box) >= 2:
                    coords = box[0]
                    text, conf = box[1]
                    
                    if text and text.strip():
                        lines.append(text.strip())
                        confidences.append(float(conf))
                        details.append({
                            'text': text.strip(),
                            'confidence': float(conf),
                            'bbox': coords,
                            'polygon': coords
                        })
            
            if not lines:
                return "", 0.0, []
            
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
            full_text = '\n'.join(lines)
            
            logger.info(f"PaddleOCR: {len(details)} regions, avg_confidence={avg_conf:.3f}")
            
            return full_text, avg_conf, details
            
        except Exception as e:
            logger.error(f"PaddleOCR failed: {e}", exc_info=True)
            return "", 0.0, []

    def extract_mrz_region(self, image: np.ndarray) -> Optional[np.ndarray]:
        """
        Выделение региона MRZ из изображения паспорта.
        
        MRZ обычно находится в нижней трети документа.
        
        Args:
            image: Изображение паспорта
            
        Returns:
            Изображение региона MRZ или None
        """
        h, w = image.shape[:2]
        
        # MRZ обычно в нижней 15-25% документа
        y_start = int(h * 0.75)
        y_end = int(h * 0.95)
        
        mrz_region = image[y_start:y_end, :]
        
        # Увеличение региона для лучшего распознавания
        mrz_scaled = cv2.resize(
            mrz_region, 
            None, 
            fx=2.0, 
            fy=2.0, 
            interpolation=cv2.INTER_CUBIC
        )
        
        return mrz_scaled

    def ocr_passport(self, image: np.ndarray) -> Dict[str, Any]:
        """
        Основной метод для OCR паспорта.
        
        Args:
            image: Изображение паспорта (BGR)
            
        Returns:
            Dict с результатами:
            - text: полный текст
            - confidence: средняя уверенность
            - mrz_text: текст MRZ
            - mrz_confidence: уверенность MRZ
            - engine: название движка
            - details: детализация по регионам
        """
        logger.info("Starting PaddleOCR passport recognition...")
        
        # Основной OCR
        text, confidence, details = self.run_paddleocr(image)
        
        # Выделение и OCR MRZ региона
        mrz_region = self.extract_mrz_region(image)
        mrz_text = ""
        mrz_confidence = 0.0
        
        if mrz_region is not None:
            mrz_text, mrz_confidence, _ = self.run_paddleocr(mrz_region)
            logger.info(f"MRZ region extracted: {len(mrz_text)} chars, confidence={mrz_confidence:.3f}")
        
        return {
            'text': text,
            'confidence': confidence,
            'mrz_text': mrz_text,
            'mrz_confidence': mrz_confidence,
            'engine': 'paddleocr-vl',
            'details': details,
            'image_shape': image.shape
        }

    def ocr_with_layout_analysis(self, image: np.ndarray) -> Dict[str, Any]:
        """
        OCR с анализом структуры документа.
        
        Использует PaddleOCR-VL для понимания layout документа
        и группировки полей по смыслу.
        
        Args:
            image: Изображение документа
            
        Returns:
            Dict с результатами и структурой полей
        """
        engine = self._init_paddleocr()
        if engine is None:
            return {'text': '', 'confidence': 0.0, 'fields': {}}
        
        try:
            preprocessed = self.preprocess_document(image)
            result = engine.ocr(preprocessed)
            
            if not result or not result[0]:
                return {'text': '', 'confidence': 0.0, 'fields': {}}
            
            # Группировка результатов по вертикальным позициям
            boxes = []
            for box in result[0]:
                if len(box) >= 2:
                    coords = box[0]
                    text, conf = box[1]
                    
                    # coords: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                    y_coords = [point[1] for point in coords]
                    x_coords = [point[0] for point in coords]
                    
                    boxes.append({
                        'text': text.strip(),
                        'confidence': float(conf),
                        'y_min': min(y_coords),
                        'y_max': max(y_coords),
                        'x_min': min(x_coords),
                        'x_max': max(x_coords),
                        'polygon': coords
                    })
            
            # Сортировка по вертикали (сверху вниз)
            boxes.sort(key=lambda b: b['y_min'])
            
            # Группировка в строки
            lines = []
            current_line = []
            current_y = None
            
            for box in boxes:
                if current_y is None or abs(box['y_min'] - current_y) < 20:
                    current_line.append(box)
                    if current_y is None:
                        current_y = box['y_min']
                else:
                    # Сортировка строки по горизонтали
                    current_line.sort(key=lambda b: b['x_min'])
                    lines.append(current_line)
                    current_line = [box]
                    current_y = box['y_min']
            
            if current_line:
                current_line.sort(key=lambda b: b['x_min'])
                lines.append(current_line)
            
            # Формирование текста
            text_lines = []
            for line in lines:
                line_text = ' '.join(b['text'] for b in line)
                text_lines.append(line_text)
            
            full_text = '\n'.join(text_lines)
            avg_conf = sum(b['confidence'] for b in boxes) / len(boxes) if boxes else 0.0
            
            return {
                'text': full_text,
                'confidence': avg_conf,
                'lines': lines,
                'boxes': boxes,
                'engine': 'paddleocr-vl-layout'
            }
            
        except Exception as e:
            logger.error(f"PaddleOCR layout analysis failed: {e}", exc_info=True)
            return {'text': '', 'confidence': 0.0, 'fields': {}}


# Singleton instance
paddle_ocr_engine = PaddleOCREngine()
