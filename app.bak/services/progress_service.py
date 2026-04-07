"""Redis-based progress tracking for OCR pipeline stages."""

import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

import redis

from app.config import settings

logger = logging.getLogger(__name__)

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

PROGRESS_TTL = 600  # 10 minutes
STAGE_ORDER = [
    "preprocessing",
    "detection",
    "ocr",
    "mrz",
    "parsing",
    "validation",
    "confidence",
]

STAGE_LABELS = {
    "preprocessing": "Preprocessing image",
    "detection": "Detecting document",
    "ocr": "OCR recognition",
    "mrz": "MRZ extraction",
    "parsing": "Parsing fields",
    "validation": "Validating data",
    "confidence": "Calculating confidence",
}


def publish_progress(
    task_id: str, stage: str, progress: int, details: Optional[Dict] = None
) -> None:
    """
    Store pipeline progress in Redis.

    Args:
        task_id: Task identifier
        stage: Current pipeline stage
        progress: Progress percentage (0-100)
        details: Optional stage details
    """
    key = f"ocr:progress:{task_id}"
    now = datetime.now(timezone.utc).isoformat()

    data = {
        "stage": stage,
        "progress": min(100, max(0, progress)),
        "timestamp": now,
        "details": details or {},
    }

    try:
        redis_client.setex(key, PROGRESS_TTL, json.dumps(data))
        logger.debug(
            "Progress published for %s: stage=%s, progress=%d", task_id, stage, progress
        )
    except redis.RedisError as e:
        logger.error("Failed to publish progress for %s: %s", task_id, e)


def get_progress(task_id: str) -> Optional[Dict[str, Any]]:
    """
    Get pipeline progress from Redis.

    Returns:
        Dict with stage, progress, timestamp, details or None if not found
    """
    key = f"ocr:progress:{task_id}"

    try:
        data = redis_client.get(key)
        if data:
            return json.loads(data)
    except redis.RedisError as e:
        logger.error("Failed to get progress for %s: %s", task_id, e)

    return None


def complete_progress(task_id: str, final_status: str, confidence: float = 0.0) -> None:
    """
    Mark progress as complete.

    Args:
        task_id: Task identifier
        final_status: Final status (valid, invalid, low_confidence, needs_review)
        confidence: Overall confidence score
    """
    publish_progress(
        task_id,
        stage="completed",
        progress=100,
        details={
            "final_status": final_status,
            "confidence": round(confidence, 3),
        },
    )


def error_progress(task_id: str, error_message: str) -> None:
    """
    Mark progress as errored.
    """
    publish_progress(
        task_id,
        stage="error",
        progress=0,
        details={"error": error_message},
    )


def calculate_stage_progress(current_stage: str) -> int:
    """
    Calculate overall progress percentage based on current stage.
    """
    if current_stage not in STAGE_ORDER:
        return 0

    stage_index = STAGE_ORDER.index(current_stage)
    base_progress = int((stage_index / len(STAGE_ORDER)) * 100)
    return min(95, base_progress)
