"""Circuit breaker for OCR engines.

Prevents cascading failures by disabling engines that repeatedly fail.
"""

import time
import logging
from enum import Enum
from typing import Dict, Optional
from threading import Lock

from app.config import settings

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Per-engine circuit breaker.

    States:
        CLOSED   — engine is healthy, requests flow normally
        OPEN     — engine has failed too many times, requests are blocked
        HALF_OPEN — recovery timeout elapsed, one test request allowed
    """

    def __init__(
        self,
        failure_threshold: int = settings.CIRCUIT_FAILURE_THRESHOLD,
        recovery_timeout: int = settings.CIRCUIT_RECOVERY_TIMEOUT,
        success_threshold: int = settings.CIRCUIT_SUCCESS_THRESHOLD,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if self._last_failure_time and (
                    time.time() - self._last_failure_time >= self.recovery_timeout
                ):
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                    logger.info("Circuit breaker transitioning to HALF_OPEN")
            return self._state

    def allow_request(self) -> bool:
        """Return True if the request should be allowed through."""
        current_state = self.state
        if current_state == CircuitState.CLOSED:
            return True
        if current_state == CircuitState.HALF_OPEN:
            return True
        return False

    def record_success(self):
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    logger.info("Circuit breaker transitioning to CLOSED (recovered)")
            else:
                self._failure_count = max(0, self._failure_count - 1)

    def record_failure(self):
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit breaker transitioning to OPEN (test request failed)"
                )
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit breaker OPEN after %d failures", self._failure_count
                )

    def reset(self):
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None

    def get_status(self) -> Dict:
        return {
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure_time": self._last_failure_time,
        }


class CircuitBreakerRegistry:
    """Global registry of circuit breakers per OCR engine."""

    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = Lock()

    def get(self, engine_name: str) -> CircuitBreaker:
        with self._lock:
            if engine_name not in self._breakers:
                self._breakers[engine_name] = CircuitBreaker()
            return self._breakers[engine_name]

    def get_all_status(self) -> Dict[str, Dict]:
        with self._lock:
            return {name: cb.get_status() for name, cb in self._breakers.items()}

    def reset_all(self):
        with self._lock:
            for cb in self._breakers.values():
                cb.reset()


circuit_breakers = CircuitBreakerRegistry()
