"""Task Engine — async task queue with Redis-backed persistence and scheduling."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

import redis.asyncio as aioredis

from packages.core.logging import get_logger

logger = get_logger("task_engine")


class TaskPriority(Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: list[str] = field(default_factory=list)


class TaskHandler(ABC):
    @abstractmethod
    async def handle(self, task: Task) -> dict[str, Any]:
        ...


class TaskEngine:
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis = aioredis.from_url(redis_url)
        self.handlers: dict[str, TaskHandler] = {}
        self.queue_key = "quantlab:tasks:queue"
        self.processing_key = "quantlab:tasks:processing"

    def register_handler(self, name: str, handler: TaskHandler) -> None:
        self.handlers[name] = handler

    async def enqueue(self, task: Task) -> str:
        await self.redis.lpush(self.queue_key, task.id)
        await self.redis.hset(
            f"quantlab:task:{task.id}",
            mapping={
                "name": task.name,
                "payload": str(task.payload),
                "priority": task.priority.value,
                "status": task.status.value,
                "retry_count": str(task.retry_count),
                "max_retries": str(task.max_retries),
            },
        )
        logger.info("task_enqueued", id=task.id, name=task.name)
        return task.id

    async def process_next(self) -> bool:
        task_id = await self.redis.rpop(self.queue_key)
        if not task_id:
            return False
        task_data = await self.redis.hgetall(f"quantlab:task:{task_id}")
        if not task_data:
            return False
        task = Task(
            id=task_id.decode() if isinstance(task_id, bytes) else task_id,
            name=task_data[b"name"].decode(),
            priority=TaskPriority(task_data[b"priority"].decode()),
        )
        handler = self.handlers.get(task.name)
        if not handler:
            logger.warning("no_handler", task=task.name)
            return True
        try:
            task.status = TaskStatus.RUNNING
            result = await handler.handle(task)
            task.status = TaskStatus.SUCCESS
            logger.info("task_completed", id=task.id, result=result)
        except Exception as e:
            task.retry_count += 1
            if task.retry_count < task.max_retries:
                await self.enqueue(task)
            else:
                task.status = TaskStatus.FAILED
            logger.error("task_failed", id=task.id, error=str(e))
        return True

    async def drain(self, limit: int = 100) -> int:
        count = 0
        for _ in range(limit):
            if not await self.process_next():
                break
            count += 1
        return count
