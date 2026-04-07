"""DEPRECATED: Re-exports from app.modules.validation for backward compatibility.

Import from app.modules.validation instead.
"""

from app.modules.validation import ValidationEngine, validation_engine

validator = validation_engine

__all__ = ["ValidationEngine", "validation_engine", "validator"]
