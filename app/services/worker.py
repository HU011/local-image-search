"""Background worker for queued image ingest tasks."""

import asyncio
from datetime import datetime
from typing import Optional

from loguru import logger

from app.core.config import get_settings
from app.core.queue import IngestTask, task_queue
from app.services.embedding import embedding_service
from app.services.error_store import error_store
from app.services.vector_db import vector_db
from app.utils.image import decode_base64_image


class WorkerStats:
    """Runtime ingest worker counters."""

    def __init__(self):
        self.processed_count = 0
        self.failed_count = 0
        self.processing_count = 0
        self.last_batch_time: Optional[datetime] = None
        self.is_running = False


class IngestWorker:
    """Fetch queued tasks, embed images, and upsert vectors."""

    def __init__(self):
        self.settings = get_settings()
        self.stats = WorkerStats()
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    async def start(self):
        """Start the background worker task."""
        if self._task and not self._task.done():
            logger.warning("Worker is already running")
            return

        self._stop_event.clear()
        self.stats.is_running = True
        self._task = asyncio.create_task(self._run())
        logger.info("Worker started")

    async def stop(self):
        """Stop the background worker task."""
        self._stop_event.set()
        self.stats.is_running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Worker stopped")

    async def _run(self):
        """Main worker loop."""
        logger.info(f"Worker loop started, batch_size={self.settings.batch_size}")

        while not self._stop_event.is_set():
            try:
                tasks = await task_queue.get_batch(
                    batch_size=self.settings.batch_size,
                    timeout=self.settings.queue_wait_timeout,
                )

                if not tasks:
                    await asyncio.sleep(0.1)
                    continue

                await self._process_batch(tasks)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Worker error: {exc}")
                await asyncio.sleep(1)

    async def _process_batch(self, tasks: list[IngestTask]):
        """Process one batch of ingest tasks."""
        batch_start = datetime.now()
        self.stats.processing_count = len(tasks)

        logger.info(f"Processing batch: {len(tasks)} images")

        images = []
        valid_tasks = []
        failed_tasks = []

        for task in tasks:
            try:
                image = decode_base64_image(task.base64)
                images.append(image)
                valid_tasks.append(task)
            except Exception as exc:
                failed_tasks.append((task, str(exc)))

        for task, error_message in failed_tasks:
            await error_store.add_error(
                id=task.id,
                url=task.url,
                error_message=f"Image decode failed: {error_message}",
                base64_preview=task.base64,
            )
            self.stats.failed_count += 1

        if not images:
            self.stats.processing_count = 0
            return

        try:
            embeddings = embedding_service.get_embeddings_batch(images)
            ids = [task.id for task in valid_tasks]
            urls = [task.url for task in valid_tasks]
            count = vector_db.upsert_vectors(ids, embeddings, urls)

            self.stats.processed_count += count
            self.stats.last_batch_time = datetime.now()

            batch_time = (datetime.now() - batch_start).total_seconds()
            logger.info(
                f"Batch complete: success={count}, failed={len(failed_tasks)}, "
                f"elapsed={batch_time:.2f}s"
            )

        except Exception as exc:
            error_message = f"Batch inference failed: {exc}"
            logger.error(error_message)

            for task in valid_tasks:
                await error_store.add_error(
                    id=task.id,
                    url=task.url,
                    error_message=error_message,
                    base64_preview=task.base64,
                )
                self.stats.failed_count += 1

        finally:
            self.stats.processing_count = 0


ingest_worker = IngestWorker()
