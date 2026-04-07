#!/usr/bin/env python3
"""
Тестирование OCR на примере данных из предоставленного скриншота.
"""
import sys
sys.path.insert(0, 'src')

from mrz_parser import MRZParser
from post_processor import FieldCorrector


def test_mrz_parsing():
    """Тест парсинга MRZ из предоставленных данных."""
    print("=" * 60)
    print("ТЕСТ: Парсинг MRZ")
    print("=" * 60)
    
    parser = MRZParser()
    
    # MRZ из предоставленного OCR текста
    # Строка 1: P<UZBSULAYMANOV<<NURALI<<<<<<<<<<<<<<<<<<<<<<
    # Строка 2: AA12345678UZB9609154M2203247<<<<<<<<<<<<<<02
    
    # Попробуем восстановить из сырого текста
    raw_mrz_line1 = "IUUZBAD11 915 837315 0986 0230078 <"
    raw_mrz_line2 = "8 6 0 915 5 М3 203237XXXUZB <<<<<<<< 0"
    
    # Очистка
    line1 = "".join(c for c in raw_mrz_line1.upper() if c.isalnum() or c == '<')
    line2 = "".join(c for c in raw_mrz_line2.upper() if c.isalnum() or c == '<')
    
    print(f"Raw Line 1: {raw_mrz_line1}")
    print(f"Cleaned Line 1: {line1}")
    print(f"Raw Line 2: {raw_mrz_line2}")
    print(f"Cleaned Line 2: {line2}")
    print()
    
    # Попробуем с идеальной MRZ
    test_line1 = "P<UZBSULAYMANOV<<NURALI<<<<<<<<<<<<<<<<<<<<<<"
    test_line2 = "AA7979278UZB9609154M3203237<<<<<<<<<<<<<<<02"
    
    print(f"Test Line 1: {test_line1}")
    print(f"Test Line 2: {test_line2}")
    print()
    
    result = parser.parse(test_line1, test_line2)
    
    print(f"Document Type: {result.document_type}")
    print(f"Issuing Country: {result.issuing_country}")
    print(f"Surname: {result.surname}")
    print(f"Given Names: {result.given_names}")
    print(f"Passport Number: {result.passport_number}")
    print(f"Nationality: {result.nationality}")
    print(f"Date of Birth (raw): {result.date_of_birth}")
    print(f"Date of Birth (formatted): {parser.format_date(result.date_of_birth)}")
    print(f"Sex: {result.sex}")
    print(f"Expiration Date (raw): {result.expiration_date}")
    print(f"Expiration Date (formatted): {parser.format_date(result.expiration_date)}")
    print(f"Personal Number: {result.personal_number}")
    print(f"MRZ Valid: {result.is_valid}")
    print(f"Errors: {result.errors}")
    print()


def test_field_correction():
    """Тест коррекции полей."""
    print("=" * 60)
    print("ТЕСТ: Коррекция полей")
    print("=" * 60)
    
    corrector = FieldCorrector()
    
    # Тестовые данные из OCR
    test_cases = [
        ("FSULAYMAMOV", True, "SULAYMANOV"),  # Фамилия с ошибкой
        ("KmURALI", False, "NURALI"),         # Имя с артефактом
        ("AMIRJONOVIC", False, "AMIRJONOVICH"), # Отчество
        ("15,09.1996", False, "15.09.1996"),  # Дата
        ("24.03.2022", False, "24.03.2022"),  # Дата выдачи
    ]
    
    for original, is_surname, expected in test_cases:
        if is_surname:
            result = corrector.correct_name(original, is_surname=True)
        elif "." in original:
            result = corrector.correct_date(original)
        else:
            result = corrector.correct_name(original, is_surname=False)
        
        status = "✓" if result == expected else "✗"
        print(f"{status} '{original}' -> '{result}' (expected: '{expected}')")
    
    print()
    print("Corrections made:", corrector.corrections_made)
    print()


def test_from_raw_ocr():
    """Тест обработки сырого OCR текста."""
    print("=" * 60)
    print("ТЕСТ: Обработка сырого OCR текста")
    print("=" * 60)
    
    raw_text = """OZBEKISTON RESPUBLIKASI
SHAXS GUVOHNOMASI
5
FSULAYMAMOV
KmURALI
AMIRJONOVIC
71Daln n
15,09.1996
ERKAK
Пlata neNi
24.03.2022
0 ZHEKISTON
{ala demplry
23,03.2032
4DII91583
AN79792
91509860230078
TOSHKEN
IIV 26283"""
    
    print("Raw OCR text:")
    print(raw_text)
    print()
    
    # Извлечение полей
    import re
    
    fields = {}
    lines = raw_text.split('\n')
    
    for line in lines:
        line = line.strip().upper()
        
        # Фамилия
        if 'SULAYM' in line:
            fields['surname'] = line
        
        # Имя
        if 'NURALI' in line:
            fields['given_name'] = line
        
        # Отчество
        if 'AMIRJON' in line:
            fields['patronymic'] = line
        
        # Дата рождения
        if re.match(r'\d{1,2}[.,]\d{1,2}[.,]1996', line):
            fields['date_of_birth'] = line
        
        # Дата выдачи
        if re.match(r'\d{1,2}[.,]\d{1,2}[.,]2022', line):
            fields['issue_date'] = line
        
        # Срок действия
        if re.match(r'\d{1,2}[.,]\d{1,2}[.,]2032', line):
            fields['expiry_date'] = line
        
        # Пол
        if 'ERKAK' in line:
            fields['sex'] = 'ERKAK'
        
        # Гражданство
        if "O'ZBEKISTON" in line or 'ZBEKISTON' in line:
            fields['nationality'] = "O'ZBEKISTON"
    
    print("Extracted fields:")
    for key, value in fields.items():
        print(f"  {key}: {value}")
    print()
    
    # Коррекция
    corrector = FieldCorrector()
    
    print("Corrected fields:")
    print(f"  Surname: {corrector.correct_name(fields.get('surname', ''), True)}")
    print(f"  Given Name: {corrector.correct_name(fields.get('given_name', ''), False)}")
    print(f"  Patronymic: {corrector.correct_name(fields.get('patronymic', ''), False)}")
    print(f"  Date of Birth: {corrector.correct_date(fields.get('date_of_birth', ''))}")
    print(f"  Issue Date: {corrector.correct_date(fields.get('issue_date', ''))}")
    print(f"  Expiry Date: {corrector.correct_date(fields.get('expiry_date', ''))}")
    print(f"  Sex: {fields.get('sex', '')}")
    print(f"  Nationality: {fields.get('nationality', '')}")


if __name__ == '__main__':
    test_mrz_parsing()
    print("\n")
    test_field_correction()
    print("\n")
    test_from_raw_ocr()
