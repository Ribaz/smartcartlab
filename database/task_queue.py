# database/task_queue.py
# Provides persistence helpers for queued background tasks.

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from database.connections import get_task_connection


def _utc_now() -> str:
    """Return the current UTC timestamp in database format."""
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def enqueue_task(
    task_type: str,
    payload: dict[str, Any] | None = None,
) -> int:
    """Add a new task to the queue and return its ID."""
    payload_json = json.dumps(payload or {}, ensure_ascii=False)

    with get_task_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO task_queue (
                task_type,
                payload,
                status,
                created_at
            )
            VALUES (?, ?, 'PENDING', ?)
            """,
            (
                task_type,
                payload_json,
                _utc_now(),
            ),
        )

        task_id = cursor.lastrowid

    if task_id is None:
        raise RuntimeError("Failed to create queued task.")

    return task_id


def claim_next_task() -> dict[str, Any] | None:
    """
    Atomically claim the next pending task.

    Only one task may be RUNNING at a time.
    """
    connection = get_task_connection()

    try:
        connection.execute("BEGIN IMMEDIATE")

        running_task = connection.execute(
            """
            SELECT id
            FROM task_queue
            WHERE status = 'RUNNING'
            LIMIT 1
            """
        ).fetchone()

        if running_task:
            connection.rollback()
            return None

        task = connection.execute(
            """
            SELECT *
            FROM task_queue
            WHERE status = 'PENDING'
            ORDER BY id
            LIMIT 1
            """
        ).fetchone()

        if task is None:
            connection.rollback()
            return None

        connection.execute(
            """
            UPDATE task_queue
            SET
                status = 'RUNNING',
                attempts = attempts + 1,
                started_at = ?,
                last_error = NULL
            WHERE id = ?
            """,
            (
                _utc_now(),
                task["id"],
            ),
        )

        connection.commit()

        claimed_task = connection.execute(
            """
            SELECT *
            FROM task_queue
            WHERE id = ?
            """,
            (task["id"],),
        ).fetchone()

        if claimed_task is None:
            raise RuntimeError(
                f"Claimed task {task['id']} could not be reloaded."
            )

        result = dict(claimed_task)
        result["payload"] = json.loads(result["payload"] or "{}")

        return result

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def mark_task_completed(
    task_id: int,
    result: dict[str, Any] | None = None,
) -> None:
    """Mark a running task as completed and store its result."""
    result_json = json.dumps(result or {}, ensure_ascii=False)

    with get_task_connection() as connection:
        connection.execute(
            """
            UPDATE task_queue
            SET
                status = 'COMPLETED',
                result_json = ?,
                completed_at = ?,
                last_error = NULL
            WHERE id = ?
            """,
            (
                result_json,
                _utc_now(),
                task_id,
            ),
        )


def mark_task_failed(
    task_id: int,
    error: str,
) -> None:
    """Mark a running task as failed and store the error."""
    with get_task_connection() as connection:
        connection.execute(
            """
            UPDATE task_queue
            SET
                status = 'FAILED',
                last_error = ?,
                completed_at = ?
            WHERE id = ?
            """,
            (
                error,
                _utc_now(),
                task_id,
            ),
        )