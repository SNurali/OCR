"""
IP-based throttling for upload abuse prevention.
Uses Redis to track upload frequency per IP.
"""

import redis
import logging
from typing import Tuple

from app.config import settings

logger = logging.getLogger(__name__)

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

UPLOAD_LIMIT_PER_HOUR = 100
UPLOAD_LIMIT_PER_DAY = 500
SUSPICIOUS_THRESHOLD = 200


def check_ip_throttle(ip: str) -> Tuple[bool, str]:
    """
    Check if IP exceeded upload limits.

    Returns:
        (is_throttled, reason)
    """
    if not ip or ip == "unknown":
        return False, ""

    hour_key = f"upload:ip:{ip}:hour"
    day_key = f"upload:ip:{ip}:day"

    hour_count = int(redis_client.get(hour_key) or 0)
    day_count = int(redis_client.get(day_key) or 0)

    if hour_count >= UPLOAD_LIMIT_PER_HOUR:
        logger.warning(
            "IP throttled (hourly): IP=%s, count=%d, limit=%d",
            ip,
            hour_count,
            UPLOAD_LIMIT_PER_HOUR,
        )
        return True, f"Hourly upload limit exceeded ({UPLOAD_LIMIT_PER_HOUR}/hour)"

    if day_count >= UPLOAD_LIMIT_PER_DAY:
        logger.warning(
            "IP throttled (daily): IP=%s, count=%d, limit=%d",
            ip,
            day_count,
            UPLOAD_LIMIT_PER_DAY,
        )
        return True, f"Daily upload limit exceeded ({UPLOAD_LIMIT_PER_DAY}/day)"

    return False, ""


def record_upload(ip: str) -> None:
    """Record an upload for IP throttling."""
    if not ip or ip == "unknown":
        return

    hour_key = f"upload:ip:{ip}:hour"
    day_key = f"upload:ip:{ip}:day"

    pipe = redis_client.pipeline()
    pipe.incr(hour_key)
    pipe.incr(day_key)
    pipe.expire(hour_key, 3600)
    pipe.expire(day_key, 86400)
    pipe.execute()

    new_count = int(redis_client.get(day_key) or 0)
    if new_count >= SUSPICIOUS_THRESHOLD:
        logger.warning(
            "Suspicious IP activity: IP=%s, daily_count=%d, threshold=%d",
            ip,
            new_count,
            SUSPICIOUS_THRESHOLD,
        )
