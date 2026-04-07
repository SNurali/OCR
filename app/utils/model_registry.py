from typing import Dict, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Model versioning for audit, rollback, and reproducibility."""

    def __init__(self):
        self._models: Dict[str, Dict] = {
            "face_recognition": {
                "name": "buffalo_l",
                "version": "1.0.0",
                "framework": "insightface",
                "embedding_dim": 512,
                "loaded_at": None,
                "status": "active",
            },
            "ocr_paddle": {
                "name": "paddleocr",
                "version": "2.7.3",
                "framework": "paddlepaddle",
                "languages": ["uz", "ru", "en"],
                "loaded_at": None,
                "status": "active",
            },
            "ocr_easyocr": {
                "name": "easyocr",
                "version": "1.7.1",
                "framework": "easyocr",
                "languages": ["uz", "ru", "en"],
                "loaded_at": None,
                "status": "active",
            },
            "ocr_tesseract": {
                "name": "tesseract",
                "version": "5.0",
                "framework": "pytesseract",
                "languages": ["uzb", "rus", "eng"],
                "loaded_at": None,
                "status": "active",
            },
            "yolo_detection": {
                "name": "yolov8",
                "version": "8.1.0",
                "framework": "ultralytics",
                "loaded_at": None,
                "status": "fallback",
            },
            "liveness": {
                "name": "rule_based_liveness",
                "version": "1.0.0",
                "framework": "opencv",
                "loaded_at": None,
                "status": "active",
            },
            "anti_spoof": {
                "name": "rule_based_antispoof",
                "version": "1.0.0",
                "framework": "opencv",
                "loaded_at": None,
                "status": "active",
            },
        }

    def get_model(self, model_key: str) -> Optional[Dict]:
        return self._models.get(model_key)

    def set_loaded(self, model_key: str):
        if model_key in self._models:
            self._models[model_key]["loaded_at"] = datetime.utcnow().isoformat()
            self._models[model_key]["status"] = "active"

    def set_fallback(self, model_key: str):
        if model_key in self._models:
            self._models[model_key]["status"] = "fallback"

    def get_active_versions(self) -> Dict[str, str]:
        return {key: f"{m['name']}_{m['version']}" for key, m in self._models.items()}

    def get_audit_info(self) -> Dict:
        return {
            key: {
                "name": m["name"],
                "version": m["version"],
                "framework": m["framework"],
                "status": m["status"],
                "loaded_at": m["loaded_at"],
            }
            for key, m in self._models.items()
        }

    def register_model(
        self, key: str, name: str, version: str, framework: str, **kwargs
    ):
        self._models[key] = {
            "name": name,
            "version": version,
            "framework": framework,
            "loaded_at": None,
            "status": "inactive",
            **kwargs,
        }


model_registry = ModelRegistry()
