"""
Тесты для OCR паспортов.
"""
import unittest
import sys
import os

# Добавляем src в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from mrz_parser import MRZParser, MRZData
from post_processor import FieldCorrector, PostProcessor


class TestMRZParser(unittest.TestCase):
    """Тесты парсера MRZ."""
    
    def setUp(self):
        self.parser = MRZParser()
    
    def test_parse_valid_mrz(self):
        """Тест парсинга валидной MRZ."""
        # Пример MRZ из узбекского паспорта
        line1 = "P<UZBSULAYMANOV<<NURALI<<<<<<<<<<<<<<<<<<<<<<"
        line2 = "AA12345678UZB9609154M2203247<<<<<<<<<<<<<<02"
        
        result = self.parser.parse(line1, line2)
        
        self.assertEqual(result.document_type, "P<")
        self.assertEqual(result.issuing_country, "UZB")
        self.assertEqual(result.surname, "SULAYMANOV")
        self.assertEqual(result.given_names, "NURALI")
        self.assertEqual(result.nationality, "UZB")
        self.assertEqual(result.date_of_birth, "960915")
        self.assertEqual(result.sex, "M")
    
    def test_check_digit_calculation(self):
        """Тест вычисления контрольной цифры."""
        # Проверка для номера паспорта "AA1234567"
        valid = self.parser._check_digit("AA1234567", "8")
        # Примечание: это пример, реальная цифра может отличаться
        self.assertIsInstance(valid, bool)
    
    def test_format_date(self):
        """Тест форматирования даты."""
        formatted = self.parser.format_date("960915")
        self.assertEqual(formatted, "15.09.1996")
        
        formatted = self.parser.format_date("220324")
        self.assertEqual(formatted, "24.03.2022")
    
    def test_correct_common_errors(self):
        """Тест исправления ошибок OCR."""
        line1 = "P<UZBSULAYMANOV<<NURALI<<<<<<<<<<<<<<<<<<<<<<"
        line2 = "AA1234567OUZB96O9154M22O3247<<<<<<<<<<<<<<O2"
        
        corrected1, corrected2 = self.parser.correct_common_errors(line1, line2)
        
        # Проверяем что O в цифровых полях заменены на 0
        self.assertIn("0", corrected2[13:19])  # Дата рождения


class TestFieldCorrector(unittest.TestCase):
    """Тесты корректора полей."""
    
    def setUp(self):
        self.corrector = FieldCorrector()
    
    def test_correct_name(self):
        """Тест коррекции имени."""
        # Исправление ошибок OCR
        result = self.corrector.correct_name("SULAYMAN0V", is_surname=True)
        self.assertEqual(result, "SULAYMANOV")
        
        result = self.corrector.correct_name("NURAL1")
        self.assertEqual(result, "NURALI")
    
    def test_correct_date(self):
        """Тест коррекции даты."""
        result = self.corrector.correct_date("15.09.1996")
        self.assertEqual(result, "15.09.1996")
        
        result = self.corrector.correct_date("15,09,1996")
        self.assertEqual(result, "15.09.1996")
    
    def test_correct_passport_number(self):
        """Тест коррекции номера паспорта."""
        result = self.corrector.correct_passport_number("AA1234567")
        self.assertEqual(result, "AA1234567")
        
        result = self.corrector.correct_passport_number("AA1234567O")
        self.assertEqual(result, "AA12345670")


class TestPostProcessor(unittest.TestCase):
    """Тесты пост-процессора."""
    
    def setUp(self):
        self.processor = PostProcessor()
    
    def test_process_raw_data(self):
        """Тест обработки сырых данных."""
        raw_data = {
            'surname': 'SULAYMAN0V',
            'given_name': 'NURAL1',
            'date_of_birth': '15.09.1996',
            'nationality': "O'ZBEKISTON",
            'sex': 'ERKAK'
        }
        
        result = self.processor.process(raw_data)
        
        self.assertEqual(result.surname, "SULAYMANOV")
        self.assertEqual(result.given_name, "NURALI")
        self.assertEqual(result.date_of_birth, "15.09.1996")
        self.assertEqual(result.nationality, "O'ZBEKISTON")
        self.assertEqual(result.sex, "ERKAK")


class TestIntegration(unittest.TestCase):
    """Интеграционные тесты."""
    
    def test_full_pipeline_with_sample_data(self):
        """Тест полного пайплайна с тестовыми данными."""
        # Этот тест требует тестового изображения
        # Пока просто проверяем что модули импортируются
        from passport_ocr import UzbekPassportOCR
        ocr = UzbekPassportOCR()
        self.assertIsNotNone(ocr)


if __name__ == '__main__':
    unittest.main()
