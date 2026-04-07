"""
Валидация и нормализация паспортных данных.

- Формат дат: DD.MM.YYYY
- Нормализация пола: M / F
- Нормализация гражданства: ISO 3166-1 alpha-3
- PINFL checksum (Узбекистан — 14 цифр с контрольной суммой)
- Логическая проверка (не будущее, не < 1900)
- Blacklist тестовых/фейковых данных
"""

import logging
import re
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

DATE_PATTERN = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")

GENDER_MAP = {
    "M": "M",
    "MALE": "M",
    "МУЖ": "M",
    "МУЖЧ": "M",
    "ERKAK": "M",
    "F": "F",
    "FEMALE": "F",
    "ЖЕН": "F",
    "ЖЕНЩ": "F",
    "AYOL": "F",
}

NATIONALITY_MAP = {
    "O'ZBEKISTON": "UZB",
    "UZBEKISTAN": "UZB",
    "O'ZB": "UZB",
    "UZB": "UZB",
    "РОССИЯ": "RUS",
    "RUSSIA": "RUS",
    "RUS": "RUS",
    "РОССИЙСКАЯ ФЕДЕРАЦИЯ": "RUS",
    "KAZAKHSTAN": "KAZ",
    "КАЗАХСТАН": "KAZ",
    "KAZ": "KAZ",
    "TAJIKISTAN": "TJK",
    "ТАДЖИКИСТАН": "TJK",
    "TJK": "TJK",
    "KYRGYZSTAN": "KGZ",
    "КЫРГЫЗСТАН": "KGZ",
    "KGZ": "KGZ",
    "TURKMENISTAN": "TKM",
    "ТУРКМЕНИСТАН": "TKM",
    "TKM": "TKM",
    "USA": "USA",
    "UNITED STATES": "USA",
    "CHINA": "CHN",
    "КИТАЙ": "CHN",
    "CHN": "CHN",
    "TURKEY": "TUR",
    "ТУРЦИЯ": "TUR",
    "TUR": "TUR",
    "UKRAINE": "UKR",
    "УКРАИНА": "UKR",
    "UKR": "UKR",
}

BLACKLIST_NAMES = {
    "JOHN",
    "DOE",
    "JANE",
    "TEST",
    "ИМЯ",
    "ФАМИЛИЯ",
    "ТЕСТ",
    "ERIKSSON",
    "ANNA",
    "MARIA",
    "IVAN",
    "IVANOV",
}

BLACKLIST_PASSPORTS = {"AB1234567", "AB123456", "AA0000000", "TEST001", "PP0000000"}

BLACKLIST_PINFL = {
    "12345678901234",
    "00000000000000",
    "11111111111111",
    "99999999999999",
}

MIN_BIRTH_YEAR = 1900
MAX_BIRTH_YEAR = datetime.now().year


def validate_date_format(value: str) -> bool:
    """Проверяет что дата в формате DD.MM.YYYY и логически корректна."""
    if not value or not value.strip():
        return False
    if not DATE_PATTERN.match(value.strip()):
        return False
    try:
        parts = value.strip().split(".")
        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
        if year < MIN_BIRTH_YEAR or year > MAX_BIRTH_YEAR + 10:
            return False
        if month < 1 or month > 12:
            return False
        if day < 1 or day > 31:
            return False
        datetime(year, month, day)
        return True
    except (ValueError, IndexError):
        return False


def validate_birth_date(value: str) -> bool:
    """Валидация даты рождения: DD.MM.YYYY, не будущее, >= 1900."""
    if not validate_date_format(value):
        return False
    try:
        parts = value.strip().split(".")
        birth = datetime(int(parts[2]), int(parts[1]), int(parts[0]))
        return birth <= datetime.now()
    except (ValueError, IndexError):
        return False


def validate_issue_date(value: str) -> bool:
    """Валидация даты выдачи: DD.MM.YYYY, не будущее, >= 1990."""
    if not validate_date_format(value):
        return False
    try:
        parts = value.strip().split(".")
        year = int(parts[2])
        return 1990 <= year <= datetime.now().year
    except (ValueError, IndexError):
        return False


def validate_pinfl(pinfl: str) -> bool:
    """
    Валидация PINFL (Персональный идентификационный номер физлица, Узбекистан).
    14 цифр. Последняя цифра — контрольная сумма.
    Алгоритм: сумма первых 13 цифр * весовых коэффициентов mod 11.
    """
    if not pinfl or not pinfl.strip():
        return False
    pinfl = pinfl.strip()
    if not pinfl.isdigit() or len(pinfl) != 14:
        return False

    digits = [int(d) for d in pinfl]
    weights = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]
    weighted_sum = sum(d * w for d, w in zip(digits[:13], weights))
    check = weighted_sum % 11
    if check == 10:
        check = 0

    return check == digits[13]


def normalize_gender(value: str) -> Optional[str]:
    """Нормализует пол к M/F. Возвращает None если не распознано."""
    if not value or not value.strip():
        return None
    return GENDER_MAP.get(value.strip().upper())


def normalize_nationality(value: str) -> Optional[str]:
    """Нормализует гражданство к ISO 3166-1 alpha-3."""
    if not value or not value.strip():
        return None
    return NATIONALITY_MAP.get(value.strip().upper(), value.strip().upper())


def is_blacklisted_name(name: str) -> bool:
    """Проверяет имя в blacklist тестовых данных."""
    if not name:
        return False
    clean = name.upper().replace("<", " ").strip()
    for word in clean.split():
        if word in BLACKLIST_NAMES:
            return True
    return False


def is_blacklisted_passport(passport_number: str) -> bool:
    """Проверяет номер паспорта в blacklist."""
    if not passport_number:
        return False
    return passport_number.upper().strip() in BLACKLIST_PASSPORTS


def is_blacklisted_pinfl(pinfl: str) -> bool:
    """Проверяет PINFL в blacklist."""
    if not pinfl:
        return False
    return pinfl.strip() in BLACKLIST_PINFL


def count_valid_fields(record: dict) -> int:
    """Считает количество валидных паспортных полей."""
    count = 0
    if record.get("passport_number", "").strip():
        count += 1
    if record.get("birth_date") and validate_birth_date(record["birth_date"]):
        count += 1
    if record.get("first_name", "").strip() or record.get("last_name", "").strip():
        count += 1
    if record.get("pinfl", "").strip():
        count += 1
    if record.get("mrz_valid"):
        count += 1
    return count


def is_recognized_passport(record: dict) -> bool:
    """Паспорт распознан если минимум 2 валидных поля."""
    return count_valid_fields(record) >= 2


def weighted_confidence_score(record: dict) -> float:
    """
    Весовая модель confidence:
    - passport_number: 0.35 (уникальный идентификатор)
    - mrz_valid: 0.30 (MRZ — самый надёжный источник)
    - birth_date: 0.15
    - full_name: 0.10
    - pinfl: 0.10
    """
    score = 0.0

    if record.get("passport_number", "").strip():
        score += 0.35

    if record.get("mrz_valid"):
        score += 0.30

    if record.get("birth_date") and validate_birth_date(record["birth_date"]):
        score += 0.15

    if record.get("first_name", "").strip() and record.get("last_name", "").strip():
        score += 0.10

    if record.get("pinfl", "").strip():
        if validate_pinfl(record["pinfl"]):
            score += 0.10
        else:
            score += 0.05

    return round(min(score, 1.0), 4)
