import hashlib
import json
import logging
import redis
from typing import Optional
import numpy as np
from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingCache:
    """Redis cache for face embeddings."""

    def __init__(self):
        self.redis_client = None
        self.ttl = 3600
        self._connect()

    def _connect(self):
        try:
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=2,
                socket_connect_timeout=2,
            )
            self.redis_client.ping()
        except Exception as e:
            logger.warning(f"Redis cache unavailable: {e}")
            self.redis_client = None

    def _compute_hash(self, image_bytes: bytes) -> str:
        return hashlib.sha256(image_bytes).hexdigest()

    def get(self, image_bytes: bytes) -> Optional[np.ndarray]:
        if not self.redis_client:
            return None

        try:
            key = f"emb:{self._compute_hash(image_bytes)}"
            data = self.redis_client.get(key)
            if data:
                parsed = json.loads(data)
                return np.array(parsed["embedding"], dtype=np.float32)
        except Exception as e:
            logger.error(f"Cache get error: {e}")

        return None

    def put(self, image_bytes: bytes, embedding: np.ndarray, quality: float = 0.0):
        if not self.redis_client:
            return

        try:
            key = f"emb:{self._compute_hash(image_bytes)}"
            data = {
                "embedding": embedding.tolist(),
                "quality": quality,
            }
            self.redis_client.setex(key, self.ttl, json.dumps(data))
        except Exception as e:
            logger.error(f"Cache put error: {e}")

    def invalidate(self, image_bytes: bytes):
        if not self.redis_client:
            return
        try:
            key = f"emb:{self._compute_hash(image_bytes)}"
            self.redis_client.delete(key)
        except Exception:
            pass

    def get_attempt_count(self, user_id: int, window_seconds: int = 3600) -> int:
        if not self.redis_client:
            return 0
        try:
            key = f"attempts:{user_id}"
            count = self.redis_client.get(key)
            return int(count) if count else 0
        except Exception:
            return 0

    def increment_attempt(self, user_id: int, window_seconds: int = 3600):
        if not self.redis_client:
            return
        try:
            key = f"attempts:{user_id}"
            pipe = self.redis_client.pipeline()
            pipe.incr(key)
            pipe.expire(key, window_seconds)
            pipe.execute()
        except Exception:
            pass

    def get_device_risk(self, ip_address: str) -> float:
        if not self.redis_client:
            return 0.0
        try:
            key = f"device_risk:{ip_address}"
            data = self.redis_client.get(key)
            if data:
                return float(json.loads(data).get("risk", 0.0))
        except Exception:
            pass
        return 0.0

    def set_device_risk(self, ip_address: str, risk: float):
        if not self.redis_client:
            return
        try:
            key = f"device_risk:{ip_address}"
            self.redis_client.setex(
                key, 86400, json.dumps({"risk": risk, "updated": True})
            )
        except Exception:
            pass


embedding_cache = EmbeddingCache()
redis_client = embedding_cache.redis_client
