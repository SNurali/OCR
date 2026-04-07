"""
Сервис дедупликации паспортных записей.

- SHA256 хеш изображения (точные дубликаты)
- Perceptual hash / aHash (похожие фото: разные углы, освещение, качество)
- Поиск по passport_number
- Возврат существующей записи при дубликате
"""

import hashlib
import logging
from typing import Optional, Tuple

import cv2
import numpy as np
from sqlalchemy.orm import Session

from app.models import PassportData

logger = logging.getLogger(__name__)


def compute_image_hash(file_bytes: bytes) -> str:
    """SHA256 хеш содержимого файла (точные дубликаты)."""
    return hashlib.sha256(file_bytes).hexdigest()


def compute_perceptual_hash(image_cv: np.ndarray, hash_size: int = 16) -> str:
    """
    Perceptual hash (average hash) изображения.
    Устойчив к: изменению размера, освещению, углу, качеству.
    Возвращает hex-строку длиной hash_size*2 символов.
    """
    gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (hash_size, hash_size), interpolation=cv2.INTER_AREA)
    avg = resized.mean()
    bits = (resized > avg).astype(np.uint8).flatten()

    hex_hash = ""
    for i in range(0, len(bits), 4):
        nibble = int("".join(str(b) for b in bits[i : i + 4]), 2)
        hex_hash += format(nibble, "x")

    return hex_hash


def hamming_distance(hash1: str, hash2: str) -> int:
    """Расстояние Хэмминга между двумя hex-хешами."""
    if len(hash1) != len(hash2):
        return 64
    n1 = int(hash1, 16)
    n2 = int(hash2, 16)
    xor = n1 ^ n2
    return bin(xor).count("1")


def perceptual_similarity(hash1: str, hash2: str) -> float:
    """Схожесть двух perceptual hash (0.0 - 1.0)."""
    max_bits = len(hash1) * 4
    distance = hamming_distance(hash1, hash2)
    return 1.0 - (distance / max_bits)


def find_existing_by_hash(db: Session, image_hash: str) -> Optional[PassportData]:
    """Поиск существующей записи по SHA256 хешу изображения."""
    return db.query(PassportData).filter(PassportData.image_hash == image_hash).first()


def find_existing_by_perceptual_hash(
    db: Session, perceptual_hash: str, threshold: float = 0.85
) -> Optional[PassportData]:
    """
    Поиск по perceptual hash среди записей с валидными паспортными данными.
    threshold: минимальная схожесть для совпадения (0.85 = ~97% похожих пикселей).
    """
    candidates = (
        db.query(PassportData)
        .filter(
            PassportData.perceptual_hash.isnot(None),
            PassportData.passport_number.isnot(None),
        )
        .all()
    )

    best_match = None
    best_similarity = 0.0

    for candidate in candidates:
        sim = perceptual_similarity(perceptual_hash, candidate.perceptual_hash)
        if sim > best_similarity and sim >= threshold:
            best_similarity = sim
            best_match = candidate

    if best_match:
        logger.info(
            "Perceptual hash match: task_id=%s, similarity=%.3f, passport=%s",
            best_match.task_id,
            best_similarity,
            best_match.passport_number,
        )

    return best_match


def find_existing_by_passport(
    db: Session, passport_number: str
) -> Optional[PassportData]:
    """Поиск существующей записи по номеру паспорта."""
    if not passport_number or not passport_number.strip():
        return None
    return (
        db.query(PassportData)
        .filter(PassportData.passport_number == passport_number.strip())
        .order_by(PassportData.created_at.desc())
        .first()
    )


def check_duplicate(
    db: Session,
    image_hash: str,
    perceptual_hash: Optional[str] = None,
    passport_number: Optional[str] = None,
) -> Tuple[bool, Optional[PassportData], int]:
    """
    Проверяет дубликат по SHA256, perceptual hash или номеру паспорта.

    Returns:
        (is_duplicate, existing_record, duplicate_count)
    """
    by_hash = find_existing_by_hash(db, image_hash)
    if by_hash:
        logger.info(
            "Duplicate detected by SHA256: task_id=%s, hash=%s",
            by_hash.task_id,
            image_hash[:12],
        )
        return True, by_hash, by_hash.duplicate_count or 1

    if perceptual_hash:
        by_phash = find_existing_by_perceptual_hash(db, perceptual_hash)
        if by_phash:
            logger.info(
                "Duplicate detected by perceptual hash: task_id=%s, passport=%s",
                by_phash.task_id,
                by_phash.passport_number,
            )
            return True, by_phash, by_phash.duplicate_count or 1

    if passport_number and passport_number.strip():
        by_passport = find_existing_by_passport(db, passport_number)
        if by_passport:
            logger.info(
                "Duplicate detected by passport_number: task_id=%s, number=%s",
                by_passport.task_id,
                passport_number,
            )
            return True, by_passport, by_passport.duplicate_count or 1

    return False, None, 0


def increment_duplicate_count(db: Session, record: PassportData) -> int:
    """Увеличивает счётчик дубликатов и сохраняет."""
    record.duplicate_count = (record.duplicate_count or 1) + 1
    db.commit()
    db.refresh(record)
    logger.info(
        "Duplicate count incremented: task_id=%s, count=%d",
        record.task_id,
        record.duplicate_count,
    )
    return record.duplicate_count
