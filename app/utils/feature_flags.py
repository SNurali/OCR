import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class FeatureFlags:
    """Feature flag system — enable/disable modules without redeploy."""

    def __init__(self):
        self._flags: Dict[str, Any] = {
            "FEATURE_LIVENESS": True,
            "FEATURE_ANTI_SPOOF": True,
            "FEATURE_FACE_MATCH": True,
            "FEATURE_OCR_PADDLE": True,
            "FEATURE_OCR_EASYOCR": True,
            "FEATURE_OCR_TESSERACT": True,
            "FEATURE_YOLO_DETECTION": True,
            "FEATURE_FRAUD_CHECK": True,
            "FEATURE_SHADOW_MODE": False,
            "FEATURE_GEO_RISK": False,
            "FEATURE_EMBEDDING_CACHE": True,
            "FEATURE_RATE_LIMITING": True,
        }
        self._overrides: Dict[str, Any] = {}

    def is_enabled(self, flag: str, default: bool = True) -> bool:
        if flag in self._overrides:
            return bool(self._overrides[flag])
        return bool(self._flags.get(flag, default))

    def get_value(self, flag: str, default: Any = None) -> Any:
        if flag in self._overrides:
            return self._overrides[flag]
        return self._flags.get(flag, default)

    def set_override(self, flag: str, value: Any):
        self._overrides[flag] = value
        logger.info(f"Feature flag override: {flag} = {value}")

    def clear_override(self, flag: str):
        self._overrides.pop(flag, None)

    def get_all(self) -> Dict[str, Any]:
        result = dict(self._flags)
        result.update(self._overrides)
        return result

    def load_from_env(self):
        import os

        for key, default_val in self._flags.items():
            env_val = os.environ.get(key)
            if env_val is not None:
                if isinstance(default_val, bool):
                    self._flags[key] = env_val.lower() in ("true", "1", "yes")
                elif isinstance(default_val, (int, float)):
                    self._flags[key] = type(default_val)(env_val)
                else:
                    self._flags[key] = env_val

    def to_json(self) -> str:
        return json.dumps(self.get_all())

    def from_json(self, data: str):
        parsed = json.loads(data)
        for key, value in parsed.items():
            if key in self._flags:
                self._overrides[key] = value


feature_flags = FeatureFlags()
feature_flags.load_from_env()
