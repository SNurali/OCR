"""Production-ready structured JSON logging configuration."""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import traceback

import structlog
from pythonjsonlogger import jsonlogger


class JSONFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter for structured logging."""

    def add_fields(
        self,
        log_record: Dict[str, Any],
        record: logging.LogRecord,
        message_dict: Dict[str, Any],
    ) -> None:
        """Add standardized fields to log record."""
        super().add_fields(log_record, record, message_dict)

        # Standard fields
        log_record["timestamp"] = datetime.fromtimestamp(
            record.created, tz=timezone.utc
        ).isoformat()
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["module"] = record.module
        log_record["function"] = record.funcName
        log_record["line"] = record.lineno

        # Add trace_id if available
        if hasattr(record, "trace_id"):
            log_record["trace_id"] = record.trace_id

        # Add request_id if available
        if hasattr(record, "request_id"):
            log_record["request_id"] = record.request_id


def setup_structured_logging() -> None:
    """Setup production-ready structured logging."""

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler with JSON formatter
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(
        JSONFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )

    root_logger.addHandler(console_handler)

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def log_error(
    error: Exception,
    context: Optional[Dict[str, Any]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Log error with structured format."""
    logger = logging.getLogger(__name__)

    error_info = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "error_traceback": traceback.format_exc(),
        "context": context or {},
        "extra": extra or {},
    }

    logger.error("Error occurred", extra={"structured_error": error_info})


def log_api_call(
    endpoint: str,
    method: str,
    status_code: int,
    duration_ms: float,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    request_size: Optional[int] = None,
) -> None:
    """Log API call with structured format."""
    logger = logging.getLogger("api")

    log_data = {
        "endpoint": endpoint,
        "method": method,
        "status_code": status_code,
        "duration_ms": duration_ms,
        "user_id": user_id,
        "ip_address": ip_address,
        "request_size_bytes": request_size,
    }

    logger.info("API call", extra={"api_call": log_data})


def log_ocr_process(
    task_id: str,
    passport_number: Optional[str],
    confidence_score: Optional[float],
    processing_time: float,
    status: str,
    source: str = "unknown",
    duplicate_detected: bool = False,
    validation_errors: Optional[list] = None,
) -> None:
    """Log OCR processing with structured format."""
    logger = logging.getLogger("ocr")

    log_data = {
        "task_id": task_id,
        "passport_number": passport_number,
        "confidence_score": confidence_score,
        "processing_time_seconds": processing_time,
        "status": status,
        "source": source,
        "duplicate_detected": duplicate_detected,
        "validation_errors": validation_errors or [],
    }

    logger.info("OCR process", extra={"ocr_process": log_data})


def log_security_event(
    event_type: str,
    severity: str,
    ip_address: str,
    user_agent: str,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Log security-related events."""
    logger = logging.getLogger("security")

    log_data = {
        "event_type": event_type,
        "severity": severity,
        "ip_address": ip_address,
        "user_agent": user_agent,
        "details": details or {},
    }

    logger.warning("Security event", extra={"security_event": log_data})
