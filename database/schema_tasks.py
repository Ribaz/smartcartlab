# database/schema_tasks.py
# Defines the database schema for queued background tasks.

import logging

from database.connections import get_task_connection

logger = logging.getLogger(__name__)


def initialize_task_db() -> None:
    """Create the task manager tables if they do not exist."""
    with get_task_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS task_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_type TEXT NOT NULL,
                payload TEXT,
                result_json TEXT,
                status TEXT NOT NULL DEFAULT 'PENDING',
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT
            )
            """
        )

    logger.info("Task Manager database schema initialized.")