"""
Пост-обработка и коррекция распознанных полей паспорта.
"""
import re
from typing import Dict, Optional, List
from dataclasses import dataclass
from datetime import datetime


@dataclass
class PassportData:
    """Структура данных паспорта."""
    surname: str = ""
    given_name: str = ""
    patronymic: str = ""
    date_of_birth: str = ""
    nationality: str = ""
    passport_number: str = ""
    passport_series: str = ""
    issue_date: str = ""
    expiry_date: str = ""
    issuing_authority: str = ""
    sex: str = ""
    pinfl: str = ""
    mrz_line1: str = ""
    mrz_line2: str = ""
    confidence_scores: Dict[str, float] = None
    
    def __post_init__(self):
        if self.confidence_scores is None:
            self.confidence_scores = {}


class FieldCorrector:
    """Корректор полей на основе правил и словарей."""
    
    # Словарь типичных ошибок OCR
    OCR_ERRORS = {
        '0': 'O', 'O': '0',  # Ноль и буква O
        '1': 'I', 'I': '1',  # Единица и I
        '5': 'S', 'S': '5',  # Пятерка и S
        '8': 'B', 'B': '8',  # Восьмерка и B
        '6': 'G', 'G': '6',  # Шестерка и G
        '2': 'Z', 'Z': '2',  # Двойка и Z
        '4': 'A', 'A': '4',  # Четверка и A
    }
    
    # Узбекские суффиксы фамилий
    UZBEK_SUFFIXES = ['OV', 'EV', 'OVA', 'EVA', 'OVICH', 'EVICH', 'OVNA', 'EVNA']
    
    # Типичные узбекские фамилии (для коррекции)
    COMMON_SURNAMES = [
        'SULAYMANOV', 'SULAYMANOVA', 'SULEYMANOV', 'SULEYMANOVA',
        'ABDULLAYEV', 'ABDULLAYEVA', 'ABDULLAEV', 'ABDULLAEVA',
        'RAXIMOV', 'RAXIMOVA', 'RAHIMOV', 'RAHIMOVA',
        'XASANOV', 'XASANOVA', 'HASANOV', 'HASANOVA',
        'NURMATOV', 'NURMATOVA', 'NURMATOVICH',
        'ISMOILOV', 'ISMOILOVA', 'ISMAILOV', 'ISMAILOVA',
        'KARIMOV', 'KARIMOVA', 'KARIMOVICH',
        'AKBAROV', 'AKBAROVA',
        'AZIZOV', 'AZIZOVA',
    ]
    
    def __init__(self):
        self.corrections_made = []
    
    def correct_name(self, name: str, is_surname: bool = False) -> str:
        """
        Коррекция имени/фамилии.
        
        Args:
            name: Распознанное имя
            is_surname: True если это фамилия
            
        Returns:
            Исправленное имя
        """
        if not name:
            return ""
        
        # Удаляем лишние пробелы
        name = ' '.join(name.split())
        
        # Заменяем строчные на заглавные
        name = name.upper()
        
        # Удаляем лишние символы (оставляем только буквы и дефис)
        name = re.sub(r'[^A-Z\-]', '', name)
        
        # Исправляем типичные ошибки OCR
        corrected = self._fix_ocr_errors(name, is_text=True)
        
        # Если это фамилия, проверяем по словарю
        if is_surname:
            corrected = self._match_surname(corrected)
        
        if corrected != name:
            self.corrections_made.append(f"Name: '{name}' -> '{corrected}'")
        
        return corrected
    
    def correct_date(self, date_str: str) -> str:
        """
        Коррекция даты в формате DD.MM.YYYY.
        
        Args:
            date_str: Распознанная дата
            
        Returns:
            Исправленная дата
        """
        if not date_str:
            return ""
        
        # Удаляем все кроме цифр и разделителей
        date_str = re.sub(r'[^0-9.,/-]', '', date_str)
        
        # Заменяем разделители на точки
        date_str = date_str.replace(',', '.').replace('/', '.').replace('-', '.')
        
        # Исправляем типичные ошибки OCR в датах
        date_str = self._fix_ocr_errors(date_str, is_text=False)
        
        # Парсим и валидируем
        parts = date_str.split('.')
        if len(parts) == 3:
            try:
                day = int(parts[0])
                month = int(parts[1])
                year = int(parts[2])
                
                # Коррекция года (если 2 цифры)
                if year < 100:
                    current_year = datetime.now().year
                    century = current_year // 100
                    year = century * 100 + year
                    if year > current_year:
                        year -= 100
                
                # Валидация
                if 1 <= day <= 31 and 1 <= month <= 12 and 1900 <= year <= 2100:
                    return f"{day:02d}.{month:02d}.{year}"
            except ValueError:
                pass
        
        return date_str
    
    def correct_passport_number(self, number: str) -> str:
        """
        Коррекция номера паспорта.
        
        Args:
            number: Распознанный номер
            
        Returns:
            Исправленный номер
        """
        if not number:
            return ""
        
        # Удаляем все кроме букв и цифр
        number = re.sub(r'[^A-Z0-9]', '', number.upper())
        
        # Исправляем OCR ошибки (в номерах буквы редки)
        number = self._fix_ocr_errors(number, is_text=False)
        
        return number
    
    def correct_pinfl(self, pinfl: str) -> str:
        """
        Коррекция ПИНФЛ (14 цифр).
        
        Args:
            pinfl: Распознанный ПИНФЛ
            
        Returns:
            Исправленный ПИНФЛ
        """
        if not pinfl:
            return ""
        
        # Удаляем все кроме цифр
        pinfl = re.sub(r'[^0-9]', '', pinfl)
        
        # Исправляем OCR ошибки
        pinfl = self._fix_ocr_errors(pinfl, is_text=False)
        
        # Проверяем длину
        if len(pinfl) != 14:
            # Пытаемся восстановить если потеряны цифры
            pass
        
        return pinfl
    
    def _fix_ocr_errors(self, text: str, is_text: bool = True) -> str:
        """
        Исправление типичных ошибок OCR.
        
        Args:
            text: Текст для исправления
            is_text: True если это текст (не цифры)
            
        Returns:
            Исправленный текст
        """
        result = []
        for char in text:
            if is_text:
                # В тексте цифры скорее всего ошибки
                if char.isdigit() and char in '01586':
                    result.append(self.OCR_ERRORS.get(char, char))
                else:
                    result.append(char)
            else:
                # В цифрах буквы скорее всего ошибки
                if char.isalpha() and char in 'OISBGZA':
                    result.append(self.OCR_ERRORS.get(char, char))
                else:
                    result.append(char)
        return ''.join(result)
    
    def _match_surname(self, surname: str) -> str:
        """Поиск ближайшей фамилии в словаре."""
        # Точное совпадение
        if surname in self.COMMON_SURNAMES:
            return surname
        
        # Поиск с исправлением суффиксов
        for common in self.COMMON_SURNAMES:
            # Проверяем расстояние Левенштейна (упрощенно)
            if self._similarity(surname, common) > 0.8:
                self.corrections_made.append(f"Surname matched: '{surname}' -> '{common}'")
                return common
        
        return surname
    
    def _similarity(self, s1: str, s2: str) -> float:
        """Простая оценка схожести строк."""
        if len(s1) != len(s2):
            return 0.0
        
        matches = sum(c1 == c2 for c1, c2 in zip(s1, s2))
        return matches / len(s1)


