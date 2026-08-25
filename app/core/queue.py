"""Task queue abstraction with optional Redis persistence."""

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Optional

from loguru import logger

from app.core.config import get_settings


try:
    import redis.asyncio as aioredis

    REDIS_AVAILABLE = True
except ImportError:
    aioredis = None
    REDIS_AVAILABLE = False


@dataclass
class IngestTask:
    """Queued image ingest task."""

    id: str
    base64: str
    url: str
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "IngestTask":
        return cls(**data)


class TaskQueue:
    """Queue ingest tasks in memory or Redis."""

    def __init__(self):
        self.settings = get_settings()
        self.queue_key = self.settings.redis_queue_key
        self._redis: Optional[Any] = None
        self._local_queue: asyncio.Queue = asyncio.Queue()
        self._use_redis = False

    async def connect(self):
        """Connect to Redis when configured; otherwise use the in-memory queue."""
        if not REDIS_AVAILABLE or not self.settings.redis_url:
            logger.info("Using in-memory ingest queue")
            self._use_redis = False
            return

        try:
            self._redis = aioredis.from_url(
                self.settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await self._redis.ping()
            self._use_redis = True
            logger.info("Connected to Redis ingest queue")
        except Exception as exc:
            logger.warning(f"Redis queue connection failed: {exc}; using in-memory queue")
            self._use_redis = False

    async def disconnect(self):
        """Close the Redis connection if it is active."""
        if self._redis:
            await self._redis.close()

    async def put(self, task: IngestTask) -> int:
        """Add one task and return the resulting queue size."""
        if self._use_redis and self._redis:
            task_json = json.dumps(task.to_dict())
            await self._redis.rpush(self.queue_key, task_json)
            return await self._redis.llen(self.queue_key)

        await self._local_queue.put(task)
        return self._local_queue.qsize()

    async def put_batch(self, tasks: list[IngestTask]) -> int:
        """Add multiple tasks and return the resulting queue size."""
        if self._use_redis and self._redis:
            pipe = self._redis.pipeline()
            for task in tasks:
                task_json = json.dumps(task.to_dict())
                pipe.rpush(self.queue_key, task_json)
            await pipe.execute()
            return await self._redis.llen(self.queue_key)

        for task in tasks:
            await self._local_queue.put(task)
        return self._local_queue.qsize()

    async def get_batch(self, batch_size: int, timeout: float = 0.5) -> list[IngestTask]:
        """Fetch up to batch_size tasks from the active queue."""
        tasks = []

        if self._use_redis and self._redis:
            start_time = asyncio.get_event_loop().time()
            while len(tasks) < batch_size:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > timeout and tasks:
                    break

                task_json = await self._redis.lpop(self.queue_key)
                if task_json:
                    tasks.append(IngestTask.from_dict(json.loads(task_json)))
                else:
                    if tasks:
                        break
                    await asyncio.sleep(0.1)
                    if asyncio.get_event_loop().time() - start_time > timeout:
                        break
            return tasks

        start_time = asyncio.get_event_loop().time()
        while len(tasks) < batch_size:
            elapsed = asyncio.get_event_loop().time() - start_time
            remaining_timeout = max(0.01, timeout - elapsed)
            try:
                task = await asyncio.wait_for(
                    self._local_queue.get(),
                    timeout=remaining_timeout,
                )
                tasks.append(task)
            except asyncio.TimeoutError:
                break

        return tasks

    async def size(self) -> int:
        """Return the active queue size."""
        if self._use_redis and self._redis:
            return await self._redis.llen(self.queue_key)
        return self._local_queue.qsize()

    async def clear(self):
        """Clear pending tasks from the active queue."""
        if self._use_redis and self._redis:
            await self._redis.delete(self.queue_key)
            return

        while not self._local_queue.empty():
            try:
                self._local_queue.get_nowait()
            except asyncio.QueueEmpty:
                break


task_queue = TaskQueue()
