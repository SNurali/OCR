"""
Модуль предобработки изображений паспортов для улучшения OCR.
"""
import cv2
import numpy as np
from typing import Tuple, Optional


class PassportPreprocessor:
    """Класс для предобработки изображений паспортов."""
    
    def __init__(self, target_width: int = 1200):
        self.target_width = target_width
    
    def preprocess(self, image: np.ndarray) -> np.ndarray:
        """
        Полная предобработка изображения паспорта.
        
        Args:
            image: Входное изображение (BGR или RGB)
            
        Returns:
            Предобработанное изображение
        """
        # Конвертация в grayscale если нужно
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # 1. Увеличение разрешения
        gray = self._resize(gray)
        
        # 2. Удаление шума
        denoised = self._denoise(gray)
        
        # 3. Улучшение контраста (CLAHE)
        enhanced = self._enhance_contrast(denoised)
        
        # 4. Бинаризация с адаптивным порогом
        binary = self._adaptive_threshold(enhanced)
        
        # 5. Удаление артефактов
        cleaned = self._remove_artifacts(binary)
        
        return cleaned
    
    def _resize(self, image: np.ndarray) -> np.ndarray:
        """Увеличение разрешения для лучшего OCR."""
        height, width = image.shape[:2]
        if width < self.target_width:
            scale = self.target_width / width
            new_width = int(width * scale)
            new_height = int(height * scale)
            return cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
        return image
    
    def _denoise(self, image: np.ndarray) -> np.ndarray:
        """Удаление шума с сохранением деталей текста."""
        # Нелокальное среднее для удаления шума
        return cv2.fastNlMeansDenoising(image, None, 10, 7, 21)
    
    def _enhance_contrast(self, image: np.ndarray) -> np.ndarray:
        """Улучшение контраста с помощью CLAHE."""
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(image)
    
    def _adaptive_threshold(self, image: np.ndarray) -> np.ndarray:
        """Адаптивная бинаризация для текста."""
        # Gaussian adaptive threshold
        binary = cv2.adaptiveThreshold(
            image, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11, 2
        )
        return binary
    
    def _remove_artifacts(self, image: np.ndarray) -> np.ndarray:
        """Удаление мелких артефактов и шума."""
        # Морфологическое открытие для удаления шума
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        cleaned = cv2.morphologyEx(image, cv2.MORPH_OPEN, kernel, iterations=1)
        return cleaned
    
    def deskew(self, image: np.ndarray) -> np.ndarray:
        """
        Выравнивание изображения (устранение наклона).
        
        Args:
            image: Входное изображение
            
        Returns:
            Выравненное изображение
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # Находим угол наклона
        coords = np.column_stack(np.where(gray > 0))
        angle = cv2.minAreaRect(coords)[-1]
        
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        
        # Поворачиваем изображение
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(image, M, (w, h),
                                  flags=cv2.INTER_CUBIC,
                                  borderMode=cv2.BORDER_REPLICATE)
        return rotated
    
    def detect_mrz_region(self, image: np.ndarray) -> Optional[np.ndarray]:
        """
        Обнаружение региона MRZ (Machine Readable Zone) в паспорте.
        
        Args:
            image: Входное изображение
            
        Returns:
            Вырезанный регион MRZ или None
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        height, width = gray.shape
        
        # MRZ обычно в нижней части паспорта (последние 15-20%)
        mrz_region = gray[int(height * 0.75):, :]
        
        return mrz_region
    
    def sharpen_text(self, image: np.ndarray) -> np.ndarray:
        """
        Усиление резкости текста.
        
        Args:
            image: Входное изображение
            
        Returns:
            Изображение с усиленной резкостью
        """
        # Ядро для усиления резкости
        kernel = np.array([[-1, -1, -1],
                          [-1,  9, -1],
                          [-1, -1, -1]])
        sharpened = cv2.filter2D(image, -1, kernel)
        return sharpened
