"""SQLite-backed failed ingest record store."""

from datetime import datetime
from pathlib import Path
from typing import Optional

import aiosqlite
from loguru import logger

from app.core.config import get_settings


class ErrorStore:
    """Persist failed image ingest records for inspection and retry."""

    def __init__(self):
        self.settings = get_settings()
        self.db_path = self.settings.error_db_path
        self._initialized = False

    async def init(self):
        """Create the error database and indexes when needed."""
        if self._initialized:
            return

        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS errors (
                    id TEXT PRIMARY KEY,
                    url TEXT,
                    error_message TEXT,
                    base64_preview TEXT,
                    created_at TEXT
                )
                """
            )
            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_errors_created_at
                ON errors(created_at)
                """
            )
            await db.commit()

        self._initialized = True
        logger.info(f"Error store initialized: {self.db_path}")

    async def add_error(
        self,
        id: str,
        url: str,
        error_message: str,
        base64_preview: Optional[str] = None,
    ):
        """Add or replace one failed ingest record."""
        if not self._initialized:
            await self.init()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO errors (id, url, error_message, base64_preview, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    id,
                    url,
                    error_message,
                    base64_preview[:100] if base64_preview else None,
                    datetime.now().isoformat(),
                ),
            )
            await db.commit()

    async def get_errors(
        self,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """Return failed ingest records in reverse chronological order."""
        if not self._initialized:
            await self.init()

        offset = (page - 1) * page_size

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute("SELECT COUNT(*) as count FROM errors")
            row = await cursor.fetchone()
            total = row["count"]

            cursor = await db.execute(
                """
                SELECT id, url, error_message, created_at
                FROM errors
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (page_size, offset),
            )

            rows = await cursor.fetchall()
            errors = [
                {
                    "id": row["id"],
                    "url": row["url"],
                    "error_message": row["error_message"],
                    "created_at": row["created_at"],
                }
                for row in rows
            ]

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "errors": errors,
        }

    async def delete_error(self, id: str) -> bool:
        """Delete one failed ingest record."""
        if not self._initialized:
            await self.init()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM errors WHERE id = ?", (id,))
            await db.commit()
            return cursor.rowcount > 0

    async def clear_errors(self) -> int:
        """Delete all failed ingest records."""
        if not self._initialized:
            await self.init()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM errors")
            await db.commit()
            return cursor.rowcount

    async def count(self) -> int:
        """Return the failed ingest record count."""
        if not self._initialized:
            await self.init()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM errors")
            row = await cursor.fetchone()
            return row[0]


error_store = ErrorStore()
