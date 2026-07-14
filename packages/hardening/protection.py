"""Hardening — connection pooling, circuit breaker, caching, production safeguards."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Callable
from uuid import uuid4

from packages.core.logging import get_logger

logger = get_logger("hardening")


class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 5, reset_timeout_seconds: int = 30):
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout = timedelta(seconds=reset_timeout_seconds)
        self.failures = 0
        self.last_failure: datetime | None = None
        self.state = "closed"

    async def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        if self.state == "open":
            if self.last_failure and datetime.now(timezone.utc) - self.last_failure > self.reset_timeout:
                self.state = "half-open"
                logger.info("circuit_half_open", name=self.name)
            else:
                raise RuntimeError(f"Circuit breaker {self.name} is open")
        try:
            result = await func(*args, **kwargs)
            if self.state == "half-open":
                self.state = "closed"
                self.failures = 0
                logger.info("circuit_closed", name=self.name)
            return result
        except Exception as e:
            self.failures += 1
            self.last_failure = datetime.now(timezone.utc)
            if self.failures >= self.failure_threshold:
                self.state = "open"
                logger.warning("circuit_opened", name=self.name, failures=self.failures)
            raise e


class SimpleCache:
    def __init__(self, ttl_seconds: int = 300):
        self._store: dict[str, tuple[Any, datetime]] = {}
        self.ttl = timedelta(seconds=ttl_seconds)

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if not entry:
            return None
        value, expires = entry
        if datetime.now(timezone.utc) > expires:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (value, datetime.now(timezone.utc) + self.ttl)

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()


class RateLimiter:
    def __init__(self, max_calls: int = 60, window_seconds: int = 60):
        self.max_calls = max_calls
        self.window = timedelta(seconds=window_seconds)
        self._calls: dict[str, list[datetime]] = {}

    def check(self, key: str) -> bool:
        now = datetime.now(timezone.utc)
        if key not in self._calls:
            self._calls[key] = []
        self._calls[key] = [t for t in self._calls[key] if now - t < self.window]
        if len(self._calls[key]) >= self.max_calls:
            return False
        self._calls[key].append(now)
        return True


class ConnectionPool:
    def __init__(self, min_size: int = 2, max_size: int = 10):
        self.min_size = min_size
        self.max_size = max_size
        self._active: dict[str, str] = {}

    def acquire(self, name: str) -> str:
        conn_id = str(uuid4())
        self._active[conn_id] = name
        return conn_id

    def release(self, conn_id: str) -> None:
        self._active.pop(conn_id, None)

    @property
    def active_count(self) -> int:
        return len(self._active)
