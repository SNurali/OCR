import numpy as np


class YoloDetector:
    """Fallback detector when the YOLO-based detector is unavailable."""

    def detect_rotation(self, image: np.ndarray) -> float:
        return 0.0

    def detect_document(self, image: np.ndarray) -> tuple[np.ndarray, bool]:
        return image, False


yolo_detector = YoloDetector()
