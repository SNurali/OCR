"""Preprocessing module: auto-crop, deskew, noise reduction, contrast enhancement."""

import cv2
import numpy as np
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


def auto_crop(image: np.ndarray) -> np.ndarray:
    """Auto-crop to document boundaries using edge detection."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 50, 150)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    dilated = cv2.dilate(edged, kernel, iterations=2)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return image

    largest = max(contours, key=cv2.contourArea)
    if len(largest) < 3:
        return image
    img_pts = np.array(
        [
            [0, 0],
            [image.shape[1], 0],
            [image.shape[1], image.shape[0]],
            [0, image.shape[0]],
        ],
        dtype=np.float32,
    )
    if cv2.contourArea(largest) < cv2.contourArea(img_pts) * 0.1:
        return image

    peri = cv2.arcLength(largest, True)
    approx = cv2.approxPolyDP(largest, 0.02 * peri, True)

    if len(approx) == 4:
        pts = approx.reshape(4, 2)
        rect = _order_points(pts)
        (tl, tr, br, bl) = rect

        width_a = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        width_b = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        max_width = max(int(width_a), int(width_b))

        height_a = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        height_b = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        max_height = max(int(height_a), int(height_b))

        dst = np.array(
            [
                [0, 0],
                [max_width - 1, 0],
                [max_width - 1, max_height - 1],
                [0, max_height - 1],
            ],
            dtype="float32",
        )

        M = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(image, M, (max_width, max_height))
        logger.info(f"Auto-crop applied: {warped.shape}")
        return warped

    x, y, w, h = cv2.boundingRect(largest)
    cropped = image[y : y + h, x : x + w]
    logger.info(f"Bounding rect crop applied: {cropped.shape}")
    return cropped


def _order_points(pts: np.ndarray) -> np.ndarray:
    """Order points: top-left, top-right, bottom-right, bottom-left."""
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def deskew(image: np.ndarray, max_angle: float = 5.0) -> np.ndarray:
    """Deskew image using Hough line transform."""
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

    if abs(angle) > max_angle:
        angle = 0.0

    if abs(angle) < 0.1:
        return image

    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )
    logger.info(f"Deskewed by {angle:.2f} degrees")
    return rotated


def reduce_noise(image: np.ndarray) -> np.ndarray:
    """Non-local means denoising."""
    denoised = cv2.fastNlMeansDenoisingColored(image, None, 6, 6, 7, 15)
    return denoised


def enhance_contrast(image: np.ndarray) -> np.ndarray:
    """CLAHE-based contrast enhancement."""
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    l_enhanced = clahe.apply(l)
    enhanced = cv2.merge([l_enhanced, a, b])
    return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)


def preprocess_for_ocr(image: np.ndarray) -> np.ndarray:
    """Binary threshold preprocessing for OCR engines."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 4
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    return cleaned


def preprocess_for_mrz(image: np.ndarray) -> np.ndarray:
    """Preprocess MRZ zone for optimal character recognition."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    mrz_roi = gray[int(h * 0.75) :, :]
    mrz_enhanced = cv2.GaussianBlur(mrz_roi, (3, 3), 0)
    mrz_enhanced = cv2.threshold(
        mrz_enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )[1]
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 1))
    mrz_enhanced = cv2.morphologyEx(mrz_enhanced, cv2.MORPH_CLOSE, kernel)
    return mrz_enhanced


def preprocess_full(image: np.ndarray) -> dict:
    """
    Full preprocessing pipeline:
    1. Auto-crop
    2. Deskew
    3. Noise reduction
    4. Contrast enhancement
    5. OCR-ready binary
    6. MRZ-ready binary
    """
    cropped = auto_crop(image)
    deskewed = deskew(cropped)
    denoised = reduce_noise(deskewed)
    enhanced = enhance_contrast(denoised)

    return {
        "enhanced": enhanced,
        "ocr_ready": preprocess_for_ocr(enhanced),
        "mrz_ready": preprocess_for_mrz(enhanced),
        "doc_detected": True,
    }
