import cv2
import numpy as np
import base64
from typing import Dict, Optional, Tuple


class FaceExtractor:
    """Извлечение фото из документа."""

    def __init__(self):
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

    def extract_face(self, image: np.ndarray) -> Optional[np.ndarray]:
        """Извлечение лица из изображения документа."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30),
            flags=cv2.CASCADE_SCALE_IMAGE,
        )

        if len(faces) == 0:
            return self._extract_by_region(image)

        x, y, w, h = faces[0]

        padding = int(w * 0.2)
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(image.shape[1], x + w + padding)
        y2 = min(image.shape[0], y + h + padding)

        face = image[y1:y2, x1:x2]
        return face

    def _extract_by_region(self, image: np.ndarray) -> Optional[np.ndarray]:
        """Извлечение фото по типичной позиции (правый верхний угол)."""
        h, w = image.shape[:2]

        photo_x1 = int(w * 0.65)
        photo_y1 = int(h * 0.05)
        photo_x2 = int(w * 0.95)
        photo_y2 = int(h * 0.35)

        if photo_x2 > photo_x1 and photo_y2 > photo_y1:
            region = image[photo_y1:photo_y2, photo_x1:photo_x2]
            if region.size > 0:
                return region

        return None

    def face_to_base64(self, face: np.ndarray) -> str:
        """Конвертация изображения лица в base64."""
        _, buffer = cv2.imencode(".jpg", face, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return base64.b64encode(buffer).decode("utf-8")

    def detect_fake_basic(self, image: np.ndarray) -> Dict:
        """Базовая детекция фейкового документа."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

        blur_score = 1.0 if laplacian_var > 100 else 0.5 if laplacian_var > 50 else 0.0

        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        saturation = np.mean(hsv[:, :, 1])
        color_score = 1.0 if saturation > 30 else 0.3

        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / (edges.shape[0] * edges.shape[1])
        edge_score = 1.0 if 0.05 < edge_density < 0.5 else 0.5

        overall_confidence = (blur_score + color_score + edge_score) / 3

        return {
            "blur_score": blur_score,
            "color_score": color_score,
            "edge_score": edge_score,
            "overall_confidence": overall_confidence,
            "likely_fake": overall_confidence < 0.4,
        }


extractor = FaceExtractor()
