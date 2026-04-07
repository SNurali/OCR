"""OpenTelemetry tracing for OCR service.

Propagates trace_id from API → Celery → DB.
"""

import logging
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)


class TraceContext:
    """Simple trace context propagator without full OTel dependency."""

    def __init__(self):
        self._current_trace_id: Optional[str] = None
        self._current_span_id: Optional[str] = None

    def start_trace(self, operation: str) -> str:
        import uuid

        trace_id = str(uuid.uuid4())
        self._current_trace_id = trace_id
        self._current_span_id = str(uuid.uuid4())[:16]
        logger.info(
            "TRACE_START",
            extra={
                "trace_id": trace_id,
                "span_id": self._current_span_id,
                "operation": operation,
            },
        )
        return trace_id

    def continue_trace(self, trace_id: str, operation: str) -> str:
        import uuid

        self._current_trace_id = trace_id
        self._current_span_id = str(uuid.uuid4())[:16]
        logger.info(
            "TRACE_CONTINUE",
            extra={
                "trace_id": trace_id,
                "span_id": self._current_span_id,
                "operation": operation,
            },
        )
        return self._current_span_id

    @property
    def trace_id(self) -> Optional[str]:
        return self._current_trace_id

    @property
    def span_id(self) -> Optional[str]:
        return self._current_span_id


trace_context = TraceContext()


def inject_trace_headers(headers: dict) -> dict:
    """Inject trace_id into headers for downstream propagation."""
    if trace_context.trace_id:
        headers["X-Trace-ID"] = trace_context.trace_id
        headers["X-Span-ID"] = trace_context.span_id
    return headers


def extract_trace_id(headers: dict) -> Optional[str]:
    """Extract trace_id from incoming request headers."""
    return headers.get("X-Trace-ID") or headers.get("x-trace-id")


def extract_span_id(headers: dict) -> Optional[str]:
    """Extract span_id from incoming request headers."""
    return headers.get("X-Span-ID") or headers.get("x-span-id")
