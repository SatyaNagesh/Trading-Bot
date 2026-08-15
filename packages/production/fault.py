"""Fault Tolerance — retry decorator, fallback providers, write queue."""

import asyncio
import functools
import inspect
import json
import time
import threading
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

T = TypeVar("T")

# ── Retry Decorator ─────────────────────────────────────────────────


@dataclass
class RetryConfig:
    max_retries: int = 3
    base_delay: float = 0.5
    max_delay: float = 10.0
    backoff_factor: float = 2.0
    retryable_exceptions: tuple = (ConnectionError, TimeoutError, OSError)


def retry(
    max_retries: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 10.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: tuple = (ConnectionError, TimeoutError, OSError),
):
    config = RetryConfig(max_retries, base_delay, max_delay, backoff_factor, retryable_exceptions)
    return _RetryDecorator(config)


class _RetryDecorator:
    def __init__(self, config: RetryConfig):
        self.config = config

    def __call__(self, fn: Callable[..., T]) -> Callable[..., T]:
        if inspect.iscoroutinefunction(fn):
            return self._async_wrap(fn)
        return self._sync_wrap(fn)

    def _sync_wrap(self, fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_error: Exception | None = None
            delay = self.config.base_delay
            for attempt in range(self.config.max_retries + 1):
                try:
                    return fn(*args, **kwargs)
                except self.config.retryable_exceptions as e:
                    last_error = e
                    if attempt < self.config.max_retries:
                        time.sleep(min(delay, self.config.max_delay))
                        delay *= self.config.backoff_factor
            msg = f"Failed after {self.config.max_retries} retries: {last_error}"
            raise RuntimeError(msg) from last_error

        return wrapper

    def _async_wrap(self, fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_error: Exception | None = None
            delay = self.config.base_delay
            for attempt in range(self.config.max_retries + 1):
                try:
                    return await fn(*args, **kwargs)
                except self.config.retryable_exceptions as e:
                    last_error = e
                    if attempt < self.config.max_retries:
                        await asyncio.sleep(min(delay, self.config.max_delay))
                        delay *= self.config.backoff_factor
            msg = f"Failed after {self.config.max_retries} retries: {last_error}"
            raise RuntimeError(msg) from last_error

        return wrapper


# ── Fallback Provider ───────────────────────────────────────────────


class FallbackProvider:
    def __init__(self, providers: list[tuple[str, Callable[..., Any]]]):
        self.providers = providers
        self.failover_count: dict[str, int] = {name: 0 for name, _ in providers}

    def execute(self, *args: Any, **kwargs: Any) -> Any:
        last_error: Exception | None = None
        for name, provider in self.providers:
            try:
                result = provider(*args, **kwargs)
                return result
            except Exception as e:
                self.failover_count[name] += 1
                last_error = e
        msg = f"All providers failed. Last error: {last_error}"
        raise RuntimeError(msg) from last_error


# ── Write Queue ─────────────────────────────────────────────────────


@dataclass
class WriteBatch:
    namespace: str
    key: str
    value: Any
    timestamp: str = ""


class WriteQueue:
    def __init__(self, db_path: str = "data/write_queue.json", max_retries: int = 5):
        self.db_path = Path(db_path)
        self._lock = threading.Lock()
        self._max_retries = max_retries
        self._queue: list[WriteBatch] = []
        self._load()

    def enqueue(self, namespace: str, key: str, value: Any) -> None:
        batch = WriteBatch(
            namespace=namespace,
            key=key,
            value=value,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            self._queue.append(batch)
            self._save()

    def _save(self) -> None:
        data = [
            {"namespace": b.namespace, "key": b.key, "value": b.value, "timestamp": b.timestamp}
            for b in self._queue
        ]
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path.write_text(json.dumps(data, default=str))

    def _load(self) -> None:
        if self.db_path.exists():
            try:
                data = json.loads(self.db_path.read_text())
                self._queue = [
                    WriteBatch(
                        namespace=d["namespace"],
                        key=d["key"],
                        value=d["value"],
                        timestamp=d.get("timestamp", ""),
                    )
                    for d in data
                ]
            except (json.JSONDecodeError, KeyError):
                self._queue = []

    def flush(self, writer: Callable[[str, str, Any], None]) -> int:
        with self._lock:
            to_process = list(self._queue)
            self._queue = []
            self._save()
        flushed = 0
        for batch in to_process:
            for attempt in range(self._max_retries):
                try:
                    writer(batch.namespace, batch.key, batch.value)
                    flushed += 1
                    break
                except Exception:
                    if attempt < self._max_retries - 1:
                        time.sleep(0.5 * (2**attempt))
                    else:
                        with self._lock:
                            self._queue.append(batch)
                            self._save()
        return flushed

    def size(self) -> int:
        with self._lock:
            return len(self._queue)
