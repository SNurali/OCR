"""Document detection module: YOLO-based document detection + rotation."""

import cv2
import numpy as np
from typing import Tuple, Optional
import logging
import os

logger = logging.getLogger(__name__)


class DocumentDetector:
    """Detects document boundaries and rotation in images."""

    def __init__(self):
        self._model = None
        self._initialized = False

    def _init_model(self):
        if self._initialized:
            return
        try:
            from ultralytics import YOLO

            model_path = os.environ.get(
                "YOLO_MODEL_PATH", "models/passport_detector.pt"
            )
            if os.path.exists(model_path):
                self._model = YOLO(model_path)
                logger.info(f"YOLO detector loaded from {model_path}")
            else:
                logger.warning(
                    f"YOLO model not found at {model_path}, using fallback detection"
                )
        except ImportError:
            logger.warning("ultralytics not installed, using fallback detection")
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
        self._initialized = True

    def detect(self, image: np.ndarray) -> Tuple[np.ndarray, bool]:
        """Detect document and return cropped image + success flag."""
        self._init_model()

        if self._model is not None:
            return self._detect_yolo(image)

        return self._detect_fallback(image)

    def _detect_yolo(self, image: np.ndarray) -> Tuple[np.ndarray, bool]:
        """YOLO-based document detection."""
        try:
            results = self._model(image, conf=0.5, verbose=False)
            if results and len(results) > 0:
                boxes = results[0].boxes
                if boxes is not None and len(boxes) > 0:
                    best_idx = boxes.conf.argmax()
                    x1, y1, x2, y2 = map(int, boxes.xyxy[best_idx].tolist())
                    h, w = image.shape[:2]
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(w, x2), min(h, y2)
                    cropped = image[y1:y2, x1:x2]
                    if cropped.size > 0:
                        logger.info(
                            f"YOLO detected document: {cropped.shape}, conf={boxes.conf[best_idx]:.2f}"
                        )
                        return cropped, True
        except Exception as e:
            logger.error(f"YOLO detection failed: {e}")
        return image, False

    def _detect_fallback(self, image: np.ndarray) -> Tuple[np.ndarray, bool]:
        """Fallback: edge-based document detection."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(blurred, 50, 150)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        dilated = cv2.dilate(edged, kernel, iterations=2)

        contours, _ = cv2.findContours(
            dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours:
            return image, False

        largest = max(contours, key=cv2.contourArea)
        area_ratio = cv2.contourArea(largest) / (image.shape[0] * image.shape[1])

        if area_ratio < 0.1:
            return image, False

        x, y, w, h = cv2.boundingRect(largest)
        cropped = image[y : y + h, x : x + w]
        logger.info(f"Fallback detection: {cropped.shape}, area_ratio={area_ratio:.2f}")
        return cropped, True

    def detect_rotation(self, image: np.ndarray) -> float:
        """Detect skew angle using minAreaRect."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.bitwise_not(gray)
        coords = np.column_stack(np.where(gray > 0))

        if len(coords) < 100:
            return 0.0

        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        if abs(angle) > 5.0:
            return 0.0

        return angle


document_detector = DocumentDetector()
