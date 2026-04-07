import cv2
import numpy as np
from typing import Tuple
from app.services.yolo_detector import yolo_detector


def deskew_image(image: np.ndarray, max_skew_angle: float = 5.0) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.bitwise_not(gray)
    coords = np.column_stack(np.where(gray > 0))

    if len(coords) < 100:
        return image

    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    if abs(angle) > max_skew_angle:
        angle = 0.0

    if abs(angle) > 0.1:
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(
            image,
            M,
            (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )
        return rotated

    return image


def denoise_image(image: np.ndarray) -> np.ndarray:
    """Мягкое шумоподавление - не слишком агрессивное, чтобы не размывать текст."""
    denoised = cv2.fastNlMeansDenoisingColored(image, None, 6, 6, 7, 15)
    return denoised


def enhance_contrast(image: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    l_enhanced = clahe.apply(l)
    enhanced = cv2.merge([l_enhanced, a, b])
    return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)


def preprocess_for_ocr(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        15,  # Увеличили размер блока для лучшей адаптации
        4,   # Увеличили константу
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    return cleaned


def preprocess_for_mrz(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    mrz_roi = gray[int(h * 0.75) :, :]
    mrz_enhanced = cv2.GaussianBlur(mrz_roi, (3, 3), 0)
    mrz_enhanced = cv2.threshold(
        mrz_enhanced,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU,
    )[1]
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 1))
    mrz_enhanced = cv2.morphologyEx(mrz_enhanced, cv2.MORPH_CLOSE, kernel)
    return mrz_enhanced


def preprocess_image(image: np.ndarray) -> dict:
    rotation = yolo_detector.detect_rotation(image)
    if abs(rotation) > 1:
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, float(rotation), 1.0)
        image = cv2.warpAffine(
            image,
            M,
            (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )

    detected, doc_found = yolo_detector.detect_document(image)

    if not doc_found:
        detected = deskew_image(image)

    denoised = denoise_image(detected)
    enhanced = enhance_contrast(denoised)

    result = {
        "full": enhanced,
        "ocr_ready": preprocess_for_ocr(enhanced),
        "mrz_ready": preprocess_for_mrz(enhanced),
        "doc_detected": doc_found,
    }

    return result
