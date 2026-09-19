# database/images.py
# Provides persistence helpers for generated images.

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from database.connections import get_social_connection

DB_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def _utc_now() -> str:
    return datetime.now(UTC).strftime(DB_DATETIME_FORMAT)


def save_generated_image(
    *,
    article_id: str,
    topic_id: int,
    prompt_id: int,
    provider: str,
    model: str,
    width: int,
    height: int,
    file_path: str,
) -> int:
    """Save generated image metadata and return its ID."""
    with get_social_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO generated_images (
                article_id,
                topic_id,
                prompt_id,
                provider,
                model,
                width,
                height,
                file_path,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                article_id,
                topic_id,
                prompt_id,
                provider,
                model,
                width,
                height,
                file_path,
                _utc_now(),
            ),
        )

        image_id = cursor.lastrowid

    if image_id is None:
        raise RuntimeError("Failed to save generated image.")

    return image_id


def get_generated_images_by_prompt(
    prompt_id: int,
) -> list[sqlite3.Row]:
    """Return generated images associated with an image prompt."""
    with get_social_connection() as connection:
        return connection.execute(
            """
            SELECT
                id,
                article_id,
                topic_id,
                prompt_id,
                provider,
                model,
                width,
                height,
                file_path,
                created_at
            FROM generated_images
            WHERE prompt_id = ?
            ORDER BY id
            """,
            (prompt_id,),
        ).fetchall()


def generated_image_exists(prompt_id: int) -> bool:
    """Return whether an image has already been generated for a prompt."""
    with get_social_connection() as connection:
        row = connection.execute(
            """
            SELECT 1
            FROM generated_images
            WHERE prompt_id = ?
            LIMIT 1
            """,
            (prompt_id,),
        ).fetchone()

    return row is not None

    