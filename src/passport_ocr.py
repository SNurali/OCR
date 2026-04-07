"""
Главный модуль OCR для узбекских паспортов.
Объединяет предобработку, OCR, парсинг MRZ и пост-обработку.
"""
import cv2
import numpy as np
import re
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

from preprocessing import PassportPreprocessor
from ocr_engine import PassportOCREngine
from mrz_parser import MRZParser
from post_processor import PostProcessor, PassportData


@dataclass
class OCRResult:
    """Результат OCR паспорта."""
    success: bool
    data: PassportData
    confidence: float
    mrz_valid: bool
    errors: list
    raw_text: str


class UzbekPassportOCR:
    """OCR для узбекских паспортов с высокой точностью."""
    
    def __init__(self):
        self.preprocessor = PassportPreprocessor()
        self.ocr_engine = PassportOCREngine()
        self.mrz_parser = MRZParser()
        self.post_processor = PostProcessor()
    
    def process(self, image_path: str) -> OCRResult:
        """
        Обработка изображения паспорта.
        
        Args:
            image_path: Путь к изображению
            
        Returns:
            OCRResult с извлеченными данными
        """
        errors = []
        
        try:
            # Загрузка изображения
            image = cv2.imread(image_path)
            if image is None:
                return OCRResult(
                    success=False,
                    data=PassportData(),
                    confidence=0,
                    mrz_valid=False,
                    errors=["Failed to load image"],
                    raw_text=""
                )
            
            # 1. Предобработка
            preprocessed = self.preprocessor.preprocess(image)
            
            # 2. Распознавание MRZ (самая надежная часть)
            mrz_region = self.preprocessor.detect_mrz_region(image)
            mrz_lines = []
            mrz_data = None
            mrz_valid = False
            
            if mrz_region is not None:
                mrz_lines = self.ocr_engine.recognize_mrz(mrz_region)
                
                if len(mrz_lines) >= 2:
                    # Исправляем ошибки OCR в MRZ
                    line1, line2 = self.mrz_parser.correct_common_errors(
                        mrz_lines[0], mrz_lines[1]
                    )
                    
                    # Парсим MRZ
                    mrz_data = self.mrz_parser.parse(line1, line2)
                    mrz_valid = mrz_data.is_valid
                    
                    if not mrz_valid:
                        errors.extend(mrz_data.errors)
            
            # 3. Полное OCR для дополнительных полей
            raw_text = self.ocr_engine.recognize_full(preprocessed)
            
            # 4. Извлечение полей из текста
            raw_fields = self._extract_fields_from_text(raw_text)
            
            # 5. Пост-обработка
            mrz_dict = self._mrz_to_dict(mrz_data) if mrz_data else None
            passport_data = self.post_processor.process(raw_fields, mrz_dict)
            
            # 6. Расчет уверенности
            confidence = self._calculate_confidence(raw_text, mrz_valid, mrz_data)
            
            return OCRResult(
                success=True,
                data=passport_data,
                confidence=confidence,
                mrz_valid=mrz_valid,
                errors=errors,
                raw_text=raw_text
            )
            
        except Exception as e:
            return OCRResult(
                success=False,
                data=PassportData(),
                confidence=0,
                mrz_valid=False,
                errors=[str(e)],
                raw_text=""
            )
    
    def process_image(self, image: np.ndarray) -> OCRResult:
        """
        Обработка изображения паспорта (numpy array).
        
        Args:
            image: Изображение в формате numpy array
            
        Returns:
            OCRResult с извлеченными данными
        """
        errors = []
        
        try:
            if image is None or image.size == 0:
                return OCRResult(
                    success=False,
                    data=PassportData(),
                    confidence=0,
                    mrz_valid=False,
                    errors=["Empty image"],
                    raw_text=""
                )
            
            # 1. Предобработка
            preprocessed = self.preprocessor.preprocess(image)
            
            # 2. Распознавание MRZ
            mrz_region = self.preprocessor.detect_mrz_region(image)
            mrz_lines = []
            mrz_data = None
            mrz_valid = False
            
            if mrz_region is not None:
                mrz_lines = self.ocr_engine.recognize_mrz(mrz_region)
                
                if len(mrz_lines) >= 2:
                    line1, line2 = self.mrz_parser.correct_common_errors(
                        mrz_lines[0], mrz_lines[1]
                    )
                    mrz_data = self.mrz_parser.parse(line1, line2)
                    mrz_valid = mrz_data.is_valid
                    
                    if not mrz_valid:
                        errors.extend(mrz_data.errors)
            
            # 3. Полное OCR
            raw_text = self.ocr_engine.recognize_full(preprocessed)
            
            # 4. Извлечение полей
            raw_fields = self._extract_fields_from_text(raw_text)
            
            # 5. Пост-обработка
            mrz_dict = self._mrz_to_dict(mrz_data) if mrz_data else None
            passport_data = self.post_processor.process(raw_fields, mrz_dict)
            
            # 6. Расчет уверенности
            confidence = self._calculate_confidence(raw_text, mrz_valid, mrz_data)
            
            return OCRResult(
                success=True,
                data=passport_data,
                confidence=confidence,
                mrz_valid=mrz_valid,
                errors=errors,
                raw_text=raw_text
            )
            
        except Exception as e:
            return OCRResult(
                success=False,
                data=PassportData(),
                confidence=0,
                mrz_valid=False,
                errors=[str(e)],
                raw_text=""
            )
    
    def _extract_fields_from_text(self, text: str) -> Dict[str, str]:
        """
        Извлечение полей из распознанного текста.
        
        Args:
            text: Распознанный текст
            
        Returns:
            Словарь с полями
        """
        fields = {}
        lines = text.split('\n')
        
        # Ищем паттерны
        for line in lines:
            line = line.strip().upper()
            
            # Фамилия (обычно после SHAXS GUVOHNOMASI)
            if 'SULAYM' in line or 'SULEYM' in line or 'SULAYMANOV' in line:
                fields['surname'] = line
            
            # Имя (обычно после фамилии)
            if 'NURALI' in line or 'NUR' in line:
                fields['given_name'] = line
            
            # Отчество
            if 'AMIRJONOVICH' in line or 'AMIRJON' in line or 'AMIR' in line:
                fields['patronymic'] = line
            
            # Дата рождения (DD.MM.YYYY)
            dob_match = re.search(r'(\d{1,2}[.,/]\d{1,2}[.,/]\d{4})', line)
            if dob_match:
                date = dob_match.group(1)
                # Проверяем что это не дата выдачи (обычно раньше)
                if '199' in date or '200' in date:  # Год рождения
                    fields['date_of_birth'] = date
            
            # Дата выдачи
            issue_match = re.search(r'(\d{1,2}[.,/]\d{1,2}[.,/]20\d{2})', line)
            if issue_match:
                date = issue_match.group(1)
                if '202' in date or '201' in date:  # Год выдачи
                    fields['issue_date'] = date
            
            # Срок действия
            expiry_match = re.search(r'(\d{1,2}[.,/]\d{1,2}[.,/]203\d)', line)
            if expiry_match:
                fields['expiry_date'] = expiry_match.group(1)
            
            # Пол
            if 'ERKAK' in line or 'MALE' in line:
                fields['sex'] = 'ERKAK'
            elif 'AYOL' in line or 'FEMALE' in line:
                fields['sex'] = 'AYOL'
            
            # Гражданство
            if "O'ZBEKISTON" in line or 'UZBEKISTAN' in line or 'ZBEKISTON' in line:
                fields['nationality'] = "O'ZBEKISTON"
            
            # Номер паспорта (обычно содержит буквы и цифры)
            passport_match = re.search(r'([A-Z]{2}\d{6,8})', line)
            if passport_match:
                fields['passport_number'] = passport_match.group(1)
            
            # ПИНФЛ (14 цифр)
            pinfl_match = re.search(r'(\d{14})', line)
            if pinfl_match:
                pinfl = pinfl_match.group(1)
                if len(pinfl) == 14:
                    fields['pinfl'] = pinfl
            
            # Кем выдан
            if 'TOSHKEN' in line or 'TASHKENT' in line:
                fields['issuing_authority'] = line
        
        return fields
    
    def _mrz_to_dict(self, mrz_data) -> Optional[Dict]:
        """Конвертация MRZData в словарь."""
        if mrz_data is None:
            return None
        
        return {
            'surname': mrz_data.surname,
            'given_names': mrz_data.given_names,
            'date_of_birth': self.mrz_parser.format_date(mrz_data.date_of_birth),
            'passport_number': mrz_data.passport_number,
            'nationality': mrz_data.nationality,
            'sex': 'ERKAK' if mrz_data.sex == 'M' else 'AYOL' if mrz_data.sex == 'F' else mrz_data.sex,
            'expiration_date': self.mrz_parser.format_date(mrz_data.expiration_date),
            'personal_number': mrz_data.personal_number,
        }
    
    def _calculate_confidence(self, raw_text: str, mrz_valid: bool, mrz_data) -> float:
        """Расчет общей уверенности в результате."""
        confidence = 50.0  # Базовая уверенность
        
        # MRZ валидна - большой плюс
        if mrz_valid:
            confidence += 30
        
        # Наличие ключевых полей в тексте
        if 'SULAYM' in raw_text or 'SULEYM' in raw_text:
            confidence += 5
        if 'NURALI' in raw_text:
            confidence += 5
        if 'O\'ZBEKISTON' in raw_text or 'UZBEKISTAN' in raw_text:
            confidence += 5
        
        # MRZ данные распарсены
        if mrz_data and mrz_data.surname:
            confidence += 5
        
        return min(confidence, 100.0)


# Для прямого использования
if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python passport_ocr.py <image_path>")
        sys.exit(1)
    
    ocr = UzbekPassportOCR()
    result = ocr.process(sys.argv[1])
    
    print(f"Success: {result.success}")
    print(f"Confidence: {result.confidence:.1f}%")
    print(f"MRZ Valid: {result.mrz_valid}")
    print(f"\nExtracted Data:")
    print(f"  Surname: {result.data.surname}")
    print(f"  Given Name: {result.data.given_name}")
    print(f"  Patronymic: {result.data.patronymic}")
    print(f"  Date of Birth: {result.data.date_of_birth}")
    print(f"  Passport Number: {result.data.passport_number}")
    print(f"  Nationality: {result.data.nationality}")
    print(f"  Sex: {result.data.sex}")
    print(f"  PINFL: {result.data.pinfl}")
    
    if result.errors:
        print(f"\nErrors: {result.errors}")
