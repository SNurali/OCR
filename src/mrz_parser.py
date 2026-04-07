"""
Парсер и валидатор MRZ (Machine Readable Zone) для паспортов.
Поддерживает формат TD3 (паспорта ICAO 9303).
"""
import re
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class MRZData:
    """Структура данных из MRZ."""
    document_type: str
    issuing_country: str
    surname: str
    given_names: str
    passport_number: str
    passport_number_check: str
    nationality: str
    date_of_birth: str
    date_of_birth_check: str
    sex: str
    expiration_date: str
    expiration_date_check: str
    personal_number: str
    personal_number_check: str
    composite_check: str
    raw_line1: str
    raw_line2: str
    is_valid: bool = False
    errors: list = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class MRZParser:
    """Парсер MRZ для паспортов формата TD3."""
    
    # Карта замены похожих символов
    CHAR_CORRECTIONS = {
        '0': 'O',  # Ноль на букву O (только в определенных позициях)
        'O': '0',  # Буква O на ноль (в цифровых полях)
        '1': 'I',  # Единица на I
        'I': '1',  # I на единицу (в цифровых полях)
        '5': 'S',  # Пятерка на S
        'S': '5',  # S на пятерку (в цифровых полях)
        '8': 'B',  # Восьмерка на B
        'B': '8',  # B на восьмерку (в цифровых полях)
    }
    
    def __init__(self):
        self.errors = []
    
    def parse(self, line1: str, line2: str) -> MRZData:
        """
        Парсинг двух строк MRZ.
        
        Args:
            line1: Первая строка MRZ (должна быть 44 символа)
            line2: Вторая строка MRZ (должна быть 44 символа)
            
        Returns:
            MRZData с распарсенными полями
        """
        self.errors = []
        
        # Очистка и нормализация
        line1 = self._clean_line(line1)
        line2 = self._clean_line(line2)
        
        # Проверка длины
        if len(line1) != 44:
            self.errors.append(f"Line 1 length is {len(line1)}, expected 44")
            line1 = line1.ljust(44, '<')
        
        if len(line2) != 44:
            self.errors.append(f"Line 2 length is {len(line2)}, expected 44")
            line2 = line2.ljust(44, '<')
        
        # Парсинг первой строки
        document_type = line1[0:2]
        issuing_country = line1[2:5]
        
        # Имя (до <<)
        name_part = line1[5:44]
        names = name_part.split('<<')
        surname = names[0].replace('<', ' ').strip()
        given_names = names[1].replace('<', ' ').strip() if len(names) > 1 else ""
        
        # Парсинг второй строки
        passport_number = line2[0:9].replace('<', '')
        passport_number_check = line2[9]
        nationality = line2[10:13]
        date_of_birth = line2[13:19]
        date_of_birth_check = line2[19]
        sex = line2[20]
        expiration_date = line2[21:27]
        expiration_date_check = line2[27]
        personal_number = line2[28:42].replace('<', '')
        personal_number_check = line2[42]
        composite_check = line2[43]
        
        mrz_data = MRZData(
            document_type=document_type,
            issuing_country=issuing_country,
            surname=surname,
            given_names=given_names,
            passport_number=passport_number,
            passport_number_check=passport_number_check,
            nationality=nationality,
            date_of_birth=date_of_birth,
            date_of_birth_check=date_of_birth_check,
            sex=sex,
            expiration_date=expiration_date,
            expiration_date_check=expiration_date_check,
            personal_number=personal_number,
            personal_number_check=personal_number_check,
            composite_check=composite_check,
            raw_line1=line1,
            raw_line2=line2,
            errors=self.errors.copy()
        )
        
        # Валидация
        mrz_data.is_valid = self._validate(mrz_data)
        
        return mrz_data
    
    def _clean_line(self, line: str) -> str:
        """Очистка строки MRZ."""
        # Удаляем все кроме допустимых символов
        line = re.sub(r'[^A-Z0-9<]', '', line.upper())
        return line
    
    def _validate(self, data: MRZData) -> bool:
        """Валидация контрольных сумм MRZ."""
        is_valid = True
        
        # Проверка контрольной цифры номера паспорта
        if not self._check_digit(data.passport_number, data.passport_number_check):
            data.errors.append("Invalid passport number check digit")
            is_valid = False
        
        # Проверка контрольной цифры даты рождения
        if not self._check_digit(data.date_of_birth, data.date_of_birth_check):
            data.errors.append("Invalid date of birth check digit")
            is_valid = False
        
        # Проверка контрольной цифры срока действия
        if not self._check_digit(data.expiration_date, data.expiration_date_check):
            data.errors.append("Invalid expiration date check digit")
            is_valid = False
        
        # Проверка контрольной цифры личного номера (если не пустой)
        if data.personal_number and data.personal_number != '':
            if not self._check_digit(data.personal_number, data.personal_number_check):
                data.errors.append("Invalid personal number check digit")
                is_valid = False
        
        # Проверка композитной контрольной суммы
        composite = data.passport_number + data.passport_number_check + \
                   data.date_of_birth + data.date_of_birth_check + \
                   data.expiration_date + data.expiration_date_check + \
                   data.personal_number + data.personal_number_check
        
        if not self._check_digit(composite, data.composite_check):
            data.errors.append("Invalid composite check digit")
            is_valid = False
        
        return is_valid
    
    def _check_digit(self, data: str, expected: str) -> bool:
        """
        Вычисление и проверка контрольной цифры по алгоритму ICAO 9303.
        
        Args:
            data: Данные для проверки
            expected: Ожидаемая контрольная цифра
            
        Returns:
            True если контрольная цифра верна
        """
        if not data:
            return False
        
        weights = [7, 3, 1]
        total = 0
        
        for i, char in enumerate(data):
            if char.isdigit():
                value = int(char)
            elif char.isalpha():
                value = ord(char) - ord('A') + 10
            elif char == '<':
                value = 0
            else:
                continue
            
            total += value * weights[i % 3]
        
        check_digit = total % 10
        return str(check_digit) == expected
    
    def correct_common_errors(self, line1: str, line2: str) -> Tuple[str, str]:
        """
        Исправление распространенных ошибок OCR в MRZ.
        
        Args:
            line1: Первая строка
            line2: Вторая строка
            
        Returns:
            Исправленные строки
        """
        # Исправляем символы в цифровых полях второй строки
        line2_corrected = list(line2)
        
        # Позиции 0-8 (номер паспорта) - буквы в цифры
        for i in range(9):
            if i < len(line2_corrected) and line2_corrected[i] in 'OISB':
                line2_corrected[i] = self.CHAR_CORRECTIONS.get(line2_corrected[i], line2_corrected[i])
        
        # Позиции 13-18 (дата рождения) - буквы в цифры
        for i in range(13, 19):
            if i < len(line2_corrected) and line2_corrected[i] in 'OISB':
                line2_corrected[i] = self.CHAR_CORRECTIONS.get(line2_corrected[i], line2_corrected[i])
        
        # Позиции 21-26 (срок действия) - буквы в цифры
        for i in range(21, 27):
            if i < len(line2_corrected) and line2_corrected[i] in 'OISB':
                line2_corrected[i] = self.CHAR_CORRECTIONS.get(line2_corrected[i], line2_corrected[i])
        
        return line1, ''.join(line2_corrected)
    
    def format_date(self, mrz_date: str) -> Optional[str]:
        """
        Форматирование даты из MRZ формата (YYMMDD) в DD.MM.YYYY.
        
        Args:
            mrz_date: Дата в формате YYMMDD
            
        Returns:
            Дата в формате DD.MM.YYYY или None
        """
        if len(mrz_date) != 6 or not mrz_date.isdigit():
            return None
        
        year = int(mrz_date[0:2])
        month = int(mrz_date[2:4])
        day = int(mrz_date[4:6])
        
        # Определяем век (если год > текущего, то это 1900-е)
        current_year = datetime.now().year % 100
        full_year = 2000 + year if year <= current_year else 1900 + year
        
        try:
            date_obj = datetime(full_year, month, day)
            return date_obj.strftime("%d.%m.%Y")
        except ValueError:
            return None
