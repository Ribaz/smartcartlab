# database/image_prompts.py
# Provides persistence helpers for generated image prompts.

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from database.connections import get_social_connection

DB_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def _utc_now() -> str:
    return datetime.now(UTC).strftime(DB_DATETIME_FORMAT)


def save_image_prompt(
    article_id: str,
    topic_id: int,
    prompt: str,
) -> int:
    """Save an image prompt and return its ID."""
    with get_social_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO image_prompts (
                article_id,
                topic_id,
                prompt,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                article_id,
                topic_id,
                prompt.strip(),
                _utc_now(),
            ),
        )

        prompt_id = cursor.lastrowid

    if prompt_id is None:
        raise RuntimeError("Failed to save image prompt.")

    return prompt_id


def get_image_prompt_by_topic(
    topic_id: int,
) -> sqlite3.Row | None:
    """Return the image prompt associated with a topic."""
    with get_social_connection() as connection:
        return connection.execute(
            """
            SELECT id, article_id, topic_id, prompt, created_at
            FROM image_prompts
            WHERE topic_id = ?
            """,
            (topic_id,),
        ).fetchone()


def image_prompt_exists(topic_id: int) -> bool:
    """Return whether an image prompt exists for a topic."""
    with get_social_connection() as connection:
        row = connection.execute(
            """
            SELECT 1
            FROM image_prompts
            WHERE topic_id = ?
            LIMIT 1
            """,
            (topic_id,),
        ).fetchone()

    return row is not None