class PostProcessor:
    """Пост-процессор для обработки результатов OCR."""
    
    def __init__(self):
        self.corrector = FieldCorrector()
    
    def process(self, raw_data: Dict[str, str], mrz_data: Optional[Dict] = None) -> PassportData:
        """
        Обработка сырых данных OCR.
        
        Args:
            raw_data: Сырые данные из OCR
            mrz_data: Данные из MRZ (опционально)
            
        Returns:
            Обработанные данные паспорта
        """
        passport = PassportData()
        
        # Обрабатываем поля
        passport.surname = self.corrector.correct_name(
            raw_data.get('surname', ''), is_surname=True
        )
        passport.given_name = self.corrector.correct_name(
            raw_data.get('given_name', '')
        )
        passport.patronymic = self.corrector.correct_name(
            raw_data.get('patronymic', '')
        )
        passport.date_of_birth = self.corrector.correct_date(
            raw_data.get('date_of_birth', '')
        )
        passport.issue_date = self.corrector.correct_date(
            raw_data.get('issue_date', '')
        )
        passport.expiry_date = self.corrector.correct_date(
            raw_data.get('expiry_date', '')
        )
        passport.passport_number = self.corrector.correct_passport_number(
            raw_data.get('passport_number', '')
        )
        passport.pinfl = self.corrector.correct_pinfl(
            raw_data.get('pinfl', '')
        )
        passport.nationality = raw_data.get('nationality', '').upper()
        passport.sex = self._normalize_sex(raw_data.get('sex', ''))
        passport.issuing_authority = raw_data.get('issuing_authority', '').upper()
        
        # Если есть MRZ данные, используем их для коррекции
        if mrz_data:
            passport = self._merge_with_mrz(passport, mrz_data)
        
        return passport
    
    def _normalize_sex(self, sex: str) -> str:
        """Нормализация пола."""
        sex = sex.upper().strip()
        if sex in ['M', 'MALE', 'ERKAK', 'МУЖ', 'М', 'МУЖСКОЙ']:
            return 'ERKAK'
        elif sex in ['F', 'FEMALE', 'AYOL', 'ЖЕН', 'Ж', 'ЖЕНСКИЙ']:
            return 'AYOL'
        return sex
    
    def _merge_with_mrz(self, passport: PassportData, mrz_data: Dict) -> PassportData:
        """Объединение данных OCR с MRZ (MRZ имеет приоритет)."""
        if mrz_data.get('surname'):
            passport.surname = mrz_data['surname']
        if mrz_data.get('given_names'):
            passport.given_name = mrz_data['given_names']
        if mrz_data.get('date_of_birth'):
            passport.date_of_birth = mrz_data['date_of_birth']
        if mrz_data.get('passport_number'):
            passport.passport_number = mrz_data['passport_number']
        if mrz_data.get('nationality'):
            passport.nationality = mrz_data['nationality']
        if mrz_data.get('sex'):
            passport.sex = mrz_data['sex']
        if mrz_data.get('expiration_date'):
            passport.expiry_date = mrz_data['expiration_date']
        
        return passport
