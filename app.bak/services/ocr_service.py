"""DEPRECATED: Re-exports from app.modules.ocr for backward compatibility.

Import from app.modules.ocr instead.
"""

from app.modules.ocr import OCREngine, ocr_engine


class _LazyOCRPipeline:
    """Backward compatibility wrapper for old ocr_pipeline API."""

    def __init__(self):
        self._instance = None

    def _get_instance(self):
        if self._instance is None:
            self._instance = ocr_engine
        return self._instance

    def __getattr__(self, name):
        return getattr(self._get_instance(), name)


ocr_pipeline = _LazyOCRPipeline()

__all__ = ["OCREngine", "ocr_engine", "ocr_pipeline"]
