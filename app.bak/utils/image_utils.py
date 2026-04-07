"""Image processing utilities for OCR pipeline."""

import hashlib
import cv2
import numpy as np
from PIL import Image
import imagehash
from typing import Tuple, Optional


def preprocess_image(image: Image.Image) -> Image.Image:
    """Preprocess image for optimal OCR results."""
    # Convert to numpy array
    img_array = np.array(image)

    # If it's a color image, convert to grayscale
    if len(img_array.shape) == 3:
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_array

    # Apply Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)

    # Apply threshold to get binary image
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Convert back to PIL Image
    processed_image = Image.fromarray(thresh)

    return processed_image


def hash_image_sha256(image_bytes: bytes) -> str:
    """Compute SHA256 hash of image bytes."""
    return hashlib.sha256(image_bytes).hexdigest()


def hash_image_perceptual(image_cv: np.ndarray) -> str:
    """Compute perceptual hash of image."""
    if len(image_cv.shape) == 3:
        gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
    else:
        gray = image_cv

    pil_image = Image.fromarray(gray)
    phash = imagehash.phash(pil_image)
    return str(phash)


def resize_image(
    image: np.ndarray, max_size: Tuple[int, int] = (1920, 1080)
) -> np.ndarray:
    """Resize image to max dimensions while maintaining aspect ratio."""
    h, w = image.shape[:2]
    max_w, max_h = max_size

    if w <= max_w and h <= max_h:
        return image

    scale = min(max_w / w, max_h / h)
    new_w, new_h = int(w * scale), int(h * scale)

    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return resized


def rotate_image_correctly(image: np.ndarray) -> np.ndarray:
    """Rotate image to correct orientation using OCR-based detection."""
    # This is a simplified version - in production, use OCR to detect text orientation
    return image
