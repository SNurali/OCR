"""API key authentication and rate limiting."""

import hashlib
import secrets
import logging
from datetime import datetime, timezone

import redis
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import APIKey

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key() -> tuple[str, str]:
    """Generate a new API key. Returns (raw_key, key_prefix)."""
    raw_key = f"ocr_{secrets.token_urlsafe(32)}"
    prefix = raw_key[:8]
    return raw_key, prefix


def get_api_key(
    api_key: str = Depends(api_key_header),
    db: Session = Depends(get_db),
) -> APIKey:
    """Validate API key and return the record."""
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide it via X-API-Key header.",
        )

    key_hash = hash_api_key(api_key)
    record = db.query(APIKey).filter(APIKey.key_hash == key_hash).first()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    if not record.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key is disabled",
        )

    return record


def check_rate_limit(api_key_record: APIKey) -> None:
    """Check per-key rate limits using Redis sliding window."""
    key_prefix = api_key_record.key_prefix
    now = datetime.now(timezone.utc)

    # Per-minute check
    minute_key = f"ratelimit:{key_prefix}:minute:{now.strftime('%Y%m%d%H%M')}"
    minute_count = redis_client.incr(minute_key)
    if minute_count == 1:
        redis_client.expire(minute_key, 120)

    if minute_count > api_key_record.rate_limit_per_minute:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {api_key_record.rate_limit_per_minute} requests/minute",
        )

    # Per-day check
    day_key = f"ratelimit:{key_prefix}:day:{now.strftime('%Y%m%d')}"
    day_count = redis_client.incr(day_key)
    if day_count == 1:
        redis_client.expire(day_key, 172800)

    if day_count > api_key_record.rate_limit_per_day:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily limit exceeded: {api_key_record.rate_limit_per_day} requests/day",
        )


def track_api_key_usage(api_key_record: APIKey, db: Session) -> None:
    """Update last_used_at and increment daily usage counter."""
    api_key_record.last_used_at = datetime.now(timezone.utc)
    api_key_record.daily_usage = api_key_record.daily_usage + 1
    db.commit()
